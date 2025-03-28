# src/erp_integration/erp_person_service.py
# Fetches Person (Individual, Legal Entity, Statistics) data from the TOTVS ERP API.

import requests
from typing import Optional, List, Dict, Any, Union
from src.config import config
from src.domain.person import IndividualDataModel, LegalEntityDataModel, PersonStatisticsResponseModel
from .erp_auth_service import ErpAuthService
from src.utils.logger import logger
from src.api.errors import ErpIntegrationError, ErpNotFoundError # Custom errors

class ErpPersonService:
    """
    Service to interact with the ERP's Person related endpoints.
    Handles fetching individuals, legal entities, and statistics.
    """

    def __init__(self, erp_auth_service: ErpAuthService):
        """
        Initializes the ErpPersonService.

        Args:
            erp_auth_service: Instance of ErpAuthService for authentication.
        """
        self.erp_auth_service = erp_auth_service
        self.base_url = config.API_BASE_URL.rstrip('/')
        # Construct full URLs for endpoints
        self.individuals_url = f"{self.base_url}{config.INDIVIDUALS_ENDPOINT}"
        self.legal_entities_url = f"{self.base_url}{config.LEGAL_ENTITIES_ENDPOINT}"
        self.stats_url = f"{self.base_url}{config.PERSON_STATS_ENDPOINT}"
        self.max_retries = config.MAX_RETRIES
        self.company_code = config.COMPANY_CODE
        logger.info("ErpPersonService initialized.")

    def _make_request(self, url: str, method: str = "POST", params: Optional[Dict] = None, json_payload: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Internal helper to make requests to the Person API, handling auth and retries.

        Args:
            url: The full URL for the API endpoint.
            method: HTTP method ("GET" or "POST").
            params: Dictionary of query parameters for GET requests.
            json_payload: Dictionary payload for POST requests.

        Returns:
            The JSON response dictionary.

        Raises:
            ErpIntegrationError: If the request fails after retries.
            ErpNotFoundError: If the API returns a 404 status.
        """
        attempt = 0
        while attempt <= self.max_retries:
            attempt += 1
            logger.debug(f"Attempt {attempt}/{self.max_retries + 1} to call ERP Person API: {method} {url}")
            try:
                token = self.erp_auth_service.get_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    # Add company code header if required by API - Check TOTVS docs
                    # "CompanyCode": str(self.company_code),
                    # "BranchCode": str(self.company_code), # Might be needed
                }

                response: requests.Response
                if method.upper() == "POST":
                    response = requests.post(url, json=json_payload, headers=headers, timeout=20)
                elif method.upper() == "GET":
                    response = requests.get(url, params=params, headers=headers, timeout=20)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Check for 404 specifically before raise_for_status
                if response.status_code == 404:
                     logger.warning(f"ERP Person API returned 404 Not Found for {method} {url}. Params/Payload: {params or json_payload}")
                     # Map 404 to a specific custom exception
                     raise ErpNotFoundError("Resource not found in ERP.")

                response.raise_for_status() # Raise HTTPError for other 4xx/5xx
                # Handle cases where API returns 200 but empty body or non-JSON
                try:
                     return response.json()
                except requests.exceptions.JSONDecodeError:
                     logger.error(f"Failed to decode JSON response from {method} {url}. Status: {response.status_code}, Response: {response.text[:200]}")
                     raise ErpIntegrationError("Received non-JSON response from ERP Person API.")


            except requests.exceptions.HTTPError as e:
                 status_code = e.response.status_code
                 if status_code == 401 and attempt <= self.max_retries:
                      logger.warning(f"ERP Person API returned 401 (Attempt {attempt}). Invalidating token and retrying.")
                      self.erp_auth_service.invalidate_token()
                      continue
                 else:
                      # ErpNotFoundError is handled above
                      response_text = e.response.text[:500]
                      logger.error(f"HTTP error {status_code} from ERP Person API ({method} {url}): {e}. Response: {response_text}", exc_info=True)
                      raise ErpIntegrationError(f"ERP Person API request failed with status {status_code}: {response_text}") from e

            except requests.exceptions.RequestException as e:
                 logger.error(f"Network error connecting to ERP Person API ({method} {url}): {e}", exc_info=True)
                 if attempt <= self.max_retries:
                      logger.warning(f"Retrying Person API call after network error (Attempt {attempt}).")
                      continue
                 else:
                      raise ErpIntegrationError(f"Network error connecting to ERP Person API after {attempt} attempts: {e}") from e

        logger.error(f"Exhausted retries for ERP Person API request: {method} {url}")
        raise ErpIntegrationError(f"Exhausted retries trying to reach ERP Person API: {method} {url}")

    def _search_person(self, url: str, filter_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Helper to perform a search and return the first item found, or None."""
        payload = {
            "filter": filter_payload,
            "expand": "phones,addresses,emails", # Request nested details
            "page": 1,
            "pageSize": 1 # Only need the first match
        }
        try:
            response_data = self._make_request(url, method="POST", json_payload=payload)
            items = response_data.get('items', [])
            if items and isinstance(items, list):
                logger.debug(f"Found person item in ERP search at {url} with filter {filter_payload}.")
                return items[0] # Return the first item dictionary
            else:
                 logger.debug(f"No items found in ERP search at {url} with filter {filter_payload}.")
                 return None
        except ErpNotFoundError:
             logger.debug(f"ERP search returned 404 (Not Found) for filter {filter_payload} at {url}.")
             return None # Treat ERP 404 as None found
        # Let other ErpIntegrationErrors propagate up


    # --- Public Methods ---

    def get_individual_by_code(self, code: int) -> Optional[IndividualDataModel]:
        """Fetches an individual from ERP by their code."""
        logger.debug(f"Searching ERP for individual by code: {code}")
        item_dict = self._search_person(self.individuals_url, {"personCodeList": [code]})
        if item_dict:
             return IndividualDataModel.from_dict(item_dict)
        return None

    def get_legal_entity_by_code(self, code: int) -> Optional[LegalEntityDataModel]:
        """Fetches a legal entity from ERP by their code."""
        logger.debug(f"Searching ERP for legal entity by code: {code}")
        item_dict = self._search_person(self.legal_entities_url, {"personCodeList": [code]})
        if item_dict:
             return LegalEntityDataModel.from_dict(item_dict)
        return None

    def get_individual_by_cpf(self, cpf: str) -> Optional[IndividualDataModel]:
        """Fetches an individual from ERP by their CPF."""
        logger.debug(f"Searching ERP for individual by CPF: {cpf[-4:]}") # Log last 4 digits
        item_dict = self._search_person(self.individuals_url, {"cpfList": [cpf]})
        if item_dict:
             return IndividualDataModel.from_dict(item_dict)
        return None

    def get_legal_entity_by_cnpj(self, cnpj: str) -> Optional[LegalEntityDataModel]:
        """Fetches a legal entity from ERP by their CNPJ."""
        logger.debug(f"Searching ERP for legal entity by CNPJ: {cnpj[-4:]}") # Log last 4 digits
        item_dict = self._search_person(self.legal_entities_url, {"cnpjList": [cnpj]})
        if item_dict:
             return LegalEntityDataModel.from_dict(item_dict)
        return None

    def get_customer_statistics(self, customer_code: int, is_admin: bool) -> Optional[PersonStatisticsResponseModel]:
        """Fetches customer statistics from the ERP."""
        # Determine BranchCode based on admin status (as per original logic)
        # TODO: Clarify requirement - should non-admins see stats only for their branch?
        branch_code = 1 if is_admin else self.company_code # Assuming 1 is a default/global branch for admin
        logger.debug(f"Fetching ERP statistics for customer code: {customer_code}, Branch: {branch_code}")

        params = {
            "CustomerCode": customer_code,
            "BranchCode": branch_code
        }
        try:
            response_data = self._make_request(self.stats_url, method="GET", params=params)
            if response_data: # Ensure response is not empty
                return PersonStatisticsResponseModel.from_dict(response_data)
            else:
                 logger.warning(f"Received empty response for statistics for customer {customer_code}.")
                 return None # Or raise ErpNotFoundError? Treat empty as not found for now.
        except ErpNotFoundError:
             logger.warning(f"ERP statistics not found (404) for customer code: {customer_code}")
             return None # Map ERP 404 to None result