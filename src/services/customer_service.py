# src/services/customer_service.py
# Contains business logic related to fetching and formatting customer data.

from typing import Optional, Dict, Any, Union, List # <<<--- ADD List HERE (and others)
from src.domain.person import IndividualDataModel, LegalEntityDataModel, PersonStatisticsResponseModel
from src.erp_integration.erp_person_service import ErpPersonService # Import ERP service
from src.utils.logger import logger
from src.api.errors import NotFoundError, ServiceError, ValidationError # Import custom errors

class CustomerService:
    """
    Service layer for handling customer-related operations, interacting
    with the ERP integration layer.
    """
    def __init__(self, erp_person_service: ErpPersonService):
        self.erp_person_service = erp_person_service
        logger.info("CustomerService initialized.")

    def get_customer_details(self, search_term: str, search_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetches and formats customer details (Individual or Legal Entity) based on search criteria.

        Args:
            search_term: The search value (Code, CPF, or CNPJ).
            search_type: Required if search_term is a code ('PF' or 'PJ').

        Returns:
            A dictionary containing formatted customer data.

        Raises:
            ValidationError: If search parameters are invalid.
            NotFoundError: If the customer is not found in the ERP.
            ServiceError: If an error occurs during ERP communication or data processing.
        """
        logger.debug(f"Fetching customer details for search term: '{search_term}', type: {search_type}")
        search_term = str(search_term).strip()
        customer_data: Optional[Union[IndividualDataModel, LegalEntityDataModel]] = None
        customer_type: str = ""

        try:
            # Determine search method based on input
            if search_term.isdigit() and len(search_term) <= 9: # Assuming max 9 digits for code
                if not search_type or search_type.upper() not in ("PF", "PJ"):
                    raise ValidationError("Field 'search_type' ('PF' or 'PJ') is required when searching by code.")
                customer_type = search_type.upper()
                customer_code = int(search_term)
                if customer_type == "PF":
                    customer_data = self.erp_person_service.get_individual_by_code(customer_code)
                else:
                    customer_data = self.erp_person_service.get_legal_entity_by_code(customer_code)

            elif len(search_term) == 11 and search_term.isdigit():
                customer_type = "PF"
                customer_data = self.erp_person_service.get_individual_by_cpf(search_term)
            elif len(search_term) == 14 and search_term.isdigit():
                customer_type = "PJ"
                customer_data = self.erp_person_service.get_legal_entity_by_cnpj(search_term)
            else:
                raise ValidationError("Invalid format for 'search_term'. Must be Code (with type 'PF'/'PJ'), CPF (11 digits), or CNPJ (14 digits).")

            if not customer_data:
                logger.warning(f"Customer not found for search term: '{search_term}', type: {search_type}")
                raise NotFoundError("Customer not found.")

            # Format the response
            formatted_response = self._format_customer_data(customer_data, customer_type)
            logger.info(f"Successfully fetched details for customer code: {customer_data.code}")
            return formatted_response

        except (NotFoundError, ValidationError) as e:
             # Re-raise specific validation/not found errors
             raise e
        except Exception as e:
            # Catch errors from ERP service or formatting
            logger.error(f"Error fetching customer details for '{search_term}': {e}", exc_info=True)
            # Wrap other exceptions in a generic ServiceError
            raise ServiceError(f"Failed to retrieve customer details: {e}") from e


    def get_customer_statistics(self, customer_code: int, is_admin: bool) -> Dict[str, Any]:
        """
        Fetches and formats customer statistics from the ERP.

        Args:
            customer_code: The unique code of the customer.
            is_admin: Flag indicating if the requesting user is an admin.

        Returns:
            A dictionary containing formatted customer statistics.

        Raises:
            NotFoundError: If statistics are not found for the customer.
            ServiceError: If an error occurs during ERP communication or data processing.
        """
        logger.debug(f"Fetching statistics for customer code: {customer_code}")
        try:
            statistics_data = self.erp_person_service.get_customer_statistics(customer_code, is_admin)

            if not statistics_data:
                 logger.warning(f"Statistics not found for customer code: {customer_code}")
                 # Raise NotFoundError instead of returning empty dict/None from service layer
                 raise NotFoundError(f"Statistics not found for customer code {customer_code}.")

            formatted_statistics = self._format_statistics(statistics_data)
            logger.info(f"Successfully fetched statistics for customer code: {customer_code}")
            return formatted_statistics

        except NotFoundError:
             raise # Re-raise NotFoundError
        except Exception as e:
            logger.error(f"Error fetching statistics for customer code {customer_code}: {e}", exc_info=True)
            raise ServiceError(f"Failed to retrieve customer statistics: {e}") from e

    # --- Private Formatting Helpers ---

    def _format_customer_data(self, customer: Union[IndividualDataModel, LegalEntityDataModel], customer_type: str) -> Dict[str, Any]:
        """Formats the raw customer data model into a dictionary for API response."""
        common_data = {
            "code": customer.code,
            "status": "Inactive" if customer.is_inactive else "Active",
            "registered_at": customer.insert_date, # Consider parsing/formatting date
            "address": self._format_address(customer.addresses),
            "phones": self._format_phones(customer.phones),
            "emails": self._format_emails(customer.emails),
            "is_customer": getattr(customer, 'is_customer', None), # Use getattr for safety
            "is_supplier": getattr(customer, 'is_supplier', None),
        }

        if customer_type == "PF" and isinstance(customer, IndividualDataModel):
            return {
                **common_data,
                "customer_type": "PF",
                "name": customer.name,
                "cpf": customer.cpf,
                "rg": customer.rg,
                "rg_issuer": customer.rg_federal_agency,
                "birth_date": customer.birth_date, # Consider parsing/formatting date
                "is_employee": customer.is_employee,
                "registered_by_branch": customer.branch_insert_code,
                # Add other PF specific fields as needed
            }
        elif customer_type == "PJ" and isinstance(customer, LegalEntityDataModel):
            return {
                **common_data,
                "customer_type": "PJ",
                "legal_name": customer.name, # Razao Social
                "trade_name": customer.fantasy_name, # Nome Fantasia
                "cnpj": customer.cnpj,
                "state_registration": customer.number_state_registration,
                "state_registration_uf": customer.uf,
                "foundation_date": customer.date_foundation, # Consider parsing/formatting date
                "share_capital": customer.share_capital,
                "is_representative": customer.is_representative,
                # Add other PJ specific fields as needed
            }
        else:
            # Should not happen if logic is correct, but handle defensively
            logger.error(f"Mismatch between customer_type '{customer_type}' and customer data type '{type(customer)}'")
            raise ServiceError("Internal error formatting customer data.")


    # Note the corrected type hints below using the imported types
    def _format_address(self, addresses: List[Any]) -> Optional[Dict[str, Any]]:
        """Formats the primary address from the list."""
        if not addresses:
            return None

        # Find default address, fallback to the first one
        # Ensure items in addresses list are not None before accessing attributes
        valid_addresses = [addr for addr in addresses if addr is not None]
        if not valid_addresses:
            return None

        default_address = next((addr for addr in valid_addresses if addr.is_default), None)
        address_to_format = default_address or valid_addresses[0]

        # Combine public_place and address safely
        street = f"{address_to_format.public_place or ''} {address_to_format.address or ''}".strip()

        return {
            "street": street or None, # Return None if both parts were empty
            "number": address_to_format.address_number,
            "neighborhood": address_to_format.neighborhood,
            "city": address_to_format.city_name,
            "state": address_to_format.state_abbreviation,
            "zip_code": address_to_format.cep,
            "type": address_to_format.address_type,
            "complement": address_to_format.complement,
            "reference": address_to_format.reference,
        }

    def _format_phones(self, phones: List[Any]) -> List[Dict[str, Any]]:
        """Formats the list of phones."""
        if not phones:
            return []
        # Ensure phone object is valid before accessing attributes
        return [
            {
                "number": phone.number,
                "type": phone.type_name,
                "is_default": phone.is_default
            } for phone in phones if phone and hasattr(phone, 'number')
        ]

    def _format_emails(self, emails: List[Any]) -> List[Dict[str, Any]]:
        """Formats the list of emails."""
        if not emails:
            return []
        # Ensure email object is valid before accessing attributes
        return [
            {
                "email": email.email,
                "type": email.type_name,
                "is_default": email.is_default
            } for email in emails if email and hasattr(email, 'email')
        ]

    def _format_statistics(self, statistics: PersonStatisticsResponseModel) -> Dict[str, Any]:
        """Formats the statistics data model into a dictionary."""
        if not statistics:
             return {} # Should be caught earlier, but handle defensively

        # Map domain model fields to desired API response fields (snake_case)
        # Consider adding formatting for dates or currency if needed
        return {
            "average_delay_days": statistics.average_delay,
            "max_delay_days": statistics.maximum_delay,
            "total_overdue_value": statistics.total_installments_delayed,
            "overdue_installments_count": statistics.quantity_installments_delayed,
            "average_installment_delay_days": statistics.average_installment_delay,
            "total_purchases_count": statistics.purchase_quantity,
            "total_purchases_value": statistics.total_purchase_value,
            "average_purchase_value": statistics.average_purchase_value,
            "first_purchase_date": statistics.first_purchase_date,
            "first_purchase_value": statistics.first_purchase_value,
            "last_purchase_date": statistics.last_purchase_date,
            "last_purchase_value": statistics.last_purchase_value,
            "biggest_purchase_date": statistics.biggest_purchase_date,
            "biggest_purchase_value": statistics.biggest_purchase_value,
            "total_paid_installments_value": statistics.total_installments_paid,
            "paid_installments_count": statistics.quantity_installments_paid,
            "average_paid_installment_value": statistics.average_value_installments_paid,
            "total_open_installments_value": statistics.total_installments_open,
            "open_installments_count": statistics.quantity_installments_open,
            "average_open_installment_value": statistics.average_installments_open,
            "last_paid_invoice_value": statistics.last_invoice_paid_value,
            "last_paid_invoice_date": statistics.last_invoice_paid_date
        }