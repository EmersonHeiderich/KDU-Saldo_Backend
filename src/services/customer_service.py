from typing import Optional, Dict, Any, Union, List
from src.domain.person import IndividualDataModel, LegalEntityDataModel, PersonStatisticsResponseModel
from src.erp_integration.erp_person_service import ErpPersonService
from src.utils.logger import logger
from src.api.errors import NotFoundError, ServiceError, ValidationError

class CustomerService:
    def __init__(self, erp_person_service: ErpPersonService):
        self.erp_person_service = erp_person_service
        logger.info("CustomerService inicializado.")

    def get_customer_details(self, search_term: str, search_type: Optional[str] = None) -> Dict[str, Any]:
        logger.debug(f"Buscando detalhes do cliente para: '{search_term}', tipo: {search_type}")
        search_term = str(search_term).strip()
        customer_data: Optional[Union[IndividualDataModel, LegalEntityDataModel]] = None
        customer_type: str = ""

        try:
            if search_term.isdigit() and len(search_term) <= 9:
                if not search_type or search_type.upper() not in ("PF", "PJ"):
                    raise ValidationError("O campo 'search_type' ('PF' ou 'PJ') é obrigatório ao buscar por código.")
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
                raise ValidationError("Formato inválido para 'search_term'. Deve ser Código (com tipo 'PF'/'PJ'), CPF (11 dígitos) ou CNPJ (14 dígitos).")

            if not customer_data:
                logger.warning(f"Cliente não encontrado para: '{search_term}', tipo: {search_type}")
                raise NotFoundError("Cliente não encontrado.")

            formatted_response = self._format_customer_data(customer_data, customer_type)
            logger.info(f"Detalhes do cliente obtidos com sucesso: {customer_data.code}")
            return formatted_response

        except (NotFoundError, ValidationError) as e:
            raise e
        except Exception as e:
            logger.error(f"Erro ao buscar detalhes do cliente '{search_term}': {e}", exc_info=True)
            raise ServiceError(f"Falha ao recuperar detalhes do cliente: {e}") from e

    def get_customer_statistics(self, customer_code: int, is_admin: bool) -> Dict[str, Any]:
        logger.debug(f"Buscando estatísticas para o cliente: {customer_code}")
        try:
            statistics_data = self.erp_person_service.get_customer_statistics(customer_code, is_admin)

            if not statistics_data:
                logger.warning(f"Estatísticas não encontradas para o cliente: {customer_code}")
                raise NotFoundError(f"Estatísticas não encontradas para o cliente {customer_code}.")

            formatted_statistics = self._format_statistics(statistics_data)
            logger.info(f"Estatísticas do cliente obtidas com sucesso: {customer_code}")
            return formatted_statistics

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Erro ao buscar estatísticas do cliente {customer_code}: {e}", exc_info=True)
            raise ServiceError(f"Falha ao recuperar estatísticas do cliente: {e}") from e

    def _format_customer_data(self, customer: Union[IndividualDataModel, LegalEntityDataModel], customer_type: str) -> Dict[str, Any]:
        common_data = {
            "code": customer.code,
            "status": "Inativo" if customer.is_inactive else "Ativo",
            "registered_at": customer.insert_date,
            "address": self._format_address(customer.addresses),
            "phones": self._format_phones(customer.phones),
            "emails": self._format_emails(customer.emails),
            "is_customer": getattr(customer, 'is_customer', None),
            "is_supplier": getattr(customer, 'is_supplier', None),
        }

        if customer_type == "PF" and isinstance(customer, IndividualDataModel):
            return {**common_data, "customer_type": "PF", "name": customer.name, "cpf": customer.cpf, "rg": customer.rg, "rg_issuer": customer.rg_federal_agency, "birth_date": customer.birth_date, "is_employee": customer.is_employee, "registered_by_branch": customer.branch_insert_code}
        elif customer_type == "PJ" and isinstance(customer, LegalEntityDataModel):
            return {**common_data, "customer_type": "PJ", "legal_name": customer.name, "trade_name": customer.fantasy_name, "cnpj": customer.cnpj, "state_registration": customer.number_state_registration, "state_registration_uf": customer.uf, "foundation_date": customer.date_foundation, "share_capital": customer.share_capital, "is_representative": customer.is_representative}
        else:
            logger.error(f"Inconsistência entre tipo '{customer_type}' e tipo de dados '{type(customer)}'")
            raise ServiceError("Erro interno ao formatar os dados do cliente.")

    def _format_address(self, addresses: List[Any]) -> Optional[Dict[str, Any]]:
        if not addresses:
            return None
        valid_addresses = [addr for addr in addresses if addr is not None]
        if not valid_addresses:
            return None
        default_address = next((addr for addr in valid_addresses if addr.is_default), None)
        address_to_format = default_address or valid_addresses[0]
        street = f"{address_to_format.public_place or ''} {address_to_format.address or ''}".strip()
        return {"street": street or None, "number": address_to_format.address_number, "neighborhood": address_to_format.neighborhood, "city": address_to_format.city_name, "state": address_to_format.state_abbreviation, "zip_code": address_to_format.cep, "type": address_to_format.address_type, "complement": address_to_format.complement, "reference": address_to_format.reference}

    def _format_phones(self, phones: List[Any]) -> List[Dict[str, Any]]:
        return [{"number": phone.number, "type": phone.type_name, "is_default": phone.is_default} for phone in phones if phone and hasattr(phone, 'number')]

    def _format_emails(self, emails: List[Any]) -> List[Dict[str, Any]]:
        return [{"email": email.email, "type": email.type_name, "is_default": email.is_default} for email in emails if email and hasattr(email, 'email')]

    def _format_statistics(self, statistics: PersonStatisticsResponseModel) -> Dict[str, Any]:
        return {"average_delay_days": statistics.average_delay, "max_delay_days": statistics.maximum_delay, "total_overdue_value": statistics.total_installments_delayed, "overdue_installments_count": statistics.quantity_installments_delayed, "total_purchases_count": statistics.purchase_quantity, "total_purchases_value": statistics.total_purchase_value, "average_purchase_value": statistics.average_purchase_value}
