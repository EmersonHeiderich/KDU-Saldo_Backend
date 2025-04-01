# src/services/accounts_receivable_service.py
# Contains business logic for the Accounts Receivable module.

import base64
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple, Set, Union

# ERP Services
from src.erp_integration.erp_accounts_receivable_service import ErpAccountsReceivableService
from src.erp_integration.erp_person_service import ErpPersonService

# Domain Models
from src.domain.accounts_receivable import (
    DocumentChangeModel, DocumentRequestModel, DocumentFilterModel, DocumentModel, DocumentResponseModel,
    BankSlipRequestModel, AccountsReceivableTomasResponseModel, FormattedReceivableListItem,
    CalculatedValuesModel, InvoiceDataModel
)
from src.domain.person import IndividualDataModel, LegalEntityDataModel

# Utils & Errors
from src.utils.logger import logger
from src.api.errors import ServiceError, NotFoundError, ValidationError, ErpIntegrationError
from src.config import config

# PDF Util (create if not exists)
from src.utils.pdf_utils import decode_base64_to_bytes # Assuming this util exists

class AccountsReceivableService:
    """
    Service layer for handling Accounts Receivable operations.
    """
    def __init__(self,
                 erp_ar_service: ErpAccountsReceivableService,
                 erp_person_service: ErpPersonService):
        self.erp_ar_service = erp_ar_service
        self.erp_person_service = erp_person_service
        logger.info("AccountsReceivableService initialized.")

    # --- Filter Parsing/Validation (Example - expand as needed) ---
    def _parse_and_validate_filters(self, raw_filters: Optional[Dict[str, Any]]) -> Optional[DocumentFilterModel]:
        """Parses raw filter dictionary into DocumentFilterModel, performing validation."""
        if not raw_filters or not isinstance(raw_filters, dict):
            return None

        filter_args: Dict[str, Any] = {} # Dictionary to hold validated args for constructor

        try:
            # --- Parse List Filters ---
            list_int_keys = {
                'branchCodeList': 'branch_code_list', 'customerCodeList': 'customer_code_list',
                'statusList': 'status_list', 'documentTypeList': 'document_type_list',
                'billingTypeList': 'billing_type_list', 'dischargeTypeList': 'discharge_type_list',
                'chargeTypeList': 'charge_type_list'
            }
            for raw_key, model_key in list_int_keys.items():
                value = raw_filters.get(raw_key)
                if value is not None:
                    if not isinstance(value, list) or not all(isinstance(x, int) for x in value):
                        raise ValidationError(f"Filter '{raw_key}' must be a list of integers.")
                    if value:
                        filter_args[model_key] = value # *** USE model_key ***

            list_str_keys = {'customerCpfCnpjList': 'customer_cpf_cnpj_list'}
            for raw_key, model_key in list_str_keys.items():
                value = raw_filters.get(raw_key)
                if value is not None:
                    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                        raise ValidationError(f"Filter '{raw_key}' must be a list of strings.")
                    if value:
                        filter_args[model_key] = value # *** USE model_key ***

            list_float_keys = {'receivableCodeList': 'receivable_code_list', 'ourNumberList': 'our_number_list'}
            for raw_key, model_key in list_float_keys.items():
                value = raw_filters.get(raw_key)
                if value is not None:
                    if not isinstance(value, list) or not all(isinstance(x, (int, float)) for x in value):
                        raise ValidationError(f"Filter '{raw_key}' must be a list of numbers.")
                    if value:
                        filter_args[model_key] = [float(x) for x in value] # *** USE model_key ***

            # --- Parse Date Filters ---
            date_keys = {
                'startExpiredDate': 'start_expired_date', 'endExpiredDate': 'end_expired_date',
                'startPaymentDate': 'start_payment_date', 'endPaymentDate': 'end_payment_date',
                'startIssueDate': 'start_issue_date', 'endIssueDate': 'end_issue_date',
                'startCreditDate': 'start_credit_date', 'endCreditDate': 'end_credit_date',
                'closingDateCommission': 'closing_date_commission'
            }
            for raw_key, model_key in date_keys.items():
                value = raw_filters.get(raw_key)
                if value is not None:
                    try:
                        datetime.fromisoformat(str(value).replace('Z', '+00:00'))
                        filter_args[model_key] = str(value)
                    except (ValueError, TypeError):
                         raise ValidationError(f"Invalid date format for filter '{raw_key}': {value}. Use ISO 8601.")

            # --- Parse Boolean Filters ---
            bool_keys = {'hasOpenInvoices': 'has_open_invoices'}
            for raw_key, model_key in bool_keys.items():
                value = raw_filters.get(raw_key)
                if value is not None:
                    if not isinstance(value, bool):
                        raise ValidationError(f"Filter '{raw_key}' must be a boolean (true/false).")
                    filter_args[model_key] = value # *** USE model_key ***

            # --- Parse Simple Int/String Filters ---
            simple_int_keys = {
                'commissionedCode': 'commissioned_code', 'closingCodeCommission': 'closing_code_commission',
                'closingCompanyCommission': 'closing_company_commission', 'closingCommissionedCode': 'closing_commissioned_code'
            }
            for raw_key, model_key in simple_int_keys.items():
                 value = raw_filters.get(raw_key)
                 if value is not None:
                      if not isinstance(value, int): raise ValidationError(f"Filter '{raw_key}' must be an integer.")
                      filter_args[model_key] = value # *** USE model_key ***

            simple_str_keys = {
                'commissionedCpfCnpj': 'commissioned_cpf_cnpj', 'closingCommissionedCpfCnpj': 'closing_commissioned_cpf_cnpj'
            }
            for raw_key, model_key in simple_str_keys.items():
                 value = raw_filters.get(raw_key)
                 if value is not None:
                      if not isinstance(value, str): raise ValidationError(f"Filter '{raw_key}' must be a string.")
                      filter_args[model_key] = value # *** USE model_key ***

            # --- Parse 'change' Filter Object ---
            change_data = raw_filters.get('change')
            if change_data is not None:
                 if not isinstance(change_data, dict):
                     raise ValidationError("Filter 'change' must be an object.")
                 change_model = DocumentChangeModel.from_dict(change_data)
                 if change_model:
                      filter_args['change'] = change_model # Use 'change' as key, as it matches the model attribute

            # --- Instantiate the frozen dataclass ONCE with all args ---
            if not filter_args:
                 return None

            parsed = DocumentFilterModel(**filter_args)
            logger.debug(f"Parsed filters: {parsed.to_dict()}")
            return parsed

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error parsing filters: {e}", exc_info=True)
            raise ValidationError(f"Invalid filter format: {e}")


    def _fetch_customer_names(self, documents: List[DocumentModel]) -> Dict[int, str]:
        """Fetches names for unique customers present in the document list."""
        customer_ids: Set[int] = set()
        for doc in documents:
            if doc.customer_code:
                customer_ids.add(doc.customer_code)

        if not customer_ids:
            return {}

        logger.debug(f"Fetching names for {len(customer_ids)} unique customer codes.")
        names_map: Dict[int, str] = {}
        # TODO: Potential Optimization: Batch request to Person API if supported?
        # For now, fetch one by one. Consider adding caching here (request-level or longer).
        for code in customer_ids:
            name = "Nome Não Encontrado" # Default
            try:
                # Try fetching as Legal Entity first, then Individual
                person: Optional[Union[LegalEntityDataModel, IndividualDataModel]] = \
                    self.erp_person_service.get_legal_entity_by_code(code)
                if person:
                    name = person.name # Razao Social
                else:
                    person = self.erp_person_service.get_individual_by_code(code)
                    if person:
                        name = person.name

                names_map[code] = name

            except ErpIntegrationError as e:
                 logger.warning(f"Failed to fetch name for customer code {code}: {e.message}")
                 # Keep default name "Nome Não Encontrado"
            except Exception as e:
                 logger.error(f"Unexpected error fetching name for customer code {code}: {e}", exc_info=True)

        logger.debug(f"Fetched names for {len(names_map)} customers.")
        return names_map

    def _format_receivable_list_item(self, doc: DocumentModel, customer_names: Dict[int, str]) -> FormattedReceivableListItem:
        """Formats a single DocumentModel, applying conditional logic for calculated values."""

        # Get invoice number
        invoice_number = None
        if doc.invoice and doc.invoice[0]:
             invoice_number = doc.invoice[0].invoice_code

        # Get customer name
        cust_name = customer_names.get(doc.customer_code, "Nome Indisponível") if doc.customer_code else "Cliente Inválido"

        # --- Determine Title Status ---
        is_paid = doc.discharge_type != 0 or doc.payment_date is not None
        is_overdue = False
        current_date = date.today() # Use date for comparison with expired_date

        if doc.expired_date and not is_paid:
            try:
                # Extract only the date part for comparison
                expired_dt = datetime.fromisoformat(doc.expired_date.split('T')[0]).date()
                is_overdue = expired_dt < current_date
            except (ValueError, TypeError):
                logger.warning(f"Could not parse expired_date: {doc.expired_date} for doc {doc.receivable_code}/{doc.installment_code}")

        # --- Initialize formatted values ---
        days_late = None
        value_corrected = None
        increase = 0.0
        rebate = 0.0
        calc_vals: Optional[CalculatedValuesModel] = doc.calculated_values # Keep reference

        # --- Apply Conditional Logic based on Status ---
        use_calculated_for_current = is_overdue and calc_vals is not None

        if use_calculated_for_current:
            # *** Use calculatedValues for Open and Overdue titles ***
            logger.debug(f"Doc {doc.receivable_code}/{doc.installment_code}: Using calculatedValues (Currently Overdue)")
            days_late = calc_vals.days_late
            value_corrected = calc_vals.corrected_value
            # Combine increase/interest/fine from calculatedValues
            increase = (calc_vals.increase_value or 0.0) + \
                       (calc_vals.interest_value or 0.0) + \
                       (calc_vals.fine_value or 0.0)
            # Use discount from calculatedValues context
            rebate = (calc_vals.discount_value or 0.0)

        else:
            # *** Use direct fields for Paid or Not Yet Due titles ***
            logger.debug(f"Doc {doc.receivable_code}/{doc.installment_code}: Using direct fields (Paid or Not Yet Due)")
            # days_late and value_corrected remain None
            # Use historical interest/assessment recorded on the document itself
            increase = (doc.interest_value or 0.0) + (doc.assessment_value or 0.0)
            # Use historical rebate/discount recorded on the document itself
            rebate = (doc.rebate_value or 0.0) + (doc.discount_value or 0.0)

        # --- Format final increase/rebate (show null if zero) ---
        value_increase = increase if increase > 0 else None
        value_rebate = rebate if rebate > 0 else None


        # --- Instantiate FormattedReceivableListItem ---
        return FormattedReceivableListItem(
            customer_code=doc.customer_code,
            customer_cpf_cnpj=doc.customer_cpf_cnpj,
            customer_name=cust_name,
            invoice_number=invoice_number,
            document_number=doc.receivable_code,
            installment_number=doc.installment_code,
            bearer_name=doc.bearer_name,
            issue_date=doc.issue_date,
            expired_date=doc.expired_date,
            payment_date=doc.payment_date,
            value_original=doc.installment_value,
            value_paid=doc.paid_value,
            # --- Use conditionally calculated values ---
            days_late=days_late,
            value_increase=value_increase,
            value_rebate=value_rebate,
            value_corrected=value_corrected,
            # --- Map other fields ---
            status=doc.status,
            document_type=doc.document_type,
            billing_type=doc.billing_type,
            discharge_type=doc.discharge_type,
            charge_type=doc.charge_type
        )

    def search_receivables(self, raw_filters: Optional[Dict[str, Any]], page: int, page_size: int, expand: Optional[str], order: Optional[str]) -> Dict[str, Any]:
        """
        Searches for accounts receivable documents, enforces default branch filter,
        enriches with customer names, and formats the results.
        """
        logger.info(f"Searching receivables. Page: {page}, Size: {page_size}, Filters: {raw_filters is not None}, Expand: {expand}, Order: {order}")

        if page < 1: page = 1
        if page_size < 1 or page_size > 100:
             logger.warning(f"Adjusting page size from {page_size} to 100 (API limit).")
             page_size = 100

        # Always expand calculatedValues and invoice for the required fields
        expand_list = set(item.strip() for item in expand.split(',') if item.strip()) if expand else set()
        expand_list.add("calculatedValues")
        expand_list.add("invoice")
        final_expand_str = ",".join(sorted(list(expand_list)))

        try:
            # 1. Parse and Validate User Filters
            parsed_user_filters = self._parse_and_validate_filters(raw_filters)

            # 2. *** Ensure Branch Code Filter is Present ***
            filter_for_request: DocumentFilterModel
            default_branch = [config.COMPANY_CODE] # Use company code from config

            if parsed_user_filters is None:
                # No filters provided by user, create filter with only default branch
                logger.debug("No user filters provided. Applying default branch filter.")
                filter_for_request = DocumentFilterModel(branch_code_list=default_branch)
            elif not parsed_user_filters.branch_code_list:
                # User provided filters, but not branchCodeList. Add default branch.
                logger.debug("User filters provided without branchCodeList. Adding default branch filter.")
                # Since DocumentFilterModel is frozen, create a new one by merging
                # Importante: to_dict() retorna chaves em camelCase (formato API), mas precisamos de snake_case para o modelo
                filter_dict = parsed_user_filters.to_dict()
                
                # Convertendo de volta para snake_case para o DocumentFilterModel
                filter_args = {}
                date_keys_map = {
                    'startExpiredDate': 'start_expired_date', 'endExpiredDate': 'end_expired_date',
                    'startPaymentDate': 'start_payment_date', 'endPaymentDate': 'end_payment_date',
                    'startIssueDate': 'start_issue_date', 'endIssueDate': 'end_issue_date',
                    'startCreditDate': 'start_credit_date', 'endCreditDate': 'end_credit_date',
                    'closingDateCommission': 'closing_date_commission'
                }
                int_list_keys_map = {
                    'branchCodeList': 'branch_code_list', 'customerCodeList': 'customer_code_list',
                    'statusList': 'status_list', 'documentTypeList': 'document_type_list',
                    'billingTypeList': 'billing_type_list', 'dischargeTypeList': 'discharge_type_list',
                    'chargeTypeList': 'charge_type_list'
                }
                str_list_keys_map = {'customerCpfCnpjList': 'customer_cpf_cnpj_list'}
                float_list_keys_map = {'receivableCodeList': 'receivable_code_list', 'ourNumberList': 'our_number_list'}
                bool_keys_map = {'hasOpenInvoices': 'has_open_invoices'}
                simple_keys_map = {
                    'commissionedCode': 'commissioned_code', 'closingCodeCommission': 'closing_code_commission',
                    'closingCompanyCommission': 'closing_company_commission', 'closingCommissionedCode': 'closing_commissioned_code',
                    'commissionedCpfCnpj': 'commissioned_cpf_cnpj', 'closingCommissionedCpfCnpj': 'closing_commissioned_cpf_cnpj'
                }
                
                # Mapeando todas as chaves camelCase para snake_case
                all_keys_map = {**date_keys_map, **int_list_keys_map, **str_list_keys_map, 
                               **float_list_keys_map, **bool_keys_map, **simple_keys_map}
                
                for camel_key, snake_key in all_keys_map.items():
                    if camel_key in filter_dict:
                        filter_args[snake_key] = filter_dict[camel_key]
                
                # Tratar a chave 'change' separadamente, pois é um objeto
                if 'change' in filter_dict:
                    filter_args['change'] = DocumentChangeModel.from_dict(filter_dict['change'])
                
                # Adicionar branch_code_list
                filter_args['branch_code_list'] = default_branch
                
                # Agora criamos o modelo com chaves corretas
                filter_for_request = DocumentFilterModel(**filter_args)
            else:
                # User provided branchCodeList, use their filters directly
                logger.debug("User provided branchCodeList in filters.")
                filter_for_request = parsed_user_filters
            # ********************************************

            # 3. Prepare ERP Request Payload using the guaranteed filter
            request_payload = DocumentRequestModel(
                filter=filter_for_request, # Use the filter that now includes branchCodeList
                expand=final_expand_str,
                order=order,
                page=page,
                page_size=page_size
            )

            # 4. Call ERP Service
            erp_response_dict = self.erp_ar_service.search_documents(request_payload.to_dict())

            # 5. Parse ERP Response
            erp_response = DocumentResponseModel.from_dict(erp_response_dict)
            if not erp_response:
                raise ServiceError("Failed to parse ERP response for receivables search.")

            # 6. Fetch Customer Names
            customer_names = self._fetch_customer_names(erp_response.items)

            # 7. Format Results
            formatted_items = [self._format_receivable_list_item(doc, customer_names) for doc in erp_response.items]

            # 8. Construct Final API Response
            result = {
                "items": [item.to_dict() for item in formatted_items],
                "page": page,
                "pageSize": page_size,
                "totalItems": erp_response.total_items,
                "totalPages": erp_response.total_pages,
                "hasNext": erp_response.has_next
            }
            logger.info(f"Successfully fetched and formatted {len(formatted_items)} receivables for page {page}. Total: {erp_response.total_items}")
            return result

        except (ValidationError, NotFoundError) as e:
            logger.warning(f"Search receivables failed: {e}")
            raise e
        except ErpIntegrationError as e:
             logger.error(f"ERP Integration error during receivables search: {e}", exc_info=False)
             raise ServiceError(f"Failed to communicate with ERP for receivables search: {e.message}") from e
        except Exception as e:
            logger.error(f"Unexpected error searching receivables: {e}", exc_info=True)
            raise ServiceError(f"An unexpected error occurred while searching receivables: {e}") from e

    def generate_boleto_pdf(self, request_data: Dict[str, Any]) -> bytes:
        """
        Generates the Bank Slip (Boleto) PDF for a specific receivable installment.
        """
        logger.info(f"Generating boleto PDF request received: {request_data}")

        # Validate required fields
        required = ['branchCode', 'customerCode', 'receivableCode', 'installmentNumber']
        missing = [field for field in required if field not in request_data]
        if missing:
            raise ValidationError(f"Missing required fields for boleto generation: {', '.join(missing)}")

        try:
            # Create request model instance
            boleto_request = BankSlipRequestModel(
                branch_code=int(request_data['branchCode']),
                customer_code=int(request_data['customerCode']),
                receivable_code=int(request_data['receivableCode']),
                installment_number=int(request_data['installmentNumber']),
                customer_cpf_cnpj=request_data.get('customerCpfCnpj') # Optional
            )
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid data type in boleto request parameters: {e}")


        try:
            # 1. Call ERP Service
            erp_response_dict = self.erp_ar_service.get_bank_slip(boleto_request.to_dict())

            # 2. Parse ERP Response
            tomas_response = AccountsReceivableTomasResponseModel.from_dict(erp_response_dict)
            if not tomas_response:
                 raise ServiceError("Failed to parse ERP response for bank slip generation.")

            # *** CORRECTED Uniface status check ***
            status_lower = tomas_response.uniface_response_status.lower() if tomas_response.uniface_response_status else ""
            # Consider "ok" or "success" as valid positive outcomes
            if tomas_response.uniface_response_status and status_lower not in ('ok', 'success'):
                 err_msg = tomas_response.uniface_message or "Unknown Uniface error"
                 logger.error(f"Boleto generation failed in Uniface. Status: {tomas_response.uniface_response_status}, Message: {err_msg}")
                 # Raise ServiceError only if status is explicitly NOT ok/success
                 raise ServiceError(f"Boleto generation failed in ERP ({tomas_response.uniface_response_status}): {err_msg}")
            # ***************************************

            # 3. Extract Base64 Content
            pdf_base64 = tomas_response.content
            if not pdf_base64:
                logger.error("ERP response for bank slip generation is missing the 'content' (Base64 PDF). Status was: %s", tomas_response.uniface_response_status)
                # If status was Success but content missing, it's still an error
                raise NotFoundError("Boleto PDF could not be generated by the ERP (missing content).")

            # 4. Decode Base64 to Bytes
            pdf_bytes = decode_base64_to_bytes(pdf_base64) # Uses utility
            logger.info("Successfully generated and decoded Boleto PDF.")
            return pdf_bytes

        except (ValidationError, NotFoundError) as e:
            logger.warning(f"Boleto generation failed: {e}")
            raise e
        except ErpIntegrationError as e:
             logger.error(f"ERP Integration error during boleto generation: {e}", exc_info=False)
             raise ServiceError(f"Failed ERP communication during boleto generation: {e.message}") from e
        except ServiceError as e: # Catch the error raised above for specific Uniface failures
             raise e
        except Exception as e:
            logger.error(f"Unexpected error generating boleto PDF: {e}", exc_info=True)
            # Ensure the original error isn't shadowed if it was the ServiceError raised above
            if isinstance(e, ServiceError):
                 raise # Re-raise the specific service error
            else:
                 raise ServiceError(f"An unexpected error occurred while generating the boleto: {e}") from e
