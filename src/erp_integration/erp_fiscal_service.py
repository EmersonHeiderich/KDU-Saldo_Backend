# src/erp_integration/erp_fiscal_service.py
# Fetches Fiscal data (Invoices, XML, DANFE) from the TOTVS ERP API.

import requests
import base64
from typing import Optional, List, Dict, Any
from src.config import config
from src.domain.fiscal import InvoiceXmlOutDto, DanfeRequestModel, DanfeResponseModel # Domain models
from .erp_auth_service import ErpAuthService
from src.utils.logger import logger
from src.api.errors import ErpIntegrationError, ErpNotFoundError # Custom errors

# Define the specific page size limit for this endpoint
FISCAL_INVOICE_PAGE_SIZE = 100 # ERP Limit

class ErpFiscalService:
    """
    Service to interact with the ERP's Fiscal related endpoints.
    Handles fetching invoices, XML content, and DANFE generation.
    """

    def __init__(self, erp_auth_service: ErpAuthService):
        """
        Initializes the ErpFiscalService.

        Args:
            erp_auth_service: Instance of ErpAuthService for authentication.
        """
        self.erp_auth_service = erp_auth_service
        self.base_url = config.API_BASE_URL.rstrip('/')
        # Construct full URLs for endpoints
        # Use updated config keys
        self.invoices_search_url = f"{self.base_url}{config.FISCAL_INVOICES_ENDPOINT}"
        self.xml_content_url_template = f"{self.base_url}{config.FISCAL_XML_ENDPOINT}/{{accessKey}}"
        self.danfe_search_url = f"{self.base_url}{config.FISCAL_DANFE_ENDPOINT}"
        self.max_retries = config.MAX_RETRIES
        self.company_code = config.COMPANY_CODE
        logger.info("ErpFiscalService initialized.")


    def _make_request(self, url: str, method: str = "POST", params: Optional[Dict] = None, json_payload: Optional[Dict] = None, stream: bool = False) -> requests.Response:
        """
        Internal helper to make requests to the Fiscal API, handling auth and retries.
        Returns the raw Response object.

        Args:
            url: The full URL for the API endpoint.
            method: HTTP method ("GET" or "POST").
            params: Dictionary of query parameters for GET requests.
            json_payload: Dictionary payload for POST requests.
            stream: Whether to stream the response (for large files like PDF).

        Returns:
            The raw requests.Response object.

        Raises:
            ErpIntegrationError: If the request fails after retries or returns unexpected status.
            ErpNotFoundError: If the API returns a 404 status.
        """
        attempt = 0
        last_exception: Optional[Exception] = None
        response: Optional[requests.Response] = None # Define response outside try for wider scope

        while attempt <= self.max_retries:
            attempt += 1
            logger.debug(f"Attempt {attempt}/{self.max_retries + 1} to call ERP Fiscal API: {method} {url}")
            response = None # Reset response for each attempt
            status_code = None # Reset status code
            response_text_snippet = "N/A" # Reset snippet

            try:
                token = self.erp_auth_service.get_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json" if not stream else "*/*" # Accept JSON or anything if streaming
                    # Add company code headers if needed
                    # "CompanyCode": str(self.company_code),
                    # "BranchCode": str(self.company_code),
                }

                timeout = 60 if stream else 30 # Longer timeout for potential PDF generation

                if method.upper() == "POST":
                    response = requests.post(url, json=json_payload, headers=headers, timeout=timeout, stream=stream)
                elif method.upper() == "GET":
                    response = requests.get(url, params=params, headers=headers, timeout=timeout, stream=stream)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # --- Start Enhanced Error Handling ---
                status_code = response.status_code # Get status code immediately
                try:
                    # Try reading text, limit length to avoid huge logs
                    response_text_snippet = response.text[:1000] if response.text else "(Empty Body)"
                except Exception as read_err:
                    response_text_snippet = f"(Error reading response body: {read_err})"

                logger.debug(f"ERP Response Status: {status_code}, Body Snippet: {response_text_snippet}")

                # Check for 404 first
                if status_code == 404:
                     logger.warning(f"ERP Fiscal API returned 404 Not Found for {method} {url}. Params/Payload: {params or json_payload}")
                     raise ErpNotFoundError(f"Resource not found in ERP for request {method} {url}.")

                # Check for 401 Unauthorized (token expired?)
                if status_code == 401 and attempt <= self.max_retries:
                     logger.warning(f"ERP Fiscal API returned 401 (Attempt {attempt}). Invalidating token and retrying.")
                     self.erp_auth_service.invalidate_token()
                     last_exception = requests.exceptions.HTTPError(f"401 Client Error: Unauthorized for url: {url}", response=response) # Store original exception
                     continue # Retry

                # Raise other HTTP errors (>= 400, excluding 404/401 handled above)
                response.raise_for_status()
                # --- End Enhanced Error Handling ---

                # If successful (no exception raised), return the response object
                return response

            except requests.exceptions.HTTPError as e:
                 # This catches errors raised by raise_for_status (excluding 404/401 retry)
                 logger.error(f"HTTP error {status_code} from ERP Fiscal API ({method} {url}): {e}. Response: {response_text_snippet}", exc_info=False) # Don't need full stack trace again
                 last_exception = ErpIntegrationError(f"ERP Fiscal API request failed with status {status_code}: {response_text_snippet}")
                 # Break loop for non-retryable HTTP errors (like 400 Bad Request)
                 break

            except requests.exceptions.RequestException as e:
                 # Network errors
                 logger.error(f"Network error connecting to ERP Fiscal API ({method} {url}): {e}", exc_info=True)
                 last_exception = ErpIntegrationError(f"Network error connecting to ERP Fiscal API: {e}")
                 if attempt <= self.max_retries:
                      logger.warning(f"Retrying Fiscal API call after network error (Attempt {attempt}).")
                      # Optional: Add delay? time.sleep(0.5 * attempt)
                      continue # Retry on network errors
                 else:
                      break # Exhausted retries

            except ErpNotFoundError as e:
                 # Catch and re-raise specific 404 error immediately
                 last_exception = e
                 raise e

            except Exception as e: # Catch potential unexpected errors
                 logger.error(f"Unexpected error during ERP Fiscal API request ({method} {url}): {e}", exc_info=True)
                 error_msg = f"Unexpected error during ERP Fiscal API request: {e}"
                 if response:
                      error_msg += f" | Response Status: {status_code}, Response Snippet: {response_text_snippet}"
                 last_exception = ErpIntegrationError(error_msg)
                 break # Don't retry unexpected errors

        # If loop finishes due to exhausted retries or non-retryable error
        log_message = f"Failed ERP Fiscal API request after {attempt} attempts: {method} {url}. LastError: {last_exception}"
        logger.error(log_message)
        # Raise the captured exception, providing more context
        if isinstance(last_exception, (ErpIntegrationError, ErpNotFoundError)):
            raise last_exception
        elif isinstance(last_exception, Exception):
            raise ErpIntegrationError(log_message) from last_exception
        else:
             raise ErpIntegrationError(f"Exhausted retries or failed for ERP Fiscal API request: {method} {url}")


    # --- Modified search_invoices to accept payload and return raw dict ---
    def search_invoices(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Searches for invoices in the ERP using the provided payload (single page).

        Args:
            payload: The request body dictionary matching InvoiceSearchInDto, including
                     pagination ('page', 'pageSize').

        Returns:
            The raw response dictionary from the ERP for the requested page.

        Raises:
            ErpIntegrationError, ErpNotFoundError.
        """
        logger.debug(f"Searching ERP invoices (single page) with payload: {payload}")
        try:
            response = self._make_request(self.invoices_search_url, method="POST", json_payload=payload)
            # Decode JSON response
            try:
                response_data = response.json()
            except requests.exceptions.JSONDecodeError as json_err:
                logger.error(f"Failed to decode JSON response for invoice search. Status: {response.status_code}, Error: {json_err}. Response Text: {response.text[:500]}")
                raise ErpIntegrationError(f"Received non-JSON response from ERP invoice search: {json_err}") from json_err

            if not isinstance(response_data, dict):
                 logger.error(f"Invalid response type received from ERP invoice search: {type(response_data)}")
                 raise ErpIntegrationError("Invalid response structure received from ERP invoice search.")

            logger.debug(f"ERP invoice search successful for page {payload.get('page', '?')}.")
            return response_data # Return the full dictionary

        except (ErpNotFoundError, ErpIntegrationError) as e:
             # Logged in _make_request, just re-raise
             raise e
        except Exception as e:
             logger.error(f"Unexpected error in search_invoices ERP call: {e}", exc_info=True)
             raise ErpIntegrationError(f"Unexpected error during ERP invoice search: {e}") from e


    def get_xml_content(self, access_key: str) -> InvoiceXmlOutDto:
        """
        Gets the XML content (Base64) for a given invoice access key.

        Args:
            access_key: The invoice's 44-digit access key.

        Returns:
            An InvoiceXmlOutDto object containing the XML data.

        Raises:
            ErpIntegrationError, ErpNotFoundError.
        """
        logger.debug(f"Fetching ERP XML content for access key: ...{access_key[-6:]}")
        url = self.xml_content_url_template.format(accessKey=access_key)
        try:
            response = self._make_request(url, method="GET")
            try:
                 response_data = response.json()
            except requests.exceptions.JSONDecodeError as json_err:
                 logger.error(f"Failed to decode JSON response for XML content key ...{access_key[-6:]}. Status: {response.status_code}, Error: {json_err}. Response Text: {response.text[:500]}")
                 raise ErpIntegrationError(f"Received non-JSON response from ERP XML content endpoint: {json_err}") from json_err

            xml_dto = InvoiceXmlOutDto.from_dict(response_data)
            if not xml_dto or not xml_dto.main_invoice_xml:
                logger.error(f"Failed to parse XML content response or mainInvoiceXml missing. Data: {response_data}")
                # If the API call was successful (2xx) but content is invalid/missing, treat as integration error.
                # NotFoundError is raised by _make_request for 404 status.
                raise ErpIntegrationError(f"Invalid or missing XML content received from ERP for access key ...{access_key[-6:]}.")

            logger.info(f"Successfully fetched XML content for access key: ...{access_key[-6:]}")
            return xml_dto
        except (ErpNotFoundError, ErpIntegrationError) as e:
            raise e # Re-raise specific errors
        except Exception as e:
            logger.error(f"Unexpected error fetching XML content for access key ...{access_key[-6:]}: {e}", exc_info=True)
            raise ErpIntegrationError(f"Unexpected error getting XML content: {e}") from e


    def get_danfe_from_xml(self, xml_base64: str) -> DanfeResponseModel:
        """
        Requests the DANFE PDF (Base64) using the invoice XML (Base64).

        Args:
            xml_base64: The Base64 encoded invoice XML (mainInvoiceXml).

        Returns:
            A DanfeResponseModel object containing the DANFE PDF Base64.

        Raises:
            ErpIntegrationError, ErpNotFoundError.
        """
        logger.debug(f"Requesting DANFE from ERP using provided XML (length: {len(xml_base64)})...")
        request_model = DanfeRequestModel(main_invoice_xml=xml_base64)
        payload = request_model.to_dict()
        try:
            response = self._make_request(self.danfe_search_url, method="POST", json_payload=payload)
            try:
                 response_data = response.json()
            except requests.exceptions.JSONDecodeError as json_err:
                 logger.error(f"Failed to decode JSON response for DANFE generation. Status: {response.status_code}, Error: {json_err}. Response Text: {response.text[:500]}")
                 raise ErpIntegrationError(f"Received non-JSON response from ERP DANFE generation endpoint: {json_err}") from json_err

            danfe_dto = DanfeResponseModel.from_dict(response_data)
            if not danfe_dto or not danfe_dto.danfe_pdf_base64:
                logger.error(f"Failed to parse DANFE response or danfePdfBase64 missing. Data: {response_data}")
                raise ErpIntegrationError("Invalid or missing DANFE PDF received from ERP.")

            logger.info("Successfully received DANFE PDF (base64) from ERP.")
            return danfe_dto
        except (ErpNotFoundError, ErpIntegrationError) as e:
            raise e # Re-raise specific errors
        except Exception as e:
            logger.error(f"Unexpected error generating DANFE PDF: {e}", exc_info=True)
            raise ErpIntegrationError(f"Unexpected error generating DANFE PDF: {e}") from e