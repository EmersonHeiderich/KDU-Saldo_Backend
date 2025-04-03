# src/erp_integration/erp_fiscal_service.py
# Fetches Fiscal data (Invoices) raw data from the TOTVS ERP API, focusing on sync needs.

import requests
from typing import Optional, List, Dict, Any
from src.config import config
# Não precisa mais de modelos de domínio aqui, retorna dicionário bruto
from .erp_auth_service import ErpAuthService
from src.utils.logger import logger
from src.api.errors import ErpIntegrationError, ErpNotFoundError # Custom errors

# Define the specific page size limit for this endpoint
ERP_FISCAL_PAGE_SIZE = 100 # ERP Limit

class ErpFiscalService:
    """
    Service to interact with the ERP's Fiscal endpoints, primarily focused on
    fetching raw invoice data for synchronization purposes.
    Handles direct communication, authentication, and basic error handling.
    Pagination logic is handled by the caller (e.g., FiscalSyncService).
    """

    def __init__(self, erp_auth_service: ErpAuthService):
        """
        Initializes the ErpFiscalService.

        Args:
            erp_auth_service: Instance of ErpAuthService for authentication.
        """
        self.erp_auth_service = erp_auth_service
        self.base_url = config.API_BASE_URL.rstrip('/')
        # Somente a URL de busca é necessária aqui para sync
        self.invoices_search_url = f"{self.base_url}{config.FISCAL_INVOICES_ENDPOINT}"
        self.xml_content_url_template = f"{self.base_url}{config.FISCAL_XML_ENDPOINT}/{{accessKey}}"
        self.danfe_search_url = f"{self.base_url}{config.FISCAL_DANFE_ENDPOINT}"
        self.max_retries = config.MAX_RETRIES
        self.company_code = config.COMPANY_CODE # Pode ser necessário para headers/filtros default
        logger.info("ErpFiscalService initialized (Refactored for Raw Data Fetch).")


    def _make_request(self, url: str, method: str = "POST", params: Optional[Dict] = None, json_payload: Optional[Dict] = None, stream: bool = False) -> requests.Response:
        """
        Internal helper to make requests to the Fiscal API, handling auth and retries.
        Returns the raw Response object.
        (This method remains largely the same as before, focusing on robust request execution)
        """
        attempt = 0
        last_exception: Optional[Exception] = None
        response: Optional[requests.Response] = None

        while attempt <= self.max_retries:
            attempt += 1
            logger.debug(f"Attempt {attempt}/{self.max_retries + 1} to call ERP Fiscal API: {method} {url}")
            response = None
            status_code = None
            response_text_snippet = "N/A"

            try:
                token = self.erp_auth_service.get_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json" if not stream else "*/*"
                    # Adicionar headers de empresa se a API TOTVS exigir
                    # "CompanyCode": str(self.company_code),
                    #"BranchCode": str(self.company_code),
                }

                timeout = 60 if stream else 45 # Increased timeout slightly

                if method.upper() == "POST":
                    response = requests.post(url, json=json_payload, headers=headers, timeout=timeout, stream=stream)
                elif method.upper() == "GET":
                    response = requests.get(url, params=params, headers=headers, timeout=timeout, stream=stream)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                status_code = response.status_code
                try:
                    response_text_snippet = response.text[:1000] if response.text else "(Empty Body)"
                except Exception as read_err:
                    response_text_snippet = f"(Error reading response body: {read_err})"

                logger.debug(f"ERP Response Status: {status_code}, Body Snippet: {response_text_snippet}")

                if status_code == 404:
                     logger.warning(f"ERP Fiscal API returned 404 Not Found for {method} {url}. Params/Payload: {params or json_payload}")
                     raise ErpNotFoundError(f"Resource not found in ERP for request {method} {url}.")

                if status_code == 401 and attempt <= self.max_retries:
                     logger.warning(f"ERP Fiscal API returned 401 (Attempt {attempt}). Invalidating token and retrying.")
                     self.erp_auth_service.invalidate_token()
                     last_exception = requests.exceptions.HTTPError(f"401 Client Error: Unauthorized for url: {url}", response=response)
                     continue # Retry

                # Check specific error patterns if needed (e.g., 400 with specific messages)
                if status_code == 400:
                    error_detail = response_text_snippet # Default
                    try:
                        error_json = response.json()
                        if isinstance(error_json, dict):
                           msg = error_json.get('message') or error_json.get('Message')
                           det_msg = error_json.get('detailedMessage') or error_json.get('DetailedMessage')
                           error_detail = f"{msg or 'Bad Request'} ({det_msg or response_text_snippet})"
                    except requests.exceptions.JSONDecodeError:
                        pass # Stick with the text snippet
                    logger.warning(f"ERP Fiscal API returned 400 Bad Request for {method} {url}. Detail: {error_detail}")
                    # Raise specific error that sync service might handle differently
                    raise ErpIntegrationError(f"ERP API returned Bad Request (400): {error_detail}", status_code=400)


                response.raise_for_status() # Raise other HTTP errors

                # Success
                return response

            except requests.exceptions.HTTPError as e:
                 logger.error(f"HTTP error {status_code} from ERP Fiscal API ({method} {url}): {e}. Response: {response_text_snippet}", exc_info=False)
                 last_exception = ErpIntegrationError(f"ERP Fiscal API request failed with status {status_code}: {response_text_snippet}", status_code=status_code)
                 break

            except requests.exceptions.RequestException as e:
                 logger.error(f"Network error connecting to ERP Fiscal API ({method} {url}): {e}", exc_info=True)
                 last_exception = ErpIntegrationError(f"Network error connecting to ERP Fiscal API: {e}")
                 if attempt <= self.max_retries:
                      logger.warning(f"Retrying Fiscal API call after network error (Attempt {attempt}).")
                      continue # Retry
                 else:
                      break # Exhausted retries

            except ErpNotFoundError as e:
                 last_exception = e
                 raise e # Re-raise specific 404

            except ErpIntegrationError as e: # Catch 400 error raised above
                 last_exception = e
                 raise e # Re-raise

            except Exception as e:
                 logger.error(f"Unexpected error during ERP Fiscal API request ({method} {url}): {e}", exc_info=True)
                 error_msg = f"Unexpected error during ERP Fiscal API request: {e}"
                 if response:
                      error_msg += f" | Response Status: {status_code}, Response Snippet: {response_text_snippet}"
                 last_exception = ErpIntegrationError(error_msg)
                 break # Don't retry unexpected errors

        # If loop finishes
        log_message = f"Failed ERP Fiscal API request after {attempt} attempts: {method} {url}. LastError: {last_exception}"
        logger.error(log_message)
        if isinstance(last_exception, (ErpIntegrationError, ErpNotFoundError)):
            raise last_exception
        elif isinstance(last_exception, Exception):
            raise ErpIntegrationError(log_message) from last_exception
        else:
             raise ErpIntegrationError(f"Exhausted retries or failed for ERP Fiscal API request: {method} {url}")


    # --- Fetch Raw Data for a SINGLE Page ---
    def fetch_invoices_page(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetches a single page of raw invoice data from the ERP based on the payload.
        Handles JSON decoding and basic response validation.

        Args:
            payload: The full request payload for the ERP's /invoices/search endpoint,
                     including filter, expand, order, page, and pageSize.

        Returns:
            The raw JSON response dictionary from the ERP for the requested page.

        Raises:
            ErpIntegrationError: If the API call fails, returns non-JSON, or invalid structure.
            ErpNotFoundError: If the API returns 404 (though less likely for search).
        """
        logger.debug(f"Fetching raw ERP invoices page {payload.get('page')} with payload.")
        # Payload details are not logged here for brevity, but could be if needed
        # logger.debug(f"Payload: {payload}")

        try:
            response = self._make_request(self.invoices_search_url, method="POST", json_payload=payload)

            # Decode JSON response
            try:
                response_data = response.json()
            except requests.exceptions.JSONDecodeError as json_err:
                logger.error(f"Failed to decode JSON response for invoice fetch page {payload.get('page')}. Status: {response.status_code}, Error: {json_err}. Response Text: {response.text[:500]}")
                raise ErpIntegrationError(f"Received non-JSON response from ERP invoice search: {json_err}") from json_err

            # Basic validation of the expected structure
            if not isinstance(response_data, dict) or 'items' not in response_data or 'hasNext' not in response_data:
                logger.error(f"Invalid response structure received from ERP invoice search: {response_data}")
                raise ErpIntegrationError("Invalid response structure received from ERP invoice search.")

            logger.debug(f"Successfully fetched raw data for page {payload.get('page')}. Items: {len(response_data.get('items', []))}, HasNext: {response_data.get('hasNext')}")
            return response_data # Return the full raw dictionary

        except (ErpNotFoundError, ErpIntegrationError) as e:
             # Logged in _make_request, just re-raise
             raise e
        except Exception as e:
             logger.error(f"Unexpected error in fetch_invoices_page ERP call: {e}", exc_info=True)
             raise ErpIntegrationError(f"Unexpected error during ERP raw invoice fetch: {e}") from e

    # --- Methods for DANFE/XML (remain mostly the same as they fetch specific items) ---
    def get_xml_content_raw(self, access_key: str) -> Dict[str, Any]:
        """Gets the raw XML content response for a given access key."""
        logger.debug(f"Fetching raw ERP XML content for access key: ...{access_key[-6:]}")
        url = self.xml_content_url_template.format(accessKey=access_key)
        try:
            response = self._make_request(url, method="GET")
            try:
                 return response.json() # Return raw dict
            except requests.exceptions.JSONDecodeError as json_err:
                 logger.error(f"Failed to decode JSON for XML key ...{access_key[-6:]}. Status: {response.status_code}, Text: {response.text[:500]}")
                 raise ErpIntegrationError(f"Received non-JSON from ERP XML content: {json_err}") from json_err
        except (ErpNotFoundError, ErpIntegrationError) as e:
            raise e
        except Exception as e:
            logger.error(f"Unexpected error fetching raw XML for key ...{access_key[-6:]}: {e}", exc_info=True)
            raise ErpIntegrationError(f"Unexpected error getting raw XML content: {e}") from e

    def get_danfe_from_xml_raw(self, xml_base64: str) -> Dict[str, Any]:
        """Requests the DANFE PDF raw response using the invoice XML."""
        logger.debug(f"Requesting raw DANFE response from ERP using provided XML...")
        # Create payload directly here or use a simple dict
        payload = {"mainInvoiceXml": xml_base64} # Add nfeDocumentType if needed
        try:
            response = self._make_request(self.danfe_search_url, method="POST", json_payload=payload)
            try:
                 return response.json() # Return raw dict
            except requests.exceptions.JSONDecodeError as json_err:
                 logger.error(f"Failed to decode JSON response for DANFE generation. Status: {response.status_code}, Text: {response.text[:500]}")
                 raise ErpIntegrationError(f"Received non-JSON response from ERP DANFE generation: {json_err}") from json_err
        except (ErpNotFoundError, ErpIntegrationError) as e:
            raise e
        except Exception as e:
            logger.error(f"Unexpected error generating raw DANFE response: {e}", exc_info=True)
            raise ErpIntegrationError(f"Unexpected error generating raw DANFE response: {e}") from e