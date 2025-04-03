# src/services/accounts_receivable_service.py
# Contém a lógica de negócios para o módulo de Contas a Receber.

import base64
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple, Set, Union
from src.erp_integration.erp_accounts_receivable_service import ErpAccountsReceivableService
from src.erp_integration.erp_person_service import ErpPersonService
from src.domain.accounts_receivable import (
    DocumentChangeModel, DocumentRequestModel, DocumentFilterModel, DocumentModel, DocumentResponseModel,
    BankSlipRequestModel, AccountsReceivableTomasResponseModel, FormattedReceivableListItem,
    CalculatedValuesModel, InvoiceDataModel
)
from src.domain.person import IndividualDataModel, LegalEntityDataModel
from src.utils.logger import logger
from src.api.errors import ServiceError, NotFoundError, ValidationError, ErpIntegrationError
from src.config import config
from src.utils.pdf_utils import decode_base64_to_bytes

class AccountsReceivableService:
    """
    Camada de serviço para lidar com operações de Contas a Receber.
    """
    def __init__(self,
                 erp_ar_service: ErpAccountsReceivableService,
                 erp_person_service: ErpPersonService):
        self.erp_ar_service = erp_ar_service
        self.erp_person_service = erp_person_service
        logger.info("AccountsReceivableService inicializado.")

    def _parse_and_validate_filters(self, raw_filters: Optional[Dict[str, Any]]) -> Optional[DocumentFilterModel]:
        """Analisa o dicionário de filtros brutos no DocumentFilterModel, realizando validação."""
        if not raw_filters or not isinstance(raw_filters, dict):
            return None

        filter_args: Dict[str, Any] = {}

        try:
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
                        raise ValidationError(f"Filtro '{raw_key}' deve ser uma lista de inteiros.")
                    if value:
                        filter_args[model_key] = value

            list_str_keys = {'customerCpfCnpjList': 'customer_cpf_cnpj_list'}
            for raw_key, model_key in list_str_keys.items():
                value = raw_filters.get(raw_key)
                if value is not None:
                    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                        raise ValidationError(f"Filtro '{raw_key}' deve ser uma lista de strings.")
                    if value:
                        filter_args[model_key] = value

            list_float_keys = {'receivableCodeList': 'receivable_code_list', 'ourNumberList': 'our_number_list'}
            for raw_key, model_key in list_float_keys.items():
                value = raw_filters.get(raw_key)
                if value is not None:
                    if not isinstance(value, list) or not all(isinstance(x, (int, float)) for x in value):
                        raise ValidationError(f"Filtro '{raw_key}' deve ser uma lista de números.")
                    if value:
                        filter_args[model_key] = [float(x) for x in value]

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
                         raise ValidationError(f"Formato de data inválido para o filtro '{raw_key}': {value}. Use ISO 8601.")

            bool_keys = {'hasOpenInvoices': 'has_open_invoices'}
            for raw_key, model_key in bool_keys.items():
                value = raw_filters.get(raw_key)
                if value is not None:
                    if not isinstance(value, bool):
                        raise ValidationError(f"Filtro '{raw_key}' deve ser um booleano (true/false).")
                    filter_args[model_key] = value

            simple_int_keys = {
                'commissionedCode': 'commissioned_code', 'closingCodeCommission': 'closing_code_commission',
                'closingCompanyCommission': 'closing_company_commission', 'closingCommissionedCode': 'closing_commissioned_code'
            }
            for raw_key, model_key in simple_int_keys.items():
                value = raw_filters.get(raw_key)
                if value is not None:
                    if not isinstance(value, int): raise ValidationError(f"Filtro '{raw_key}' deve ser um inteiro.")
                    filter_args[model_key] = value

            simple_str_keys = {
                'commissionedCpfCnpj': 'commissioned_cpf_cnpj', 'closingCommissionedCpfCnpj': 'closing_commissioned_cpf_cnpj'
            }
            for raw_key, model_key in simple_str_keys.items():
                value = raw_filters.get(raw_key)
                if value is not None:
                    if not isinstance(value, str): raise ValidationError(f"Filtro '{raw_key}' deve ser uma string.")
                    filter_args[model_key] = value

            change_data = raw_filters.get('change')
            if change_data is not None:
                if not isinstance(change_data, dict):
                    raise ValidationError("Filtro 'change' deve ser um objeto.")
                change_model = DocumentChangeModel.from_dict(change_data)
                if change_model:
                    filter_args['change'] = change_model #

            # --- Instanciar o dataclass congelado UMA VEZ com todos os args ---
            if not filter_args:
                return None

            parsed = DocumentFilterModel(**filter_args)
            logger.debug(f"Filtros analisados: {parsed.to_dict()}")
            return parsed

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Erro ao analisar filtros: {e}", exc_info=True)
            raise ValidationError(f"Formato de filtro inválido: {e}")


    def _fetch_customer_names(self, documents: List[DocumentModel]) -> Dict[int, str]:
        """Busca nomes para clientes únicos presentes na lista de documentos."""
        customer_ids: Set[int] = set()
        for doc in documents:
            if doc.customer_code:
                customer_ids.add(doc.customer_code)

        if not customer_ids:
            return {}

        logger.debug(f"Buscando nomes para {len(customer_ids)} códigos de cliente únicos.")
        names_map: Dict[int, str] = {}
        # Otimização Potencial: Requisição em lote para a API de Pessoas, se suportado.
        # Por enquanto, busca um por um. Considere adicionar cache aqui (nível de requisição ou mais longo).
        for code in customer_ids:
            name = "Nome Não Encontrado"
            try:
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
                 logger.warning(f"Falha ao buscar nome para o código de cliente {code}: {e.message}")
            except Exception as e:
                 logger.error(f"Erro inesperado ao buscar nome para o código de cliente {code}: {e}", exc_info=True)

        logger.debug(f"Nomes buscados para {len(names_map)} clientes.")
        return names_map

    def _format_receivable_list_item(self, doc: DocumentModel, customer_names: Dict[int, str]) -> FormattedReceivableListItem:
        """Formata um único DocumentModel, aplicando lógica condicional para valores calculados."""

        # Obter número da nota fiscal
        invoice_number = None
        if doc.invoice and doc.invoice[0]:
             invoice_number = doc.invoice[0].invoice_code

        # Obter nome do cliente
        cust_name = customer_names.get(doc.customer_code, "Nome Indisponível") if doc.customer_code else "Cliente Inválido"

        # --- Determinar Status do Título ---
        is_paid = doc.discharge_type != 0 or doc.payment_date is not None
        is_overdue = False
        current_date = date.today() # Usa date para comparação com expired_date

        if doc.expired_date and not is_paid:
            try:
                # Extrai apenas a parte da data para comparação
                expired_dt = datetime.fromisoformat(doc.expired_date.split('T')[0]).date()
                is_overdue = expired_dt < current_date
            except (ValueError, TypeError):
                logger.warning(f"Não foi possível analisar expired_date: {doc.expired_date} para o doc {doc.receivable_code}/{doc.installment_code}")

        # --- Inicializar valores formatados ---
        days_late = None
        value_corrected = None
        increase = 0.0
        rebate = 0.0
        calc_vals: Optional[CalculatedValuesModel] = doc.calculated_values # Mantém referência

        # --- Aplicar Lógica Condicional baseada no Status ---
        # Usar valores calculados (calculateValue) se o título estiver aberto E vencido
        use_calculated_for_current = is_overdue and calc_vals is not None

        if use_calculated_for_current:
            # *** Usa calculateValue para títulos Abertos e Vencidos ***
            logger.debug(f"Doc {doc.receivable_code}/{doc.installment_code}: Usando calculateValue (Atualmente Vencido)")
            days_late = calc_vals.days_late
            value_corrected = calc_vals.corrected_value
            # Combina acréscimo/juros/multa de calculateValue
            increase = (calc_vals.increase_value or 0.0) + \
                       (calc_vals.interest_value or 0.0) + \
                       (calc_vals.fine_value or 0.0)
            # Usa desconto do contexto de calculateValue
            rebate = (calc_vals.discount_value or 0.0)

        else:
            # *** Usa campos diretos para títulos Pagos ou Ainda Não Vencidos ***
            logger.debug(f"Doc {doc.receivable_code}/{doc.installment_code}: Usando campos diretos (Pago ou Não Vencido)")
            # days_late e value_corrected permanecem None
            # Usa juros/acréscimos históricos registrados no próprio documento
            increase = (doc.interest_value or 0.0) + (doc.assessment_value or 0.0)
            # Usa abatimento/desconto históricos registrados no próprio documento
            rebate = (doc.rebate_value or 0.0) + (doc.discount_value or 0.0)

        # --- Formatar acréscimo/abatimento final (mostrar nulo se zero) ---
        value_increase = increase if increase > 0 else None
        value_rebate = rebate if rebate > 0 else None


        # --- Instanciar FormattedReceivableListItem ---
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
            # --- Usar valores calculados condicionalmente ---
            days_late=days_late,
            value_increase=value_increase,
            value_rebate=value_rebate,
            value_corrected=value_corrected,
            # --- Mapear outros campos ---
            status=doc.status,
            document_type=doc.document_type,
            billing_type=doc.billing_type,
            discharge_type=doc.discharge_type,
            charge_type=doc.charge_type
        )

    def search_receivables(self, raw_filters: Optional[Dict[str, Any]], page: int, page_size: int, expand: Optional[str], order: Optional[str]) -> Dict[str, Any]:
        """
        Busca por documentos de contas a receber, aplica filtro de filial padrão,
        enriquece com nomes de clientes e formata os resultados.
        """
        logger.info(f"Buscando contas a receber. Página: {page}, Tamanho: {page_size}, Filtros: {raw_filters is not None}, Expandir: {expand}, Ordem: {order}")

        if page < 1: page = 1
        if page_size < 1 or page_size > 100:
             logger.warning(f"Ajustando tamanho da página de {page_size} para 100 (limite da API).")
             page_size = 100

        # Sempre expandir calculateValue e invoice para os campos necessários
        expand_list = set(item.strip() for item in expand.split(',') if item.strip()) if expand else set()
        expand_list.add("calculateValue")
        expand_list.add("invoice")
        final_expand_str = ",".join(sorted(list(expand_list)))

        try:
            # 1. Analisar e Validar Filtros do Usuário
            parsed_user_filters = self._parse_and_validate_filters(raw_filters)

            # 2. *** Garantir que o Filtro de Código da Filial Esteja Presente ***
            filter_for_request: DocumentFilterModel
            default_branch = [config.COMPANY_CODE] # Usa código da empresa da config

            if parsed_user_filters is None:
                # Nenhum filtro fornecido pelo usuário, cria filtro apenas com filial padrão
                logger.debug("Nenhum filtro de usuário fornecido. Aplicando filtro de filial padrão.")
                filter_for_request = DocumentFilterModel(branch_code_list=default_branch)
            elif not parsed_user_filters.branch_code_list:
                # Usuário forneceu filtros, mas não branchCodeList. Adiciona filial padrão.
                logger.debug("Filtros de usuário fornecidos sem branchCodeList. Adicionando filtro de filial padrão.")
                # Como DocumentFilterModel é congelado, cria um novo mesclando
                # Importante: to_dict() retorna chaves em camelCase (formato API), mas precisamos de snake_case para o modelo
                filter_dict = parsed_user_filters.to_dict()

                # Convertendo de volta para snake_case para o DocumentFilterModel
                filter_args = {}
                # Mapeamentos de camelCase para snake_case (necessário para reconstruir o modelo)
                all_keys_map = {
                     'branchCodeList': 'branch_code_list', 'customerCodeList': 'customer_code_list',
                     'statusList': 'status_list', 'documentTypeList': 'document_type_list',
                     'billingTypeList': 'billing_type_list', 'dischargeTypeList': 'discharge_type_list',
                     'chargeTypeList': 'charge_type_list',
                     'customerCpfCnpjList': 'customer_cpf_cnpj_list',
                     'receivableCodeList': 'receivable_code_list', 'ourNumberList': 'our_number_list',
                     'startExpiredDate': 'start_expired_date', 'endExpiredDate': 'end_expired_date',
                     'startPaymentDate': 'start_payment_date', 'endPaymentDate': 'end_payment_date',
                     'startIssueDate': 'start_issue_date', 'endIssueDate': 'end_issue_date',
                     'startCreditDate': 'start_credit_date', 'endCreditDate': 'end_credit_date',
                     'closingDateCommission': 'closing_date_commission',
                     'hasOpenInvoices': 'has_open_invoices',
                     'commissionedCode': 'commissioned_code', 'closingCodeCommission': 'closing_code_commission',
                     'closingCompanyCommission': 'closing_company_commission', 'closingCommissionedCode': 'closing_commissioned_code',
                     'commissionedCpfCnpj': 'commissioned_cpf_cnpj', 'closingCommissionedCpfCnpj': 'closing_commissioned_cpf_cnpj'
                 }

                for camel_key, snake_key in all_keys_map.items():
                    if camel_key in filter_dict:
                        filter_args[snake_key] = filter_dict[camel_key]

                # Tratar a chave 'change' separadamente, pois é um objeto
                if 'change' in filter_dict and filter_dict['change']:
                    filter_args['change'] = DocumentChangeModel.from_dict(filter_dict['change'])
                filter_args['branch_code_list'] = default_branch
                filter_for_request = DocumentFilterModel(**filter_args)
            else:
                logger.debug("Usuário forneceu branchCodeList nos filtros.")
                filter_for_request = parsed_user_filters

            # 3. Preparar Payload da Requisição ERP usando o filtro garantido
            request_payload = DocumentRequestModel(
                filter=filter_for_request,
                expand=final_expand_str,
                order=order,
                page=page,
                page_size=page_size
            )

            # 4. Chamar Serviço ERP
            erp_response_dict = self.erp_ar_service.search_documents(request_payload.to_dict())

            # 5. Analisar Resposta ERP
            erp_response = DocumentResponseModel.from_dict(erp_response_dict)
            if not erp_response:
                raise ServiceError("Falha ao analisar a resposta do ERP para a busca de contas a receber.")

            # 6. Buscar Nomes dos Clientes
            customer_names = self._fetch_customer_names(erp_response.items)

            # 7. Formatar Resultados
            formatted_items = [self._format_receivable_list_item(doc, customer_names) for doc in erp_response.items]

            # 8. Construir Resposta Final da API
            result = {
                "items": [item.to_dict() for item in formatted_items],
                "page": page,
                "pageSize": page_size,
                "totalItems": erp_response.total_items,
                "totalPages": erp_response.total_pages,
                "hasNext": erp_response.has_next
            }
            logger.info(f"Buscou e formatou com sucesso {len(formatted_items)} contas a receber para a página {page}. Total: {erp_response.total_items}")
            return result

        except (ValidationError, NotFoundError) as e:
            logger.warning(f"Busca de contas a receber falhou: {e}")
            raise e
        except ErpIntegrationError as e:
             logger.error(f"Erro de integração com o ERP durante a busca de contas a receber: {e}", exc_info=False)
             raise ServiceError(f"Falha ao comunicar com o ERP para a busca de contas a receber: {e.message}") from e
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar contas a receber: {e}", exc_info=True)
            raise ServiceError(f"Ocorreu um erro inesperado ao buscar contas a receber: {e}") from e

    def generate_boleto_pdf(self, request_data: Dict[str, Any]) -> bytes:
        """
        Gera o PDF do Boleto Bancário para uma parcela específica de contas a receber.
        """
        logger.info(f"Requisição para gerar PDF do boleto recebida: {request_data}")

        required = ['branchCode', 'customerCode', 'receivableCode', 'installmentNumber']
        missing = [field for field in required if field not in request_data]
        if missing:
            raise ValidationError(f"Campos obrigatórios ausentes para geração do boleto: {', '.join(missing)}")

        try:
            boleto_request = BankSlipRequestModel(
                branch_code=int(request_data['branchCode']),
                customer_code=int(request_data['customerCode']),
                receivable_code=int(request_data['receivableCode']),
                installment_number=int(request_data['installmentNumber']),
                customer_cpf_cnpj=request_data.get('customerCpfCnpj')
            )
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Tipo de dado inválido nos parâmetros da requisição do boleto: {e}")


        try:
            # 1. Chamar Serviço ERP
            erp_response_dict = self.erp_ar_service.get_bank_slip(boleto_request.to_dict())

            # 2. Analisar Resposta ERP
            tomas_response = AccountsReceivableTomasResponseModel.from_dict(erp_response_dict)
            if not tomas_response:
                 raise ServiceError("Falha ao analisar a resposta do ERP para a geração do boleto.")

            status_lower = tomas_response.uniface_response_status.lower() if tomas_response.uniface_response_status else ""
            if tomas_response.uniface_response_status and status_lower not in ('ok', 'success'):
                 err_msg = tomas_response.uniface_message or "Erro desconhecido do Uniface"
                 logger.error(f"Geração do boleto falhou no Uniface. Status: {tomas_response.uniface_response_status}, Mensagem: {err_msg}")
                 raise ServiceError(f"Geração do boleto falhou no ERP ({tomas_response.uniface_response_status}): {err_msg}")

            # 3. Extrair Conteúdo Base64
            pdf_base64 = tomas_response.content
            if not pdf_base64:
                logger.error("Resposta do ERP para geração do boleto está sem o 'content' (PDF Base64). Status foi: %s", tomas_response.uniface_response_status)
                raise NotFoundError("O PDF do boleto não pôde ser gerado pelo ERP (conteúdo ausente).")

            # 4. Decodificar Base64 para Bytes
            pdf_bytes = decode_base64_to_bytes(pdf_base64)
            logger.info("PDF do Boleto gerado e decodificado com sucesso.")
            return pdf_bytes

        except (ValidationError, NotFoundError) as e:
            logger.warning(f"Geração do boleto falhou: {e}")
            raise e
        except ErpIntegrationError as e:
             logger.error(f"Erro de integração com o ERP durante a geração do boleto: {e}", exc_info=False)
             raise ServiceError(f"Falha na comunicação com o ERP durante a geração do boleto: {e.message}") from e
        except ServiceError as e:
             raise e
        except Exception as e:
            logger.error(f"Erro inesperado ao gerar PDF do boleto: {e}", exc_info=True)
            if isinstance(e, ServiceError):
                raise
            else:
                raise ServiceError(f"Ocorreu um erro inesperado ao gerar o boleto: {e}") from e

