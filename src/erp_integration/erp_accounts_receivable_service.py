# src/erp_integration/erp_accounts_receivable_service.py
# Fetches Accounts Receivable data from the TOTVS ERP API.

import requests
from typing import Optional, Dict, Any
from src.config import config
# Import domain models if needed for type hints, but methods return raw dicts
from .erp_auth_service import ErpAuthService
from src.utils.logger import logger
from src.api.errors import ErpIntegrationError, ErpNotFoundError

class ErpAccountsReceivableService:
    """
    Service to interact with the ERP's Accounts Receivable endpoints.
    """

    def __init__(self, erp_auth_service: ErpAuthService):
        """
        Initializes the ErpAccountsReceivableService.

        Args:
            erp_auth_service: Instance of ErpAuthService for authentication.
        """
        self.erp_auth_service = erp_auth_service
        self.base_url = config.API_BASE_URL.rstrip('/')
        self.documents_url = f"{self.base_url}{config.ACCOUNTS_RECEIVABLE_DOCUMENTS_ENDPOINT}"
        self.bank_slip_url = f"{self.base_url}{config.ACCOUNTS_RECEIVABLE_BANKSLIP_ENDPOINT}"
        # self.payment_link_url = f"{self.base_url}{config.ACCOUNTS_RECEIVABLE_PAYMENTLINK_ENDPOINT}" # If needed later
        self.max_retries = config.MAX_RETRIES
        self.company_code = config.COMPANY_CODE
        logger.info("ErpAccountsReceivableService initialized.")

    def _make_request(self, url: str, method: str = "POST", params: Optional[Dict] = None, json_payload: Optional[Dict] = None) -> Dict[str, Any]:
        """Internal helper to make requests, handling auth and retries."""
        # This can be copied/adapted from ErpPersonService or ErpFiscalService
        # Ensure it handles POST correctly and specific error cases for this API
        attempt = 0
        last_exception: Optional[Exception] = None

        while attempt <= self.max_retries:
            attempt += 1
            logger.debug(f"Attempt {attempt}/{self.max_retries + 1} to call ERP AR API: {method} {url}")
            response = None
            status_code = None
            response_text_snippet = "N/A"

            try:
                token = self.erp_auth_service.get_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }

                timeout = 45 # Slightly longer timeout might be needed

                if method.upper() == "POST":
                    response = requests.post(url, json=json_payload, headers=headers, timeout=timeout)
                elif method.upper() == "GET":
                    response = requests.get(url, params=params, headers=headers, timeout=timeout)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                status_code = response.status_code
                try:
                    response_text_snippet = response.text[:1000] if response.text else "(Empty Body)"
                except Exception as read_err:
                    response_text_snippet = f"(Error reading response body: {read_err})"

                logger.debug(f"ERP AR Response Status: {status_code}, Body Snippet: {response_text_snippet}")

                # Check specific AR error patterns if necessary (e.g., 400 with DomainNotificationMessage)
                # The Swagger shows 400 for Bad Request, 200 for Success. No explicit 404 mentioned for search/boleto.
                # If a 400 contains useful info in DomainNotificationMessage, parse it?
                if status_code == 400:
                    error_detail = response_text_snippet # Default error detail
                    try:
                        error_json = response.json()
                        if isinstance(error_json, dict):
                           msg = error_json.get('message') or error_json.get('Message') # Check common keys
                           det_msg = error_json.get('detailedMessage') or error_json.get('DetailedMessage')
                           error_detail = f"{msg or 'Bad Request'} ({det_msg or response_text_snippet})"
                    except requests.exceptions.JSONDecodeError:
                        pass # Stick with the text snippet
                    logger.warning(f"ERP AR API returned 400 Bad Request for {method} {url}. Detail: {error_detail}")
                    # Map 400 to ErpIntegrationError for now, service layer might interpret further
                    raise ErpIntegrationError(f"ERP AR API returned Bad Request (400): {error_detail}")


                if status_code == 401 and attempt <= self.max_retries:
                     logger.warning(f"ERP AR API returned 401 (Attempt {attempt}). Invalidating token and retrying.")
                     self.erp_auth_service.invalidate_token()
                     last_exception = requests.exceptions.HTTPError(f"401 Client Error: Unauthorized for url: {url}", response=response)
                     continue # Retry

                # Raise other HTTP errors (>= 400, excluding 400/401 handled above)
                response.raise_for_status()

                # Handle cases where API returns 200 but empty body or non-JSON
                try:
                     resp_json = response.json()
                     if not resp_json and method.upper() != "GET": # Allow empty response for GET maybe, but not POST results
                          logger.warning(f"Received empty successful response (2xx) from ERP AR API: {method} {url}")
                          # Treat as error for POST requests expecting data
                          raise ErpIntegrationError(f"Received empty successful response from ERP AR API: {method} {url}")
                     return resp_json
                except requests.exceptions.JSONDecodeError as json_err:
                     logger.error(f"Failed to decode JSON response from {method} {url}. Status: {status_code}, Error: {json_err}. Response: {response_text_snippet}")
                     raise ErpIntegrationError(f"Received non-JSON response from ERP AR API: {json_err}") from json_err

            except requests.exceptions.HTTPError as e:
                 # Catches errors raised by raise_for_status (excluding 400/401 retry)
                 logger.error(f"HTTP error {status_code} from ERP AR API ({method} {url}): {e}. Response: {response_text_snippet}", exc_info=False)
                 last_exception = ErpIntegrationError(f"ERP AR API request failed with status {status_code}: {response_text_snippet}")
                 break # Break loop for non-retryable HTTP errors

            except requests.exceptions.RequestException as e:
                 logger.error(f"Network error connecting to ERP AR API ({method} {url}): {e}", exc_info=True)
                 last_exception = ErpIntegrationError(f"Network error connecting to ERP AR API: {e}")
                 if attempt <= self.max_retries:
                      logger.warning(f"Retrying AR API call after network error (Attempt {attempt}).")
                      continue # Retry on network errors
                 else:
                      break # Exhausted retries

            except ErpIntegrationError as e: # Catch 400 errors raised above
                 last_exception = e
                 raise e # Re-raise immediately

            except Exception as e:
                 logger.error(f"Unexpected error during ERP AR API request ({method} {url}): {e}", exc_info=True)
                 error_msg = f"Unexpected error during ERP AR API request: {e}"
                 if response:
                      error_msg += f" | Response Status: {status_code}, Response Snippet: {response_text_snippet}"
                 last_exception = ErpIntegrationError(error_msg)
                 break

        # If loop finishes due to exhausted retries or non-retryable error
        log_message = f"Failed ERP AR API request after {attempt} attempts: {method} {url}. LastError: {last_exception}"
        logger.error(log_message)
        if isinstance(last_exception, ErpIntegrationError):
            raise last_exception
        elif isinstance(last_exception, Exception):
            raise ErpIntegrationError(log_message) from last_exception
        else:
             raise ErpIntegrationError(f"Exhausted retries or failed for ERP AR API request: {method} {url}")


    def search_documents(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Calls the ERP endpoint to search for accounts receivable documents."""
        logger.debug(f"Calling ERP AR documents search with payload: {payload}")
        # Note: _make_request returns the parsed dictionary directly
        return self._make_request(self.documents_url, method="POST", json_payload=payload)

    def get_bank_slip(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Calls the ERP endpoint to generate a bank slip (boleto)."""
        logger.debug(f"Calling ERP AR bank slip generation with payload: {payload}")
        # Note: _make_request returns the parsed dictionary directly
        return self._make_request(self.bank_slip_url, method="POST", json_payload=payload)