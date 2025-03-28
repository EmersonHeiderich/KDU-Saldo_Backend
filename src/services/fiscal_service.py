# src/services/fiscal_service.py
# Contains business logic for the Fiscal module.

import base64
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from src.erp_integration.erp_fiscal_service import ErpFiscalService, FISCAL_INVOICE_PAGE_SIZE # Import constant
# Use the FormattedInvoiceListItem for the final API response structure
from src.domain.fiscal import FormattedInvoiceListItem, InvoiceXmlOutDto, DanfeResponseModel
from src.utils.logger import logger
from src.api.errors import ErpIntegrationError, ServiceError, NotFoundError, ValidationError
from src.config import config # Import config

class FiscalService:
    """
    Service layer for handling fiscal operations like searching invoices and generating DANFE.
    """
    def __init__(self, erp_fiscal_service: ErpFiscalService):
        self.erp_fiscal_service = erp_fiscal_service
        logger.info("FiscalService initialized.")

    def _parse_list_filter(self, filter_value: Optional[str]) -> Optional[List[Any]]:
        """Parses comma-separated string into a list of strings."""
        if not filter_value:
            return None
        items = [item.strip() for item in filter_value.split(',') if item.strip()]
        return items if items else None

    def _parse_numeric_list_filter(self, filter_value: Optional[str]) -> Optional[List[int]]:
        """Parses comma-separated string into a list of integers."""
        items_str = self._parse_list_filter(filter_value)
        if not items_str:
            return None
        try:
            # Ensure all items are digits before converting
            if not all(item.isdigit() for item in items_str):
                 raise ValueError("Non-numeric value found in list.")
            return [int(item) for item in items_str]
        except ValueError as e:
            logger.warning(f"Invalid numeric list format: '{filter_value}'. Error: {e}")
            raise ValidationError(f"Invalid numeric list format: '{filter_value}'. Must be comma-separated numbers.")

    def _parse_date_filter(self, date_str: Optional[str]) -> Optional[str]:
        """Validates and returns date string (basic ISO validation)."""
        if not date_str:
            return None
        try:
            # Attempt to parse to ensure it's a valid ISO-like date/datetime
            datetime.fromisoformat(date_str.replace('Z', '+00:00')) # Handle Z suffix
            # Return the original string as ERP might expect it precisely
            return date_str
        except ValueError:
            logger.warning(f"Invalid date format received: '{date_str}'")
            raise ValidationError(f"Invalid date format: '{date_str}'. Use ISO 8601 format (e.g., YYYY-MM-DD or YYYY-MM-DDTHH:mm:ss).")

    def _parse_invoice_number_filter(self, filter_value: Optional[str]) -> Tuple[Optional[List[int]], Optional[int], Optional[int]]:
        """Parses invoice number filter (list or range)."""
        invoice_code_list: Optional[List[int]] = None
        start_invoice_code: Optional[int] = None
        end_invoice_code: Optional[int] = None

        if not filter_value:
            return invoice_code_list, start_invoice_code, end_invoice_code

        filter_value = str(filter_value).strip() # Ensure string

        if '-' in filter_value and ',' not in filter_value:
            # Potential range
            parts = filter_value.split('-')
            if len(parts) == 2:
                try:
                    start_str, end_str = parts[0].strip(), parts[1].strip()
                    if not start_str.isdigit() or not end_str.isdigit():
                         raise ValueError("Range parts must be numeric")
                    start = int(start_str)
                    end = int(end_str)
                    if start <= end:
                        start_invoice_code = start
                        end_invoice_code = end
                    else:
                        logger.warning(f"Invalid invoice range: start ({start}) > end ({end})")
                        raise ValidationError("Start invoice code must be less than or equal to end invoice code in range.")
                except ValueError:
                    logger.warning(f"Invalid characters in invoice range: '{filter_value}'")
                    raise ValidationError("Invalid invoice number range format. Use NUM-NUM.")
            else:
                raise ValidationError("Invalid invoice number range format. Use NUM-NUM.")
        else:
             # Try parsing as list (handles single number too if no comma)
             try:
                  # This handles "123" and "123,456"
                  invoice_code_list = self._parse_numeric_list_filter(filter_value)
                  # If parsing succeeded but resulted in empty list (e.g. input was just ",") raise error
                  if not invoice_code_list and filter_value:
                       raise ValidationError(f"Invalid invoice number list/value: '{filter_value}'.")
             except ValidationError: # Catch error from _parse_numeric_list_filter
                  raise # Re-raise the specific validation error
             except Exception as e: # Catch any other unexpected parsing error
                  logger.error(f"Unexpected error parsing invoice numbers '{filter_value}': {e}", exc_info=True)
                  raise ValidationError(f"Could not parse invoice numbers: '{filter_value}'.")


        return invoice_code_list, start_invoice_code, end_invoice_code

    def search_invoices(self, filters: Dict[str, Any], page: int = 1, page_size: int = config.FISCAL_PAGE_SIZE) -> Dict[str, Any]:
        """
        Searches for invoices based on filters for a specific page and formats the results.

        Args:
            filters: Dictionary containing user-provided filters.
                     Keys match API request query params (e.g., 'customer_code', 'invoice_number').
            page: Page number requested.
            page_size: Number of items per page.

        Returns:
            A dictionary containing the paginated list of formatted invoices and pagination info.
            {
                "items": List[Dict],
                "page": int,
                "pageSize": int,
                "totalItems": int,
                "totalPages": int
            }

        Raises:
            ValidationError: If filters are invalid.
            ServiceError: If an error occurs during ERP communication or processing.
        """
        logger.info(f"Searching invoices with filters: {filters}, Page: {page}, PageSize: {page_size}")

        # Validate page size against ERP limit
        if page_size > FISCAL_INVOICE_PAGE_SIZE:
             logger.warning(f"Requested pageSize {page_size} exceeds limit {FISCAL_INVOICE_PAGE_SIZE}. Clamping.")
             page_size = FISCAL_INVOICE_PAGE_SIZE
        elif page_size < 1:
             page_size = config.FISCAL_PAGE_SIZE # Use default if invalid

        erp_filter: Dict[str, Any] = {
            # Mandatory filters - Check if these Enum values are correct for TOTVS
            "branchCodeList": [config.COMPANY_CODE],
            "documentTypeCodeList": [55], # NF-e
            "operationType": "S", # Saida
            "origin": "Own", # Propria - Check if "Own" string or an Enum int is needed
        }

        # --- Apply User Filters ---
        try:
            person_code_list = self._parse_numeric_list_filter(filters.get('customer_code'))
            if person_code_list:
                erp_filter["personCodeList"] = person_code_list

            person_cpf_cnpj_list = self._parse_list_filter(filters.get('customer_cpf_cnpj'))
            # TODO: Validate CPF/CNPJ format if necessary
            if person_cpf_cnpj_list:
                erp_filter["personCpfCnpjList"] = person_cpf_cnpj_list

            invoice_code_list, start_invoice, end_invoice = self._parse_invoice_number_filter(filters.get('invoice_number'))
            if invoice_code_list:
                 erp_filter["invoiceCodeList"] = invoice_code_list
            if start_invoice is not None:
                 erp_filter["startInvoiceCode"] = start_invoice
            if end_invoice is not None:
                 erp_filter["endInvoiceCode"] = end_invoice

            start_issue_date = self._parse_date_filter(filters.get('start_date'))
            if start_issue_date:
                 erp_filter["startIssueDate"] = start_issue_date # Assuming ERP accepts ISO string

            end_issue_date = self._parse_date_filter(filters.get('end_date'))
            if end_issue_date:
                 erp_filter["endIssueDate"] = end_issue_date # Assuming ERP accepts ISO string

            # Status filter - needs mapping from user input to ERP enum values
            status_filter = self._parse_list_filter(filters.get('status'))
            if status_filter:
                 # Map user-friendly status names to ERP ElectronicInvoiceStatusType enum values
                 # These MUST match the exact strings the ERP expects. Verify casing.
                 status_map = {
                     "authorized": "Authorized",
                     "canceled": "Canceled",
                     "denied": "Denied",
                     "sent": "Sent", # Assuming 'Sent' exists
                     "generated": "Generated", # Assuming 'Generated' exists
                     "rejected": "Rejected", # Assuming 'Rejected' exists
                     "pending": "Pending" # Added based on swagger example
                     # Add other potential mappings based on swagger/ERP docs
                 }
                 erp_statuses = []
                 invalid_statuses = []
                 for s in status_filter:
                      mapped = status_map.get(s.lower())
                      if mapped:
                           erp_statuses.append(mapped)
                      else:
                           invalid_statuses.append(s)

                 if invalid_statuses:
                      logger.warning(f"Ignoring invalid status values: {invalid_statuses}")
                      # Optionally raise ValidationError if strict matching is required
                      # raise ValidationError(f"Invalid status value(s) provided: {invalid_statuses}. Valid statuses are case-insensitive versions of: {list(status_map.keys())}")

                 if erp_statuses:
                      erp_filter["electronicInvoiceStatusList"] = erp_statuses
                 elif status_filter: # Original filter had values, but none were valid
                      raise ValidationError(f"No valid status values provided. Valid options (case-insensitive): {list(status_map.keys())}")

        except ValidationError as ve:
             logger.warning(f"Filter validation failed: {ve}")
             raise # Re-raise validation errors


        # --- Prepare full ERP payload ---
        payload = {
            "filter": erp_filter,
            "expand": "shippingCompany, salesOrder, person, eletronic", # Include necessary expands
            "order": "-invoiceSequence", # Order by newest first
            "page": page,
            "pageSize": page_size
        }

        try:
            logger.debug(f"Calling ERP search_invoices with payload: {payload}")
            # Call ERP service for ONE specific page
            erp_response = self.erp_fiscal_service.search_invoices(payload) # Pass the whole payload

            if not isinstance(erp_response, dict) or 'items' not in erp_response:
                logger.error(f"ERP invoice search returned an invalid response structure: {erp_response}")
                # Return empty pagination structure on unexpected response format
                return { "items": [], "page": page, "pageSize": page_size, "totalItems": 0, "totalPages": 0 }

            # Format items from the current page
            formatted_items = [self._format_invoice_list_item(item) for item in erp_response.get('items', []) if isinstance(item, dict)]

            # Extract pagination metadata from the ERP response
            total_items_erp = erp_response.get('count', 0)
            total_pages_erp = erp_response.get('totalPages', 0)
            # Recalculate total pages if needed based on totalItems and our clamped page_size
            # if total_items_erp > 0 and page_size > 0:
            #      total_pages_erp = (total_items_erp + total_pages_erp - 1) // page_size

            # Structure the final response
            result = {
                "items": formatted_items,
                "page": page,
                "pageSize": page_size, # Return the actual page size used (might be clamped)
                "totalItems": total_items_erp,
                "totalPages": total_pages_erp
            }
            logger.info(f"Successfully fetched and formatted {len(formatted_items)} invoices for page {page}. TotalItems: {total_items_erp}")
            return result

        except (ValidationError, NotFoundError) as e:
            logger.warning(f"Validation or Not Found error during invoice search: {e}")
            raise e
        except ErpIntegrationError as e:
             logger.error(f"ERP Integration error during invoice search: {e}", exc_info=False) # Already logged details in ERP layer
             raise ServiceError(f"Failed to communicate with ERP for invoice search: {e.message}") from e
        except Exception as e:
            logger.error(f"Unexpected error searching or processing invoices: {e}", exc_info=True)
            raise ServiceError(f"An unexpected error occurred while searching invoices: {e}") from e

    def _format_invoice_list_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Formats a single raw invoice item from ERP into the desired list structure."""
        if not item:
            return {}

        # Safely get nested values using .get() - Use dicts directly
        eletronic_data = item.get('eletronic') if isinstance(item.get('eletronic'), dict) else {}
        person_data = item.get('person') if isinstance(item.get('person'), dict) else {}
        shipping_data = item.get('shippingCompany') if isinstance(item.get('shippingCompany'), dict) else {}
        sales_orders = item.get('salesOrder') # It's often a list in TOTVS APIs

        # Determine sales order code (Handle list or single object)
        sales_order_code = None
        if isinstance(sales_orders, list) and sales_orders:
            first_order = sales_orders[0]
            if isinstance(first_order, dict):
                 sales_order_code = first_order.get('orderCode')
        elif isinstance(sales_orders, dict): # Handle case if API returns single object
            sales_order_code = sales_orders.get('orderCode')


        # Format using the domain model structure (but returning dict)
        formatted = FormattedInvoiceListItem(
            status=eletronic_data.get('electronicInvoiceStatus'),
            recipient_name=person_data.get('personName'),
            sales_order_code=sales_order_code,
            invoice_number=item.get('invoiceCode'),
            invoice_series=item.get('serialCode'),
            issue_date=eletronic_data.get('receivementDate') or item.get('issueDate') or item.get('invoiceDate'), # Prioritize NFe date
            total_value=item.get('totalValue'),
            total_quantity=item.get('quantity'),
            operation_name=item.get('operatioName'),
            shipping_company_name=shipping_data.get('shippingCompanyName'), # Name might be just 'name' check expand structure
            access_key=eletronic_data.get('accessKey')
        )

        return formatted.to_dict()


    def generate_danfe_pdf(self, access_key: str) -> bytes:
        """
        Generates the DANFE PDF for a given invoice access key.

        Args:
            access_key: The 44-digit access key of the invoice.

        Returns:
            The raw PDF content as bytes.

        Raises:
            ValidationError: If access key is invalid.
            NotFoundError: If the invoice XML or DANFE cannot be found/generated.
            ServiceError: If an error occurs during ERP communication or processing.
        """
        if not access_key or len(access_key) != 44 or not access_key.isdigit():
             raise ValidationError("Invalid access key format. Must be 44 digits.")

        logger.info(f"Generating DANFE for access key: ...{access_key[-6:]}")
        try:
            # 1. Get XML Content
            logger.debug(f"Step 1: Fetching XML for access key ...{access_key[-6:]}")
            xml_dto = self.erp_fiscal_service.get_xml_content(access_key)
            # erp_fiscal_service raises NotFoundError/ErpIntegrationError if needed
            main_xml_base64 = xml_dto.main_invoice_xml
            logger.debug(f"Step 1: Successfully fetched main XML (Base64 Length: {len(main_xml_base64)}).")

            # 2. Get DANFE from XML
            logger.debug(f"Step 2: Requesting DANFE using fetched XML...")
            danfe_dto = self.erp_fiscal_service.get_danfe_from_xml(main_xml_base64)
            # erp_fiscal_service raises NotFoundError/ErpIntegrationError if needed
            pdf_base64 = danfe_dto.danfe_pdf_base64
            logger.debug(f"Step 2: Successfully received DANFE PDF (Base64 Length: {len(pdf_base64)}).")

            # 3. Decode Base64 to PDF bytes
            try:
                pdf_bytes = base64.b64decode(pdf_base64, validate=True) # Add validation
                logger.info(f"Successfully generated and decoded DANFE PDF for access key ...{access_key[-6:]}.")
                return pdf_bytes
            except (base64.binascii.Error, ValueError) as decode_err:
                logger.error(f"Failed to decode Base64 DANFE PDF: {decode_err}", exc_info=True)
                raise ServiceError("Failed to decode the generated DANFE PDF.")

        except (NotFoundError, ValidationError) as e:
             logger.warning(f"DANFE Generation failed for key ...{access_key[-6:]}: {e}")
             raise e # Re-raise specific errors
        except ErpIntegrationError as e:
             logger.error(f"ERP Integration error during DANFE generation for key ...{access_key[-6:]}: {e}", exc_info=False)
             # Make error message clearer
             raise ServiceError(f"Failed ERP communication during DANFE generation: {e.message}") from e
        except Exception as e:
            logger.error(f"Unexpected error generating DANFE for access key ...{access_key[-6:]}: {e}", exc_info=True)
            raise ServiceError(f"An unexpected error occurred while generating DANFE: {e}") from e