# src/database/fiscal_repository.py
# Handles database operations for Fiscal data using SQLAlchemy ORM.

import re # Importar regex para o range
from datetime import datetime, timezone, date, time # Adicionado timezone, date, time
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func, delete, update, and_, or_ # Importar and_, or_
from sqlalchemy.orm import Session, joinedload, selectinload, make_transient
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .base_repository import BaseRepository
from src.domain.fiscal_orm import (
    NotaFiscalOrm, NotaFiscalItemOrm, NotaFiscalItemProdutoOrm,
    NotaFiscalPagamentoOrm, NotaFiscalPedidoVendaOrm, NotaFiscalObservacaoOrm
)
from src.utils.logger import logger
from src.api.errors import DatabaseError, NotFoundError, ValidationError
from src.utils.data_conversion import safe_float, safe_int, parse_optional_date, parse_optional_datetime, parse_optional_time

class FiscalRepository(BaseRepository):
    """
    Repository for managing Fiscal data (NotaFiscal and related entities) using ORM Sessions.
    Methods expect a Session object to be passed in.
    """

    # --- Upsert Logic ---
    def upsert_invoice(self, db: Session, invoice_data: Dict[str, Any]) -> Optional[NotaFiscalOrm]:
        """
        Creates or updates a Nota Fiscal and its related entities based on ERP data.
        Prioritizes lookup by (branch_code, invoice_sequence, invoice_date). Handles potential
        duplicates from ERP pagination by checking access_key if primary lookup fails.
        More robust handling of potential duplicates within the same session flush.

        Args:
            db: The SQLAlchemy Session.
            invoice_data: A dictionary representing a single invoice item from the ERP API response.

        Returns:
            The created or updated NotaFiscalOrm object, or None if essential data is missing or skipped.
        """
        if not isinstance(invoice_data, dict):
            logger.warning(f"Pulando upsert da nota fiscal: dados recebidos não são um dicionário: {invoice_data}")
            return None

        branch_code = safe_int(invoice_data.get('branchCode'))
        invoice_sequence = safe_int(invoice_data.get('invoiceSequence'))
        invoice_code = safe_int(invoice_data.get('invoiceCode')) # Usado para logs e busca secundária
        access_key = (invoice_data.get('eletronic') or {}).get('accessKey')
        invoice_date = parse_optional_date(invoice_data.get('invoiceDate')) # Adicionado invoice_date à chave natural

        # Validação da chave natural primária
        if branch_code is None or invoice_sequence is None or invoice_date is None:
            logger.warning(f"Pulando upsert da nota fiscal: Faltando branchCode ({branch_code}), invoiceSequence ({invoice_sequence}) ou invoiceDate ({invoice_date}).")
            return None

        # --- Chave Natural Primária ---
        natural_key_filter = (
            NotaFiscalOrm.branch_code == branch_code,
            NotaFiscalOrm.invoice_sequence == invoice_sequence,
            NotaFiscalOrm.invoice_date == invoice_date
        )
        existing_invoice: Optional[NotaFiscalOrm] = None
        created_new = False

        try:
            # --- Busca Robusta ---
            # 1. Tentar buscar na sessão atual primeiro (caso já processado no batch)
            for obj in db.new: # Objetos a serem inseridos
                if (isinstance(obj, NotaFiscalOrm) and
                        obj.branch_code == branch_code and
                        obj.invoice_sequence == invoice_sequence and
                        obj.invoice_date == invoice_date):
                    existing_invoice = obj
                    logger.debug(f"Nota fiscal {branch_code}/{invoice_sequence}/{invoice_date} já pendente para inserção na sessão.")
                    break
            if not existing_invoice:
                 for obj in db.dirty: # Objetos a serem atualizados
                     if (isinstance(obj, NotaFiscalOrm) and
                            obj.branch_code == branch_code and
                            obj.invoice_sequence == invoice_sequence and
                            obj.invoice_date == invoice_date):
                          existing_invoice = obj
                          logger.debug(f"Nota fiscal {branch_code}/{invoice_sequence}/{invoice_date} já pendente para atualização na sessão.")
                          break

            # 2. Se não estiver na sessão, buscar no banco pela chave natural
            if not existing_invoice:
                stmt_natural = select(NotaFiscalOrm).where(and_(*natural_key_filter))
                existing_invoice = db.scalars(stmt_natural).one_or_none()

            # 3. Se ainda não encontrado E houver access_key, tentar por access_key no banco
            #    (Cobre casos de inconsistência na chave natural vs access_key ou erros anteriores)
            if not existing_invoice and access_key:
                stmt_access_key = select(NotaFiscalOrm).where(NotaFiscalOrm.access_key == access_key)
                invoice_by_key = db.scalars(stmt_access_key).one_or_none()
                if invoice_by_key:
                    logger.warning(f"Nota fiscal encontrada pela access_key '{access_key}' mas não pela chave natural ({branch_code}/{invoice_sequence}/{invoice_date}). Usando registro existente encontrado pela chave.")
                    existing_invoice = invoice_by_key

            # --- Helper Function to Map Data ---
            def map_data_to_invoice(target: NotaFiscalOrm, data: Dict[str, Any]):
                eletronic_data = data.get('eletronic') or {}
                shipping_data = data.get('shippingCompany') or {}

                target.branch_cnpj = data.get('branchCnpj')
                target.person_code = safe_int(data.get('personCode'))
                target.person_name = data.get('personName')
                target.invoice_code = safe_int(data.get('invoiceCode'))
                target.serial_code = data.get('serialCode')
                target.invoice_status = data.get('invoiceStatus')
                target.access_key = eletronic_data.get('accessKey')
                target.electronic_invoice_status = eletronic_data.get('electronicInvoiceStatus')
                target.receipt = str(eletronic_data.get('receipt')) if eletronic_data.get('receipt') is not None else None
                target.receivement_date = parse_optional_datetime(eletronic_data.get('receivementDate'))
                target.disable_protocol = eletronic_data.get('disableProtocol')
                target.disable_date = parse_optional_datetime(eletronic_data.get('disableDate'))
                target.transaction_branch_code = safe_int(data.get('transactionBranchCode'))
                target.transaction_date = parse_optional_date(data.get('transactionDate'))
                target.transaction_code = safe_int(data.get('transactionCode'))
                target.inclusion_component_code = data.get('inclusionComponentCode')
                target.user_code = safe_int(data.get('userCode'))
                target.origin = data.get('origin')
                target.document_type = safe_int(data.get('documentType'))
                target.operation_type = data.get('operationType')
                target.operation_code = safe_int(data.get('operationCode'))
                target.operation_name = data.get('operatioName') # Potential typo in source data 'operatioName'?
                target.invoice_date = parse_optional_date(data.get('invoiceDate')) # Já validado
                target.issue_date = parse_optional_date(data.get('issueDate'))
                target.release_date = parse_optional_date(data.get('releaseDate'))
                target.exit_time = parse_optional_time(data.get('exitTime'))
                target.lastchange_date = parse_optional_datetime(data.get('lastchangeDate'))
                target.payment_condition_code = safe_int(data.get('paymentConditionCode'))
                target.payment_condition_name = data.get('paymentConditionName')
                target.discount_percentage = safe_float(data.get('discountPercentage'))
                target.quantity = safe_float(data.get('quantity'))
                target.product_value = safe_float(data.get('productValue'))
                target.additional_value = safe_float(data.get('additionalValue'))
                target.shipping_value = safe_float(data.get('shippingValue'))
                target.insurance_value = safe_float(data.get('insuranceValue'))
                target.ipi_value = safe_float(data.get('ipiValue'))
                target.base_icms_value = safe_float(data.get('baseIcmsValue'))
                target.icms_value = safe_float(data.get('icmsValue'))
                target.icms_subst_value = safe_float(data.get('icmsSubStValue')) # Typo? 'icmsSubstValue'?
                target.total_value = safe_float(data.get('totalValue'))
                target.shipping_company_code = safe_int(shipping_data.get('shippingCompanyCode'))
                target.shipping_company_name = shipping_data.get('shippingCompanyName')
                target.freight_type = shipping_data.get('freightType') # Source had 'freitghtType'?
                target.freight_type_redispatch = shipping_data.get('freightTypeRedispatch') # Source had 'freitghtTypeRedispatch'?
                target.freight_value = safe_float(shipping_data.get('freightValue'))
                target.package_number = safe_int(shipping_data.get('packageNumber'))
                target.gross_weight = safe_float(shipping_data.get('grossWeight'))
                target.net_weight = safe_float(shipping_data.get('netWeight'))
                target.species = shipping_data.get('species')
                target.terminal_code = safe_int(data.get('terminalCode'))
                target.observation_nfe = data.get('observationNFE') # Campo de observação único

            # --- Atualizar ou Criar ---
            if existing_invoice:
                # --- ATUALIZAÇÃO ---
                new_last_change = parse_optional_datetime(invoice_data.get('lastchangeDate'))
                should_update = True
                if existing_invoice.lastchange_date and new_last_change:
                    # Normalizar para UTC ou comparar como naive (se ambos forem naive)
                    existing_ts = existing_invoice.lastchange_date
                    new_ts = new_last_change
                    if existing_ts.tzinfo and new_ts.tzinfo:
                         if new_ts.astimezone(timezone.utc) <= existing_ts.astimezone(timezone.utc):
                              should_update = False
                    elif not existing_ts.tzinfo and not new_ts.tzinfo:
                         if new_ts <= existing_ts:
                              should_update = False
                    else: # Mistura de naive e aware, assume que deve atualizar
                         logger.warning(f"Comparando timestamp naive e aware para NF {branch_code}/{invoice_sequence}/{invoice_date}. Atualizando por segurança.")

                if not should_update:
                     logger.debug(f"Pulando atualização da nota fiscal {branch_code}/{invoice_sequence}/{invoice_date}, timestamp não alterado ou mais antigo ({new_last_change}).")
                     return existing_invoice

                logger.debug(f"Atualizando nota fiscal existente ID {existing_invoice.id} ({branch_code}/{invoice_sequence}/{invoice_date})")
                invoice = existing_invoice
                map_data_to_invoice(invoice, invoice_data)
                # Limpar filhos ANTES de adicionar novos para evitar duplicatas
                invoice.items.clear()
                invoice.payments.clear()
                invoice.sales_orders.clear()
                invoice.observations.clear()
                # Flush pode ajudar a garantir que deletes ocorram antes de inserts se houver constraints
                # db.flush() # Descomente se necessário, mas pode impactar performance
            else:
                 # --- CRIAÇÃO ---
                 logger.debug(f"Criando nova nota fiscal ({branch_code}/{invoice_sequence}/{invoice_date}, Chave: ...{access_key[-6:] if access_key else 'N/A'})")
                 # Checagem prévia por access_key (melhoria contra race condition/duplicidade)
                 if access_key:
                      stmt_check_key = select(NotaFiscalOrm.id).where(NotaFiscalOrm.access_key == access_key).limit(1)
                      key_already_exists = db.execute(stmt_check_key).scalar_one_or_none()
                      if key_already_exists:
                           logger.warning(f"Access_key duplicada '{access_key}' encontrada antes do INSERT para {branch_code}/{invoice_sequence}/{invoice_date}. Pulando este registro.")
                           return None # Pula esta nota

                 invoice = NotaFiscalOrm(branch_code=branch_code, invoice_sequence=invoice_sequence, invoice_date=invoice_date)
                 map_data_to_invoice(invoice, invoice_data)
                 db.add(invoice)
                 created_new = True # Marca que foi criado

            # --- Handle Children (Processar e associar ao 'invoice' correto) ---

            # Items and their Products
            items_list = invoice_data.get('items')
            if isinstance(items_list, list):
                for item_data in items_list:
                    if not isinstance(item_data, dict): continue
                    item_orm = NotaFiscalItemOrm(
                        nota_fiscal=invoice, # Associação feita aqui
                         sequence=safe_int(item_data.get('sequence')),
                         code=item_data.get('code'), name=item_data.get('name'),
                         ncm=item_data.get('ncm'), cfop=safe_int(item_data.get('cfop')),
                         measure_unit=item_data.get('measureUnit'), quantity=safe_float(item_data.get('quantity')),
                         gross_value=safe_float(item_data.get('grossValue')), discount_value=safe_float(item_data.get('discountValue')),
                         net_value=safe_float(item_data.get('netValue')), unit_gross_value=safe_float(item_data.get('unitGrossValue')),
                         unit_discount_value=safe_float(item_data.get('unitDiscountValue')), unit_net_value=safe_float(item_data.get('unitNetValue')),
                         additional_value=safe_float(item_data.get('additionalValue')), freight_value=safe_float(item_data.get('freightValue')),
                         insurance_value=safe_float(item_data.get('insuranceValue')), additional_item_information=item_data.get('additionalItemInformation')
                    )
                    # Não precisa de db.add(item_orm) por causa do cascade
                    products_list = item_data.get('products')
                    if isinstance(products_list, list):
                         for prod_data in products_list:
                              if not isinstance(prod_data, dict): continue
                              prod_orm = NotaFiscalItemProdutoOrm(
                                  item=item_orm, # Associação feita aqui
                                  product_code=safe_int(prod_data.get('productCode')), product_name=prod_data.get('productName'),
                                  dealer_code=safe_int(prod_data.get('dealerCode')), quantity=safe_float(prod_data.get('quantity')),
                                  unit_gross_value=safe_float(prod_data.get('unitGrossValue')), unit_discount_value=safe_float(prod_data.get('unitDiscountValue')),
                                  unit_net_value=safe_float(prod_data.get('unitNetValue')), gross_value=safe_float(prod_data.get('grossValue')),
                                  discount_value=safe_float(prod_data.get('discountValue')), net_value=safe_float(prod_data.get('netValue'))
                              )
                              # Associação via backref/relationship, não precisa add
                              item_orm.item_products.append(prod_orm)
                    # Associação via backref/relationship
                    invoice.items.append(item_orm)

            # Payments
            payments_list = invoice_data.get('payments')
            if isinstance(payments_list, list):
                for payment_data in payments_list:
                    if not isinstance(payment_data, dict): continue
                    payment_orm = NotaFiscalPagamentoOrm(
                        nota_fiscal=invoice, # Associação
                        document_number=safe_int(payment_data.get('documentNumber')), expiration_date=parse_optional_datetime(payment_data.get('expirationDate')),
                        payment_value=safe_float(payment_data.get('paymentValue')), document_type_code=safe_int(payment_data.get('documentTypeCode')),
                        document_type=payment_data.get('documentType'), installment=safe_int(payment_data.get('installment')),
                        bearer_code=safe_int(payment_data.get('bearerCode')), bearer_name=payment_data.get('bearerName')
                    )
                    invoice.payments.append(payment_orm) # Associação

            # Sales Orders
            sales_order_list = invoice_data.get('salesOrder')
            if isinstance(sales_order_list, list):
                for order_data in sales_order_list:
                    if not isinstance(order_data, dict): continue
                    order_orm = NotaFiscalPedidoVendaOrm(
                        nota_fiscal=invoice, # Associação
                        branch_code=safe_int(order_data.get('branchCode')), order_code=safe_int(order_data.get('orderCode')),
                        customer_order_code=order_data.get('customerOrderCode')
                    )
                    invoice.sales_orders.append(order_orm) # Associação

            # Observations (observationNF list)
            observations_list = invoice_data.get('observationNF')
            if isinstance(observations_list, list):
                 for obs_data in observations_list:
                      if not isinstance(obs_data, dict): continue
                      obs_orm = NotaFiscalObservacaoOrm(
                          nota_fiscal=invoice, # Associação
                          observation=obs_data.get('observation'),
                          sequence=safe_int(obs_data.get('sequence'))
                      )
                      invoice.observations.append(obs_orm) # Associação


            # --- Flush Final ---
            # O flush aqui pode detectar UniqueViolations ANTES do commit do batch
            # db.flush() # Descomente se encontrar problemas de integridade complexos
            log_operation = "Criada" if created_new else "Atualizada"
            logger.debug(f"{log_operation} nota fiscal {branch_code}/{invoice_sequence}/{invoice_date} na sessão. Commit pendente.")
            return invoice

        except IntegrityError as e:
            db.rollback() # Rollback da sessão atual para não afetar o resto do batch
            logger.error(f"Erro de integridade do banco de dados durante upsert para nota fiscal {branch_code}/{invoice_sequence}/{invoice_date}: {e}", exc_info=True)
            # Checar constraints específicas se necessário
            # if "uq_nota_fiscal_branch_sequence_date" in str(e.orig) or "ix_nota_fiscal_access_key" in str(e.orig):
            #      logger.warning(f"IntegrityError (chave duplicada?) para nota fiscal {branch_code}/{invoice_sequence}/{invoice_date}. Pulando este registro.")
            #      return None # Pular este item
            # else:
                 # Outro erro de integridade, pode ser melhor propagar
            raise DatabaseError(f"Erro de integridade processando nota fiscal {branch_code}/{invoice_sequence}/{invoice_date}: {e}") from e
        except SQLAlchemyError as e:
            db.rollback() # Rollback da sessão atual
            logger.error(f"Erro de banco de dados durante upsert da nota fiscal {branch_code}/{invoice_sequence}/{invoice_date}: {e}", exc_info=True)
            raise DatabaseError(f"Erro de banco de dados processando nota fiscal {branch_code}/{invoice_sequence}/{invoice_date}: {e}") from e
        except Exception as e:
            db.rollback() # Rollback da sessão atual
            logger.error(f"Erro inesperado durante upsert da nota fiscal {branch_code}/{invoice_sequence}/{invoice_date}: {e}", exc_info=True)
            raise DatabaseError(f"Erro inesperado processando nota fiscal {branch_code}/{invoice_sequence}/{invoice_date}: {e}") from e


    # --- Get Latest Sync Timestamp ---
    def get_latest_sync_timestamp(self, db: Session) -> Optional[datetime]:
        """
        Finds the maximum 'lastchange_date' from the nota_fiscal table.
        """
        logger.debug("Consultando timestamp mais recente de sincronização (max lastchange_date) na tabela nota_fiscal.")
        try:
            stmt = select(func.max(NotaFiscalOrm.lastchange_date))
            latest_timestamp = db.scalar(stmt)
            if latest_timestamp:
                 # Certificar que o timestamp retornado é timezone-aware (UTC)
                 if latest_timestamp.tzinfo is None:
                      logger.warning(f"Timestamp {latest_timestamp} do DB é naive, assumindo UTC.")
                      latest_timestamp = latest_timestamp.replace(tzinfo=timezone.utc)
                 else:
                      latest_timestamp = latest_timestamp.astimezone(timezone.utc)
                 logger.info(f"Timestamp mais recente de sincronização encontrado: {latest_timestamp.isoformat()}")
            else:
                 logger.info("Nenhum timestamp anterior de sincronização encontrado no banco de dados.")
            return latest_timestamp
        except SQLAlchemyError as e:
             logger.error(f"Erro de banco de dados ao obter timestamp mais recente de sincronização: {e}", exc_info=True)
             return None # Retorna None para indicar falha ou ausência
        except Exception as e:
            logger.error(f"Erro inesperado ao obter timestamp mais recente de sincronização: {e}", exc_info=True)
            return None # Retorna None


    # --- Find Invoices Local ---
    def find_invoices_local(self, db: Session, filters: Dict[str, Any], page: int, page_size: int) -> Tuple[List[NotaFiscalOrm], int]:
        """
        Searches for invoices in the LOCAL database based on provided filters.
        Args:
            db: The SQLAlchemy Session.
            filters: Dictionary of filter criteria mapped from API request.
            page: Page number (starting from 1).
            page_size: Number of items per page.
        Returns:
            A tuple containing: (list of NotaFiscalOrm objects, total_count).
        """
        logger.debug(f"Buscando notas fiscais locais com filtros: {filters}, Página: {page}, TamanhoPágina: {page_size}")
        try:
            query = select(NotaFiscalOrm)
            applied_filters = [] # Para logar os filtros aplicados

            # --- Apply Filters ---

            # Filtro por Status (Chave API: 'status', Campo ORM: electronic_invoice_status)
            if 'status' in filters:
                status_input = filters['status']
                if status_input and isinstance(status_input, str):
                    # Divide por vírgula, remove espaços e converte para minúsculo
                    status_list_lower = [s.strip().lower() for s in status_input.split(',') if s.strip()]
                    if status_list_lower:
                        query = query.where(func.lower(NotaFiscalOrm.electronic_invoice_status).in_(status_list_lower))
                        applied_filters.append(f"status IN {status_list_lower}")

            # Filtro por Nome do Destinatário (Chave API: 'recipient_name' - Manter se útil)
            if 'recipient_name' in filters:
                name_filter = filters['recipient_name']
                if name_filter and isinstance(name_filter, str):
                    query = query.where(NotaFiscalOrm.person_name.ilike(f"%{name_filter}%"))
                    applied_filters.append(f"recipient_name LIKE '%{name_filter}%'")

            # Filtro por Número da Nota Fiscal (Chave API: 'invoice_number', Campo ORM: invoice_code)
            if 'invoice_number' in filters:
                num_input = filters['invoice_number']
                if num_input and isinstance(num_input, str):
                    num_input = num_input.strip()
                    # 1. Checar por Range (ex: "100-150")
                    range_match = re.match(r'^(\d+)\s*-\s*(\d+)$', num_input)
                    if range_match:
                        start_num = safe_int(range_match.group(1))
                        end_num = safe_int(range_match.group(2))
                        if start_num is not None and end_num is not None and start_num <= end_num:
                            query = query.where(NotaFiscalOrm.invoice_code.between(start_num, end_num))
                            applied_filters.append(f"invoice_number BETWEEN {start_num} AND {end_num}")
                        else:
                            logger.warning(f"Range de número de nota inválido: '{num_input}'. Ignorando filtro.")
                    # 2. Checar por Lista (ex: "101, 105, 200")
                    elif ',' in num_input:
                        int_num_list = [safe_int(n.strip()) for n in num_input.split(',') if safe_int(n.strip()) is not None]
                        if int_num_list:
                            query = query.where(NotaFiscalOrm.invoice_code.in_(int_num_list))
                            applied_filters.append(f"invoice_number IN {int_num_list}")
                        else:
                             logger.warning(f"Lista de números de nota inválida ou vazia: '{num_input}'. Ignorando filtro.")
                    # 3. Assumir Número Único
                    else:
                        single_num = safe_int(num_input)
                        if single_num is not None:
                            query = query.where(NotaFiscalOrm.invoice_code == single_num)
                            applied_filters.append(f"invoice_number == {single_num}")
                        else:
                             logger.warning(f"Número de nota inválido: '{num_input}'. Ignorando filtro.")


            # Filtro por Chave de Acesso (Chave API: 'access_key')
            if 'access_key' in filters:
                 key = filters['access_key']
                 if key and isinstance(key, str) and len(key) == 44 and key.isdigit():
                      query = query.where(NotaFiscalOrm.access_key == key)
                      applied_filters.append(f"access_key == ...{key[-6:]}")
                 elif key:
                      logger.warning(f"Formato de chave de acesso inválido no filtro: '{key}'. Ignorando.")


            # Filtro por Código do Cliente (Chave API interna: 'customer_code', Campo ORM: person_code)
            if 'customer_code' in filters:
                code_input = filters['customer_code']
                if code_input and isinstance(code_input, str):
                    # Tratar lista separada por vírgula
                    code_list = [safe_int(c.strip()) for c in code_input.split(',') if safe_int(c.strip()) is not None]
                    if len(code_list) == 1:
                         query = query.where(NotaFiscalOrm.person_code == code_list[0])
                         applied_filters.append(f"person_code == {code_list[0]}")
                    elif len(code_list) > 1:
                         query = query.where(NotaFiscalOrm.person_code.in_(code_list))
                         applied_filters.append(f"person_code IN {code_list}")
                    else:
                        logger.warning(f"Lista de códigos de cliente inválida ou vazia: '{code_input}'. Ignorando filtro.")


            # Filtro por CPF/CNPJ do Cliente (Chave API interna: 'customer_cpf_cnpj')
            # !!! AJUSTE NECESSÁRIO QUANDO O JOIN COM A TABELA DE PESSOAS/CLIENTES FOR IMPLEMENTADO !!!
            if 'customer_cpf_cnpj' in filters:
                 cpf_cnpj_input = filters['customer_cpf_cnpj']
                 if cpf_cnpj_input and isinstance(cpf_cnpj_input, str):
                     cpf_cnpj_list = [doc.strip() for doc in cpf_cnpj_input.split(',') if doc.strip() and doc.isdigit() and (len(doc) == 11 or len(doc) == 14)]
                     if cpf_cnpj_list:
                          # --- Placeholder ---
                          # Substitua 'NotaFiscalOrm.branch_cnpj' pelo campo correto após o JOIN com a tabela de Pessoas/Clientes
                          # Exemplo: Se houver um relacionamento 'person' em NotaFiscalOrm:
                          # from src.domain.person_orm import PersonOrm # Importar
                          # query = query.join(PersonOrm, NotaFiscalOrm.person_code == PersonOrm.code) # Exemplo de JOIN
                          # query = query.where(PersonOrm.cpf_cnpj.in_(cpf_cnpj_list)) # Exemplo de filtro no campo correto
                          logger.warning("Filtro por CPF/CNPJ ainda não implementado com JOIN. Usando placeholder NotaFiscalOrm.branch_cnpj.")
                          query = query.where(NotaFiscalOrm.branch_cnpj.in_(cpf_cnpj_list)) # <<< AJUSTE ESTA LINHA FUTURAMENTE
                          applied_filters.append(f"branch_cnpj IN {cpf_cnpj_list} (Placeholder!)") # Ajuste o nome do campo no log também
                          # --- Fim Placeholder ---
                     else:
                          logger.warning(f"Lista de CPF/CNPJ inválida ou vazia: '{cpf_cnpj_input}'. Ignorando filtro.")


            # Filtro por Data de Emissão (Chaves API: 'start_date', 'end_date', Campo ORM: issue_date)
            start_issue_date = parse_optional_date(filters.get('start_date')) # Simplificado, API só usa 'start_date' agora
            end_issue_date = parse_optional_date(filters.get('end_date'))     # Simplificado, API só usa 'end_date' agora
            if start_issue_date:
                 query = query.where(NotaFiscalOrm.issue_date >= start_issue_date)
                 applied_filters.append(f"issue_date >= {start_issue_date.isoformat()}")
            if end_issue_date:
                 # Para garantir que a data final seja inclusiva
                 query = query.where(NotaFiscalOrm.issue_date <= end_issue_date)
                 applied_filters.append(f"issue_date <= {end_issue_date.isoformat()}")


            # Log dos filtros efetivamente aplicados
            if applied_filters:
                logger.info(f"Filtros aplicados na consulta: {'; '.join(applied_filters)}")
            else:
                logger.info("Nenhum filtro específico aplicado na consulta.")


            # --- Count Total Matching Items ---
            # Contar *depois* de aplicar todos os filtros WHERE
            count_query = select(func.count()).select_from(query.subquery())
            total_count = db.scalar(count_query) or 0
            logger.debug(f"Contagem total ANTES da paginação (com filtros): {total_count}")

            # --- Apply Ordering ---
            # Ordenar antes da paginação
            query = query.order_by(NotaFiscalOrm.issue_date.desc(), NotaFiscalOrm.invoice_code.desc())

            # --- Apply Pagination ---
            offset = (page - 1) * page_size
            query = query.limit(page_size).offset(offset)

            # --- Eager Loading ---
            # Carregar relacionamentos necessários para a formatação no FiscalService
            query = query.options(
                selectinload(NotaFiscalOrm.sales_orders) # Usado em _format_invoice_list_item
                # Adicione outros relacionamentos se forem usados na formatação
            )

            # --- Execute Query ---
            results = db.scalars(query).all()

            logger.info(f"Busca local concluída. {len(results)} itens retornados para página {page}. Total de itens correspondentes: {total_count}.")
            return list(results), total_count

        except SQLAlchemyError as e:
            logger.error(f"Erro de banco de dados na busca de notas fiscais locais: {e}", exc_info=True)
            raise DatabaseError(f"Erro de banco de dados durante busca de notas fiscais locais: {e}") from e
        except Exception as e:
            logger.error(f"Erro inesperado na busca de notas fiscais locais: {e}", exc_info=True)
            raise DatabaseError(f"Erro inesperado durante busca de notas fiscais locais: {e}") from e