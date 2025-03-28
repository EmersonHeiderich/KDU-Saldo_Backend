# src/erp_integration/erp_cost_service.py
# Fetches product cost data from the TOTVS ERP API.

from typing import List, Optional, Dict, Any
import requests
from src.config import config
from src.domain.cost import CostResponse, ProductCost # Domain models
from .erp_auth_service import ErpAuthService # ERP Auth service
from src.utils.logger import logger
from src.api.errors import ErpIntegrationError # Custom error

class ErpCostService:
    """
    Service to interact with the ERP's product cost endpoint.
    """

    def __init__(self, erp_auth_service: ErpAuthService):
        """
        Initializes the ErpCostService.

        Args:
            erp_auth_service: Instance of ErpAuthService to get auth tokens.
        """
        self.erp_auth_service = erp_auth_service
        self.api_url = f"{config.API_BASE_URL.rstrip('/')}{config.COSTS_ENDPOINT}"
        self.max_retries = config.MAX_RETRIES
        self.page_size = config.PAGE_SIZE
        self.company_code = config.COMPANY_CODE
        logger.info(f"ErpCostService initialized for URL: {self.api_url}")

    def get_costs(self,
                  reference_code_list: Optional[List[str]] = None,
                  is_fabric: bool = False) -> List[ProductCost]:
        """
        Retrieves product costs from the ERP, handling pagination.

        Args:
            reference_code_list: Optional list of reference codes to filter by.
            is_fabric: If True, applies filters for raw materials (fabrics).
                       If False, applies filters for finished products.

        Returns:
            A list of ProductCost objects containing cost data.

        Raises:
            ErpIntegrationError: If communication with the ERP fails or the response is invalid.
        """
        all_items: List[ProductCost] = []
        current_page = 1
        has_next = True

        log_prefix = "fabrics" if is_fabric else f"products (Refs: {reference_code_list or 'All'})"
        logger.info(f"Starting ERP cost fetch for {log_prefix}.")

        while has_next:
            logger.debug(f"Fetching page {current_page} for {log_prefix} costs...")
            try:
                payload = self._build_request_payload(current_page, reference_code_list, is_fabric)
                response_data = self._make_api_request(payload)

                if not response_data or not isinstance(response_data, dict):
                    logger.warning(f"Received invalid cost response data for page {current_page}. Aborting fetch.")
                    break

                cost_response = CostResponse.from_dict(response_data)
                page_items = cost_response.items
                all_items.extend(page_items)

                has_next = cost_response.has_next
                total_pages = cost_response.total_pages
                logger.debug(f"Fetched cost page {current_page}/{total_pages or '?'}. Items: {len(page_items)}. HasNext: {has_next}")

                current_page += 1

                # Safety break
                if current_page > (total_pages + 5) and total_pages > 0:
                     logger.warning(f"Potential infinite loop detected in cost pagination. Stopping at page {current_page-1}.")
                     break
                if current_page > 500:
                     logger.warning(f"Reached absolute page limit (500) for cost fetch. Stopping.")
                     break


            except ErpIntegrationError as e:
                 logger.error(f"Failed to fetch page {current_page} for {log_prefix} costs: {e}", exc_info=True)
                 raise e
            except Exception as e:
                 logger.error(f"Unexpected error fetching page {current_page} for {log_prefix} costs: {e}", exc_info=True)
                 raise ErpIntegrationError(f"Unexpected error during cost fetch: {e}") from e

        logger.info(f"Finished ERP cost fetch for {log_prefix}. Total items retrieved: {len(all_items)}")
        return all_items


    def _make_api_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Makes the HTTP request to the ERP API, handling retries and auth."""
        attempt = 0
        while attempt <= self.max_retries:
            attempt += 1
            logger.debug(f"Attempt {attempt}/{self.max_retries + 1} to call ERP cost API.")
            try:
                token = self.erp_auth_service.get_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }
                response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
                response.raise_for_status()
                return response.json()

            except requests.exceptions.HTTPError as e:
                 status_code = e.response.status_code
                 if status_code == 401 and attempt <= self.max_retries:
                      logger.warning(f"ERP Cost API returned 401 (Attempt {attempt}). Invalidating token and retrying.")
                      self.erp_auth_service.invalidate_token()
                      continue
                 else:
                      response_text = e.response.text[:500]
                      logger.error(f"HTTP error {status_code} from ERP cost API: {e}. Response: {response_text}", exc_info=True)
                      raise ErpIntegrationError(f"ERP cost API request failed with status {status_code}: {response_text}") from e

            except requests.exceptions.RequestException as e:
                 logger.error(f"Network error connecting to ERP cost API: {e}", exc_info=True)
                 if attempt <= self.max_retries:
                      logger.warning(f"Retrying cost API call after network error (Attempt {attempt}).")
                      continue
                 else:
                      raise ErpIntegrationError(f"Network error connecting to ERP cost API after {attempt} attempts: {e}") from e

        logger.error("Exhausted retries for ERP cost API request.")
        raise ErpIntegrationError("Exhausted retries trying to reach ERP cost API.")


    def _build_request_payload(self, page: int, reference_code_list: Optional[List[str]], is_fabric: bool) -> Dict[str, Any]:
        """Constructs the JSON payload for the cost API request."""

        base_payload = {
            "page": page,
            "pageSize": self.page_size,
            "order": "colorCode,productSize", # Or relevant order for costs
             "filter": {
                 "branchInfo": {
                     "branchCode": self.company_code,
                     "isActive": True,
                 }
             },
             "option": {
                 # Specify which cost codes are needed
                 "costs": [{"branchCode": self.company_code, "costCodeList": [2]}] # Example: Cost Code 2 = Custo Reposição? Verify.
             }
        }

        if is_fabric:
             # Filters for Raw Materials / Tecidos
             base_payload["filter"]["branchInfo"].update({
                 "isFinishedProduct": False,
                 "isRawMaterial": True,
                 "isBulkMaterial": False,
                 "isOwnProduction": False,
             })
             base_payload["filter"]["classifications"] = [
                 {"type": 4000, "codeList": ["001"]},
                 {"type": 4001, "codeList": ["001", "002", "003"]}
             ]
        else:
             # Filters for Finished Products
             base_payload["filter"]["branchInfo"].update({
                 "isFinishedProduct": True,
                 "isRawMaterial": False,
                 "isBulkMaterial": False,
                 "isOwnProduction": True,
             })
             if reference_code_list:
                  base_payload["filter"]["referenceCodeList"] = reference_code_list

        logger.debug(f"Generated ERP cost payload: {base_payload}")
        return base_payload