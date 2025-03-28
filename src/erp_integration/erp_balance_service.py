# src/erp_integration/erp_balance_service.py
# Fetches product balance data from the TOTVS ERP API.

from typing import List, Optional, Dict, Any
import requests
from src.config import config
from src.domain.balance import ProductResponse, ProductItem # Domain models
from .erp_auth_service import ErpAuthService # ERP Auth service
from src.utils.logger import logger
from src.api.errors import ErpIntegrationError # Custom error

class ErpBalanceService:
    """
    Service to interact with the ERP's product balance endpoint.
    """

    def __init__(self, erp_auth_service: ErpAuthService):
        """
        Initializes the ErpBalanceService.

        Args:
            erp_auth_service: Instance of ErpAuthService to get auth tokens.
        """
        self.erp_auth_service = erp_auth_service
        self.api_url = f"{config.API_BASE_URL.rstrip('/')}{config.BALANCES_ENDPOINT}"
        self.max_retries = config.MAX_RETRIES
        self.page_size = config.PAGE_SIZE
        self.company_code = config.COMPANY_CODE
        logger.info(f"ErpBalanceService initialized for URL: {self.api_url}")

    def get_balances(self,
                     reference_code_list: Optional[List[str]] = None,
                     is_fabric: bool = False) -> List[ProductItem]:
        """
        Retrieves product balances from the ERP, handling pagination.

        Args:
            reference_code_list: Optional list of reference codes to filter by (only for finished products).
            is_fabric: If True, applies filters for raw materials (fabrics).
                       If False, applies filters for finished products.

        Returns:
            A list of ProductItem objects containing balance data.

        Raises:
            ErpIntegrationError: If communication with the ERP fails or the response is invalid.
        """
        all_items: List[ProductItem] = []
        current_page = 1
        has_next = True

        log_prefix = "fabrics" if is_fabric else f"products (Refs: {reference_code_list or 'All'})"
        logger.info(f"Starting ERP balance fetch for {log_prefix}.")

        while has_next:
            logger.debug(f"Fetching page {current_page} for {log_prefix} balances...")
            try:
                payload = self._build_request_payload(current_page, reference_code_list, is_fabric)
                response_data = self._make_api_request(payload)

                if not response_data or not isinstance(response_data, dict):
                    logger.warning(f"Received invalid response data for page {current_page}. Aborting fetch.")
                    # Should this be an error? Depends on API contract. Assume empty list is valid.
                    break # Stop pagination if response is weird

                # Parse response using domain model
                product_response = ProductResponse.from_dict(response_data)
                page_items = product_response.items
                all_items.extend(page_items)

                has_next = product_response.has_next
                total_pages = product_response.total_pages
                logger.debug(f"Fetched page {current_page}/{total_pages or '?'}. Items: {len(page_items)}. HasNext: {has_next}")

                current_page += 1

                # Safety break: Avoid infinite loops if hasNext is always true
                if current_page > (total_pages + 5) and total_pages > 0: # Allow a few extra pages just in case
                     logger.warning(f"Potential infinite loop detected in balance pagination. Stopping at page {current_page-1}.")
                     break
                if current_page > 500: # Absolute safety limit
                     logger.warning(f"Reached absolute page limit (500) for balance fetch. Stopping.")
                     break


            except ErpIntegrationError as e:
                 logger.error(f"Failed to fetch page {current_page} for {log_prefix} balances: {e}", exc_info=True)
                 # Re-raise the specific error
                 raise e
            except Exception as e:
                 logger.error(f"Unexpected error fetching page {current_page} for {log_prefix} balances: {e}", exc_info=True)
                 # Wrap in generic ERP error
                 raise ErpIntegrationError(f"Unexpected error during balance fetch: {e}") from e

        logger.info(f"Finished ERP balance fetch for {log_prefix}. Total items retrieved: {len(all_items)}")
        return all_items

    def _make_api_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Makes the actual HTTP request to the ERP API, handling retries and auth.

        Args:
            payload: The request body (dictionary).

        Returns:
            The JSON response dictionary from the API.

        Raises:
            ErpIntegrationError: If the request fails after retries.
        """
        attempt = 0
        while attempt <= self.max_retries:
            attempt += 1
            logger.debug(f"Attempt {attempt}/{self.max_retries + 1} to call ERP balance API.")
            try:
                token = self.erp_auth_service.get_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    # Add other headers if required by ERP
                }

                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=30 # Adjust timeout as needed
                )
                response.raise_for_status() # Raise HTTPError for 4xx/5xx
                return response.json()

            except requests.exceptions.HTTPError as e:
                 status_code = e.response.status_code
                 # Check for 401 Unauthorized specifically for token refresh
                 if status_code == 401 and attempt <= self.max_retries:
                      logger.warning(f"ERP API returned 401 Unauthorized (Attempt {attempt}). Invalidating token and retrying.")
                      self.erp_auth_service.invalidate_token()
                      # Optional: Add a small delay before retrying?
                      # time.sleep(0.5)
                      continue # Go to next attempt loop
                 else:
                      # For other HTTP errors or if retries exhausted
                      response_text = e.response.text[:500] # Limit response text length
                      logger.error(f"HTTP error {status_code} from ERP balance API: {e}. Response: {response_text}", exc_info=True)
                      raise ErpIntegrationError(f"ERP API request failed with status {status_code}: {response_text}") from e

            except requests.exceptions.RequestException as e:
                 # Includes connection errors, timeouts, etc.
                 logger.error(f"Network error connecting to ERP balance API: {e}", exc_info=True)
                 if attempt <= self.max_retries:
                      logger.warning(f"Retrying after network error (Attempt {attempt}).")
                      # Optional: Add delay before retry
                      # time.sleep(1)
                      continue
                 else:
                      raise ErpIntegrationError(f"Network error connecting to ERP API after {attempt} attempts: {e}") from e
            # except Exception as e: # Catch other potential errors like JSONDecodeError
            #      logger.error(f"Unexpected error during ERP API request: {e}", exc_info=True)
            #      # Should we retry on unexpected errors? Maybe not.
            #      raise ErpIntegrationError(f"Unexpected error during ERP API request: {e}") from e

        # Should not be reached if loop logic is correct, but as fallback:
        logger.error("Exhausted retries for ERP balance API request.")
        raise ErpIntegrationError("Exhausted retries trying to reach ERP balance API.")


    def _build_request_payload(self, page: int, reference_code_list: Optional[List[str]], is_fabric: bool) -> Dict[str, Any]:
        """Constructs the JSON payload for the balance API request."""

        # Common parts
        base_payload = {
            "page": page,
            "pageSize": self.page_size,
            "order": "colorCode,productSize", # Consistent ordering
             "filter": {
                 "branchInfo": {
                     "branchCode": self.company_code,
                     "isActive": True,
                     # Specific flags based on product type
                 }
             },
             "option": {
                 "balances": [
                     {
                         "branchCode": self.company_code,
                         "stockCodeList": [1], # Always use stock code 1 (FISICO)? Verify requirement.
                         # Specific flags based on product type
                     }
                 ]
             }
        }

        # Type-specific adjustments
        if is_fabric:
             # Filters for Raw Materials / Tecidos
             base_payload["filter"]["branchInfo"].update({
                 "isFinishedProduct": False,
                 "isRawMaterial": True,
                 "isBulkMaterial": False, # Assuming fabrics aren't bulk
                 "isOwnProduction": False,
             })
             # Fabric-specific classifications (Example based on original code)
             base_payload["filter"]["classifications"] = [
                 {"type": 4000, "codeList": ["001"]}, # Example: Tipo = Matéria Prima
                 {"type": 4001, "codeList": ["001", "002", "003"]} # Example: Subtipo = Tecido Plano, Malha, etc.
             ]
             # Balance options for fabrics (don't need sales/production orders?)
             base_payload["option"]["balances"][0].update({
                 "isSalesOrder": False, # Typically no sales orders for raw materials?
                 "isTransaction": True, # Inputs/Outputs
                 "isProductionOrder": False, # Typically no production orders *for* raw materials?
             })
        else:
             # Filters for Finished Products
             base_payload["filter"]["branchInfo"].update({
                 "isFinishedProduct": True,
                 "isRawMaterial": False,
                 "isBulkMaterial": False,
                 "isOwnProduction": True, # Assuming finished goods are own production
             })
             # Add reference code filter if provided
             if reference_code_list:
                  base_payload["filter"]["referenceCodeList"] = reference_code_list
             # Balance options for finished products
             base_payload["option"]["balances"][0].update({
                 "isSalesOrder": True, # Include sales orders
                 "isTransaction": True, # Inputs/Outputs
                 "isProductionOrder": True, # Include production orders
             })

        logger.debug(f"Generated ERP balance payload: {base_payload}")
        return base_payload