# src/services/fiscal_service.py
# Contains business logic for the Fiscal module.

import base64
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
# Import ErpFiscalService correctly
from src.erp_integration.erp_fiscal_service import ErpFiscalService, FISCAL_INVOICE_PAGE_SIZE
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

    # --- Filter Parsing Helpers ---
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
            datetime.fromisoformat(date_str.replace('Z', '+00:00')) # Handle Z suffix
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

        filter_value = str(filter_value).strip()

        if '-' in filter_value and ',' not in filter_value:
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
             try:
                  invoice_code_list = self._parse_numeric_list_filter(filter_value)
                  if not invoice_code_list and filter_value:
                       raise ValidationError(f"Invalid invoice number list/value: '{filter_value}'.")
             except ValidationError:
                  raise
             except Exception as e:
                  logger.error(f"Unexpected error parsing invoice numbers '{filter_value}': {e}", exc_info=True)
                  raise ValidationError(f"Could not parse invoice numbers: '{filter_value}'.")

        return invoice_code_list, start_invoice_code, end_invoice_code
    # --- End Filter Parsing Helpers ---


    def search_invoices(self, filters: Dict[str, Any], page: int = 1, page_size: int = config.FISCAL_PAGE_SIZE) -> Dict[str, Any]:
        """
        Searches for invoices based on filters for a specific page and formats the results.
        (Method documentation remains the same)
        """
        logger.info(f"Searching invoices with filters: {filters}, Page: {page}, PageSize: {page_size}")

        if page_size > FISCAL_INVOICE_PAGE_SIZE:
             logger.warning(f"Requested pageSize {page_size} exceeds limit {FISCAL_INVOICE_PAGE_SIZE}. Clamping.")
             page_size = FISCAL_INVOICE_PAGE_SIZE
        elif page_size < 1:
             page_size = config.FISCAL_PAGE_SIZE

        # Initialize erp_filter with mandatory filters FIRST
        erp_filter: Dict[str, Any] = {
            "branchCodeList": [config.COMPANY_CODE],
            "documentTypeCodeList": [55], # NF-e
            "operationType": "S", # Saida
            "origin": "Own", # Check if "Own" string or an Enum int is needed
        }

        # --- Apply User Filters (Merge into erp_filter) ---
        try:
            person_code_list = self._parse_numeric_list_filter(filters.get('customer_code'))
            if person_code_list:
                erp_filter["personCodeList"] = person_code_list

            person_cpf_cnpj_list = self._parse_list_filter(filters.get('customer_cpf_cnpj'))
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
                 erp_filter["startIssueDate"] = start_issue_date

            end_issue_date = self._parse_date_filter(filters.get('end_date'))
            if end_issue_date:
                 erp_filter["endIssueDate"] = end_issue_date

            status_filter = self._parse_list_filter(filters.get('status'))
            if status_filter:
                 status_map = {
                     "authorized": "Authorized", "cancelado": "Canceled", # Added Portuguese cancelado
                     "canceled": "Canceled", "denied": "Denied", "sent": "Sent",
                     "generated": "Generated", "rejected": "Rejected", "pending": "Pending",
                     "autorizada": "Authorized", "denegada": "Denied", # Added Portuguese
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
                 if erp_statuses:
                      erp_filter["eletronicInvoiceStatusList"] = erp_statuses
                 elif status_filter:
                      raise ValidationError(f"No valid status values provided. Valid options (case-insensitive): {list(status_map.keys())}")

        except ValidationError as ve:
             logger.warning(f"Filter validation failed: {ve}")
             raise


        # --- Prepare full ERP payload AFTER merging filters --- <<<--- MOVED
        payload = {
            "filter": erp_filter, # Now erp_filter contains merged filters
            "expand": "shippingCompany, salesOrder, person, eletronic",
            "order": "-invoiceSequence",
            "page": page,
            "pageSize": page_size
        }
        # -------------------------------------------------------

        try:
            logger.debug(f"Calling ERP search_invoices with payload: {payload}")
            erp_response = self.erp_fiscal_service.search_invoices(payload)

            if not isinstance(erp_response, dict) or 'items' not in erp_response:
                logger.error(f"ERP invoice search returned an invalid response structure: {erp_response}")
                return { "items": [], "page": page, "pageSize": page_size, "totalItems": 0, "totalPages": 0 }

            formatted_items = [self._format_invoice_list_item(item) for item in erp_response.get('items', []) if isinstance(item, dict)]

            total_items_erp = erp_response.get('count', 0)
            total_pages_erp = erp_response.get('totalPages', 0)

            result = {
                "items": formatted_items,
                "page": page,
                "pageSize": page_size,
                "totalItems": total_items_erp,
                "totalPages": total_pages_erp
            }
            logger.info(f"Successfully fetched and formatted {len(formatted_items)} invoices for page {page}. Total Matching Items: {total_items_erp}")
            return result

        except (ValidationError, NotFoundError) as e:
            logger.warning(f"Validation or Not Found error during invoice search: {e}")
            raise e
        except ErpIntegrationError as e:
             logger.error(f"ERP Integration error during invoice search: {e}", exc_info=False)
             raise ServiceError(f"Failed to communicate with ERP for invoice search: {e.message}") from e
        except Exception as e:
            logger.error(f"Unexpected error searching or processing invoices: {e}", exc_info=True)
            raise ServiceError(f"An unexpected error occurred while searching invoices: {e}") from e

    def _format_invoice_list_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Formats a single raw invoice item from ERP into the desired list structure."""
        if not item:
            return {}

        eletronic_data = item.get('eletronic') if isinstance(item.get('eletronic'), dict) else {}
        person_data = item.get('person') if isinstance(item.get('person'), dict) else {}
        shipping_data = item.get('shippingCompany') if isinstance(item.get('shippingCompany'), dict) else {}
        sales_orders = item.get('salesOrder') # List or dict

        sales_order_code = None
        if isinstance(sales_orders, list) and sales_orders:
            first_order = sales_orders[0]
            if isinstance(first_order, dict):
                 sales_order_code = first_order.get('orderCode')
        elif isinstance(sales_orders, dict):
            sales_order_code = sales_orders.get('orderCode')

        # Use the FormattedInvoiceListItem dataclass for structure definition
        formatted = FormattedInvoiceListItem(
            status=eletronic_data.get('electronicInvoiceStatus'),
            recipient_name=person_data.get('personName'),
            sales_order_code=sales_order_code,
            invoice_number=item.get('invoiceCode'),
            invoice_series=item.get('serialCode'),
            # Prioritize electronic date, fall back to main issue/invoice date
            issue_date=eletronic_data.get('receivementDate') or eletronic_data.get('issueDate') or item.get('issueDate') or item.get('invoiceDate'),
            total_value=item.get('totalValue'),
            total_quantity=item.get('quantity'),
            operation_name=item.get('operatioName'), # Use the potential typo name from ERP
            # Check potential names for shipping company name based on expand structure
            shipping_company_name=shipping_data.get('shippingCompanyName') or shipping_data.get('name'),
            access_key=eletronic_data.get('accessKey')
        )
        # Convert the dataclass instance to a dictionary for the final JSON response
        return formatted.to_dict()

    def generate_danfe_pdf(self, access_key: str) -> bytes:
        """
        Generates the DANFE PDF for a given invoice access key.
        (Method documentation remains the same)
        """
        if not access_key or len(access_key) != 44 or not access_key.isdigit():
             raise ValidationError("Invalid access key format. Must be 44 digits.")

        logger.info(f"Generating DANFE for access key: ...{access_key[-6:]}")
        try:
            # 1. Get XML Content
            logger.debug(f"Step 1: Fetching XML for access key ...{access_key[-6:]}")
            xml_dto = self.erp_fiscal_service.get_xml_content(access_key)
            main_xml_base64 = xml_dto.main_invoice_xml
            logger.debug(f"Step 1: Successfully fetched main XML (Base64 Length: {len(main_xml_base64)}).")

            # 2. Get DANFE from XML
            logger.debug(f"Step 2: Requesting DANFE using fetched XML...")
            danfe_dto = self.erp_fiscal_service.get_danfe_from_xml(main_xml_base64)
            pdf_base64 = danfe_dto.danfe_pdf_base64
            logger.debug(f"Step 2: Successfully received DANFE PDF (Base64 Length: {len(pdf_base64)}).")

            # 3. Decode Base64 to PDF bytes
            try:
                pdf_bytes = base64.b64decode(pdf_base64, validate=True)
                logger.info(f"Successfully generated and decoded DANFE PDF for access key ...{access_key[-6:]}.")
                return pdf_bytes
            except (base64.binascii.Error, ValueError) as decode_err:
                logger.error(f"Failed to decode Base64 DANFE PDF: {decode_err}", exc_info=True)
                raise ServiceError("Failed to decode the generated DANFE PDF.")

        except (NotFoundError, ValidationError) as e:
             logger.warning(f"DANFE Generation failed for key ...{access_key[-6:]}: {e}")
             raise e
        except ErpIntegrationError as e:
             logger.error(f"ERP Integration error during DANFE generation for key ...{access_key[-6:]}: {e}", exc_info=False)
             raise ServiceError(f"Failed ERP communication during DANFE generation: {e.message}") from e
        except Exception as e:
            logger.error(f"Unexpected error generating DANFE for access key ...{access_key[-6:]}: {e}", exc_info=True)
            raise ServiceError(f"An unexpected error occurred while generating DANFE: {e}") from e