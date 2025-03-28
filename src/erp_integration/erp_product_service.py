# src/erp_integration/erp_product_service.py
# Fetches generic product data (like fabric details) from the TOTVS ERP API.

from typing import List, Optional, Dict, Any
import requests
from src.config import config
from src.domain.fabric_details import FabricDetailsItem # Domain model for results
from .erp_auth_service import ErpAuthService # ERP Auth service
from src.utils.logger import logger
from src.api.errors import ErpIntegrationError # Custom error

class ErpProductService:
    """
    Service to interact with the ERP's generic product endpoint,
    used here specifically to fetch fabric details (width, grammage, etc.).
    """

    def __init__(self, erp_auth_service: ErpAuthService):
        """
        Initializes the ErpProductService.

        Args:
            erp_auth_service: Instance of ErpAuthService to get auth tokens.
        """
        self.erp_auth_service = erp_auth_service
        self.api_url = f"{config.API_BASE_URL.rstrip('/')}{config.PRODUCTS_ENDPOINT}"
        self.max_retries = config.MAX_RETRIES
        self.page_size = config.PAGE_SIZE
        self.company_code = config.COMPANY_CODE
        logger.info(f"ErpProductService initialized for URL: {self.api_url}")

    def get_fabric_details(self) -> Dict[int, FabricDetailsItem]:
        """
        Retrieves product details relevant to fabrics (width, grammage, shrinkage)
        from the ERP, handling pagination.

        Returns:
            A dictionary mapping product_code (int) to FabricDetailsItem objects.

        Raises:
            ErpIntegrationError: If communication with the ERP fails or the response is invalid.
        """
        all_details: Dict[int, FabricDetailsItem] = {}
        current_page = 1
        has_next = True

        logger.info("Starting ERP fabric details fetch.")

        while has_next:
            logger.debug(f"Fetching page {current_page} for fabric details...")
            try:
                payload = self._build_request_payload(current_page)
                response_data = self._make_api_request(payload)

                if not response_data or not isinstance(response_data, dict):
                    logger.warning(f"Received invalid product details response data for page {current_page}. Aborting fetch.")
                    break

                items_data = response_data.get('items', [])
                if not isinstance(items_data, list):
                     logger.warning(f"Invalid 'items' format in product details response page {current_page}. Expected list.")
                     items_data = []

                processed_count = 0
                for item_dict in items_data:
                     if isinstance(item_dict, dict):
                          details_item = FabricDetailsItem.from_product_api_item(item_dict)
                          if details_item:
                               all_details[details_item.product_code] = details_item
                               processed_count += 1
                     else:
                          logger.warning(f"Skipping non-dict item in product details response: {item_dict}")


                has_next = response_data.get('hasNext', False)
                total_pages = response_data.get('totalPages', 0)
                logger.debug(f"Fetched product details page {current_page}/{total_pages or '?'}. Processed Items: {processed_count}. HasNext: {has_next}")

                current_page += 1

                # Safety break
                if current_page > (total_pages + 5) and total_pages > 0:
                     logger.warning(f"Potential infinite loop detected in product details pagination. Stopping at page {current_page-1}.")
                     break
                if current_page > 500:
                     logger.warning(f"Reached absolute page limit (500) for product details fetch. Stopping.")
                     break

            except ErpIntegrationError as e:
                 logger.error(f"Failed to fetch page {current_page} for fabric details: {e}", exc_info=True)
                 raise e
            except Exception as e:
                 logger.error(f"Unexpected error fetching page {current_page} for fabric details: {e}", exc_info=True)
                 raise ErpIntegrationError(f"Unexpected error during fabric details fetch: {e}") from e

        logger.info(f"Finished ERP fabric details fetch. Total items retrieved: {len(all_details)}")
        return all_details

    def _make_api_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Makes the HTTP request to the ERP API, handling retries and auth."""
        attempt = 0
        while attempt <= self.max_retries:
            attempt += 1
            logger.debug(f"Attempt {attempt}/{self.max_retries + 1} to call ERP product API for details.")
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
                      logger.warning(f"ERP Product API returned 401 (Attempt {attempt}). Invalidating token and retrying.")
                      self.erp_auth_service.invalidate_token()
                      continue
                 else:
                      response_text = e.response.text[:500]
                      logger.error(f"HTTP error {status_code} from ERP product API: {e}. Response: {response_text}", exc_info=True)
                      raise ErpIntegrationError(f"ERP product API request failed with status {status_code}: {response_text}") from e

            except requests.exceptions.RequestException as e:
                 logger.error(f"Network error connecting to ERP product API: {e}", exc_info=True)
                 if attempt <= self.max_retries:
                      logger.warning(f"Retrying product API call after network error (Attempt {attempt}).")
                      continue
                 else:
                      raise ErpIntegrationError(f"Network error connecting to ERP product API after {attempt} attempts: {e}") from e

        logger.error("Exhausted retries for ERP product API request.")
        raise ErpIntegrationError("Exhausted retries trying to reach ERP product API.")


    def _build_request_payload(self, page: int) -> Dict[str, Any]:
        """Constructs the JSON payload for the product details API request (fabric specific)."""

        # Payload specifically to get fabric details (width, grammage, shrinkage)
        payload = {
            "page": page,
            "pageSize": self.page_size,
            "order": "productCode", # Order by product code
            "expand": "additionalFields", # Crucial: Expand to get the details
            "filter": {
                "branchInfo": {
                    "branchCode": self.company_code,
                    "isActive": True,
                    # Filters specific to fabrics (raw materials)
                    "isFinishedProduct": False,
                    "isRawMaterial": True,
                    "isBulkMaterial": False,
                    "isOwnProduction": False,
                },
                # Fabric-specific classifications (same as in balance/cost)
                "classifications": [
                    {"type": 4000, "codeList": ["001"]},
                    {"type": 4001, "codeList": ["001", "002", "003"]}
                ]
            },
            "option": {
                # Specify which additional fields are needed by code
                "additionalFields": [
                    {"codeList": [1, 2, 3]}  # 1=Width, 2=Grammage, 3=Shrinkage
                ],
                 # Optionally include branch info code if needed, but might not be necessary if filtering by it
                 "branchInfoCode": self.company_code,
            }
        }

        logger.debug(f"Generated ERP product details payload: {payload}")
        return payload
