# src/database/fiscal_repository.py
# Handles database operations for Fiscal data using SQLAlchemy ORM.

from datetime import datetime, timezone # Adicionado timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func, delete, update
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
        Prioritizes lookup by (branch_code, invoice_sequence). Handles potential
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
        invoice_code = safe_int(invoice_data.get('invoiceCode'))
        access_key = (invoice_data.get('eletronic') or {}).get('accessKey')

        invoice_date = parse_optional_date(invoice_data.get('invoiceDate'))
        if branch_code is None or invoice_sequence is None or invoice_date is None:
            logger.warning("Pulando upsert da nota fiscal: Faltando branchCode, invoiceSequence ou invoiceDate.")
            return None

        # --- Chave Natural Primária ---
        natural_key_filter = (NotaFiscalOrm.branch_code == branch_code) & (NotaFiscalOrm.invoice_sequence == invoice_sequence) & (NotaFiscalOrm.invoice_date == invoice_date)
        existing_invoice: Optional[NotaFiscalOrm] = None
        created_new = False

        try:
            # --- Busca Robusta ---
            # 1. Tentar buscar na sessão atual primeiro (caso já processado no batch)
            for obj in db.new: # Objetos a serem inseridos
                if isinstance(obj, NotaFiscalOrm) and obj.branch_code == branch_code and obj.invoice_sequence == invoice_sequence:
                    existing_invoice = obj
                    logger.debug(f"Nota fiscal {branch_code}/{invoice_code} já pendente para inserção na sessão.")
                    break
            if not existing_invoice:
                 for obj in db.dirty: # Objetos a serem atualizados
                     if isinstance(obj, NotaFiscalOrm) and obj.branch_code == branch_code and obj.invoice_sequence == invoice_sequence:
                          existing_invoice = obj
                          logger.debug(f"Nota fiscal {branch_code}/{invoice_code} já pendente para atualização na sessão.")
                          break

            # 2. Se não estiver na sessão, buscar no banco pela chave natural
            if not existing_invoice:
                stmt_natural = select(NotaFiscalOrm).where(natural_key_filter)
                existing_invoice = db.scalars(stmt_natural).one_or_none()

            # 3. Se ainda não encontrado E houver access_key, tentar por access_key no banco
            #    (Cobre casos de inconsistência na chave natural vs access_key ou erros anteriores)
            if not existing_invoice and access_key:
                stmt_access_key = select(NotaFiscalOrm).where(NotaFiscalOrm.access_key == access_key)
                invoice_by_key = db.scalars(stmt_access_key).one_or_none()
                if invoice_by_key:
                    logger.warning(f"Nota fiscal encontrada pela access_key '{access_key}' mas não pela chave natural ({branch_code}/{invoice_code}). Usando registro existente encontrado pela chave.")
                    existing_invoice = invoice_by_key

            # --- Helper Function to Map Data (Permanece igual) ---
            def map_data_to_invoice(target: NotaFiscalOrm, data: Dict[str, Any]):
                # ... (código de mapeamento exatamente como antes) ...
                eletronic_data = data.get('eletronic') or {}
                shipping_data = data.get('shippingCompany') or {}

                target.branch_cnpj = data.get('branchCnpj')
                target.person_code = safe_int(data.get('personCode'))
                target.person_name = data.get('personName')
                target.invoice_code = safe_int(data.get('invoiceCode'))
                target.serial_code = data.get('serialCode')
                target.invoice_status = data.get('invoiceStatus')
                # Acesso seguro a access_key
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
                target.operation_name = data.get('operatioName') # Potential typo
                target.invoice_date = parse_optional_date(data.get('invoiceDate'))
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
                target.icms_subst_value = safe_float(data.get('icmsSubStValue'))
                target.total_value = safe_float(data.get('totalValue'))
                # Acesso seguro a shipping_data
                target.shipping_company_code = safe_int(shipping_data.get('shippingCompanyCode'))
                target.shipping_company_name = shipping_data.get('shippingCompanyName')
                target.freight_type = shipping_data.get('freitghtType') # Potential typo
                target.freight_type_redispatch = shipping_data.get('freitghtTypeRedispatch') # Potential typo
                target.freight_value = safe_float(shipping_data.get('freightValue'))
                target.package_number = safe_int(shipping_data.get('packageNumber'))
                target.gross_weight = safe_float(shipping_data.get('grossWeight'))
                target.net_weight = safe_float(shipping_data.get('netWeight'))
                target.species = shipping_data.get('species')
                target.terminal_code = safe_int(data.get('terminalCode'))
                target.observation_nfe = data.get('observationNFE')


            # --- Atualizar ou Criar ---
            if existing_invoice:
                # --- ATUALIZAÇÃO ---
                new_last_change = parse_optional_datetime(invoice_data.get('lastchangeDate'))
                # Comparar apenas se ambas as datas existirem
                should_update = True
                if existing_invoice.lastchange_date and new_last_change:
                    # Normalizar para UTC antes de comparar (se não forem naive)
                    existing_utc = existing_invoice.lastchange_date.astimezone(timezone.utc) if existing_invoice.lastchange_date.tzinfo else existing_invoice.lastchange_date
                    new_utc = new_last_change # new_last_change já é UTC ou naive (tratado como UTC implicitamente)
                    if new_utc <= existing_utc:
                        should_update = False

                if not should_update:
                     logger.debug(f"Pulando atualização da nota fiscal {branch_code}/{invoice_code}, timestamp não alterado ou mais antigo ({new_last_change}).")
                     # Não limpar filhos se não for atualizar
                     return existing_invoice

                logger.debug(f"Atualizando nota fiscal existente ID {existing_invoice.id} (Código: {invoice_code}, Filial: {branch_code})")
                invoice = existing_invoice
                map_data_to_invoice(invoice, invoice_data)
                # Limpar filhos ANTES de adicionar novos
                invoice.items.clear()
                invoice.payments.clear()
                invoice.sales_orders.clear()
                invoice.observations.clear()
                # Garantir que o flush ocorra para remover os filhos antigos do DB antes de adicionar novos
                # Isso pode ser feito implicitamente pelo SQLAlchemy ou explicitamente com db.flush() aqui,
                # mas o flush final já cobre isso.
            else:
                 # --- CRIAÇÃO ---
                logger.debug(f"Tentando criar nova nota fiscal (Código: {invoice_code}, Filial: {branch_code}, Chave: ...{access_key[-6:] if access_key else 'N/A'})")
                # Checagem prévia por access_key (melhoria contra race condition)
                if access_key:
                     stmt_check_key = select(NotaFiscalOrm.id).where(NotaFiscalOrm.access_key == access_key).limit(1)
                     key_already_exists = db.execute(stmt_check_key).scalar_one_or_none()
                     if key_already_exists:
                          logger.warning(f"Access_key duplicada '{access_key}' encontrada antes do INSERT para {branch_code}/{invoice_code}. Pulando este registro.")
                          return None # Pula esta nota

                invoice = NotaFiscalOrm(branch_code=branch_code, invoice_sequence=invoice_sequence)
                map_data_to_invoice(invoice, invoice_data)
                db.add(invoice)
                created_new = True # Marca que foi criado

            # --- Handle Children (Lógica como antes, associando ao 'invoice' correto) ---
            # ... (código completo para processar items, products, payments, sales_orders, observations) ...
            # Items and their Products
            items_list = invoice_data.get('items')
            if isinstance(items_list, list):
                for item_data in items_list:
                    if not isinstance(item_data, dict): continue
                    item_orm = NotaFiscalItemOrm(
                        nota_fiscal=invoice,
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
                    products_list = item_data.get('products')
                    if isinstance(products_list, list):
                         for prod_data in products_list:
                              if not isinstance(prod_data, dict): continue
                              prod_orm = NotaFiscalItemProdutoOrm(
                                  item=item_orm,
                                  product_code=safe_int(prod_data.get('productCode')), product_name=prod_data.get('productName'),
                                  dealer_code=safe_int(prod_data.get('dealerCode')), quantity=safe_float(prod_data.get('quantity')),
                                  unit_gross_value=safe_float(prod_data.get('unitGrossValue')), unit_discount_value=safe_float(prod_data.get('unitDiscountValue')),
                                  unit_net_value=safe_float(prod_data.get('unitNetValue')), gross_value=safe_float(prod_data.get('grossValue')),
                                  discount_value=safe_float(prod_data.get('discountValue')), net_value=safe_float(prod_data.get('netValue'))
                              )
                              item_orm.item_products.append(prod_orm)
                    invoice.items.append(item_orm)

            # Payments
            payments_list = invoice_data.get('payments')
            if isinstance(payments_list, list):
                for payment_data in payments_list:
                    if not isinstance(payment_data, dict): continue
                    payment_orm = NotaFiscalPagamentoOrm(
                        nota_fiscal=invoice,
                        document_number=safe_int(payment_data.get('documentNumber')), expiration_date=parse_optional_datetime(payment_data.get('expirationDate')),
                        payment_value=safe_float(payment_data.get('paymentValue')), document_type_code=safe_int(payment_data.get('documentTypeCode')),
                        document_type=payment_data.get('documentType'), installment=safe_int(payment_data.get('installment')),
                        bearer_code=safe_int(payment_data.get('bearerCode')), bearer_name=payment_data.get('bearerName')
                    )
                    invoice.payments.append(payment_orm)

            # Sales Orders
            sales_order_list = invoice_data.get('salesOrder')
            if isinstance(sales_order_list, list):
                for order_data in sales_order_list:
                    if not isinstance(order_data, dict): continue
                    order_orm = NotaFiscalPedidoVendaOrm(
                        nota_fiscal=invoice,
                        branch_code=safe_int(order_data.get('branchCode')), order_code=safe_int(order_data.get('orderCode')),
                        customer_order_code=order_data.get('customerOrderCode')
                    )
                    invoice.sales_orders.append(order_orm)

            # Observations (observationNF list)
            observations_list = invoice_data.get('observationNF')
            if isinstance(observations_list, list):
                 for obs_data in observations_list:
                      if not isinstance(obs_data, dict): continue
                      obs_orm = NotaFiscalObservacaoOrm(
                          nota_fiscal=invoice,
                          observation=obs_data.get('observation'),
                          sequence=safe_int(obs_data.get('sequence'))
                      )
                      invoice.observations.append(obs_orm)


            # --- Flush Final ---
            # O flush aqui é importante para detectar UniqueViolations ANTES do commit do batch
            db.flush()
            log_operation = "Criada" if created_new else "Atualizada"
            logger.debug(f"{log_operation} nota fiscal {branch_code}/{invoice_code} na sessão. Commit pendente.")
            return invoice

        except IntegrityError as e:
            # O rollback será feito pelo chamador (_sync_time_range)
            logger.error(f"Erro de integridade do banco de dados durante preparação de upsert para nota fiscal {branch_code}/{invoice_code}: {e}", exc_info=True)
            if "ix_nota_fiscal_access_key" in str(e.orig) or "uq_nota_fiscal_branch_sequence" in str(e.orig): # Checar ambas as constraints
                 logger.warning(f"IntegrityError provavelmente devido a chave duplicada para nota fiscal {branch_code}/{invoice_code}. Pulando este registro.")
                 # Precisamos fazer o rollback aqui para não afetar o resto do batch
                 db.rollback()
                 # Re-abrir a transação para o restante do batch (SQLAlchemy gerencia isso com o Session)
                 return None # Pular este item
            else:
                 # Outro erro de integridade, propagar
                 raise DatabaseError(f"Erro de integridade processando nota fiscal {branch_code}/{invoice_code}: {e}") from e
        except SQLAlchemyError as e:
            # O rollback será feito pelo chamador (_sync_time_range)
            logger.error(f"Erro de banco de dados durante upsert da nota fiscal {branch_code}/{invoice_code}: {e}", exc_info=True)
            raise DatabaseError(f"Erro de banco de dados processando nota fiscal {branch_code}/{invoice_code}: {e}") from e
        except Exception as e:
            # O rollback será feito pelo chamador (_sync_time_range)
            logger.error(f"Erro inesperado durante upsert da nota fiscal {branch_code}/{invoice_code}: {e}", exc_info=True)
            raise DatabaseError(f"Erro inesperado processando nota fiscal {branch_code}/{invoice_code}: {e}") from e


    # ... (get_latest_sync_timestamp e find_invoices_local permanecem iguais) ...
    def get_latest_sync_timestamp(self, db: Session) -> Optional[datetime]:
        """
        Finds the maximum 'lastchange_date' from the nota_fiscal table.
        """
        logger.debug("Consultando timestamp mais recente de sincronização (max lastchange_date) na tabela nota_fiscal.")
        try:
            stmt = select(func.max(NotaFiscalOrm.lastchange_date))
            latest_timestamp = db.scalar(stmt)
            if latest_timestamp:
                 logger.info(f"Timestamp mais recente de sincronização encontrado: {latest_timestamp.isoformat()}")
            else:
                 logger.info("Nenhum timestamp anterior de sincronização encontrado no banco de dados.")
            # Certificar que o timestamp retornado é timezone-aware (UTC)
            if latest_timestamp and latest_timestamp.tzinfo is None:
                 logger.warning(f"Timestamp {latest_timestamp} do DB é naive, assumindo UTC.")
                 latest_timestamp = latest_timestamp.replace(tzinfo=timezone.utc)
            elif latest_timestamp:
                 latest_timestamp = latest_timestamp.astimezone(timezone.utc)
            return latest_timestamp
        except SQLAlchemyError as e:
             logger.error(f"Erro de banco de dados ao obter timestamp mais recente de sincronização: {e}", exc_info=True)
             return None
        except Exception as e:
            logger.error(f"Erro inesperado ao obter timestamp mais recente de sincronização: {e}", exc_info=True)
            return None


    def find_invoices_local(self, db: Session, filters: Dict[str, Any], page: int, page_size: int) -> Tuple[List[NotaFiscalOrm], int]:
        """
        Searches for invoices in the LOCAL database based on provided filters.
        Args:
            db: The SQLAlchemy Session.
            filters: Dictionary of filter criteria (keys match NotaFiscalOrm attributes).
            page: Page number (starting from 1).
            page_size: Number of items per page.
        Returns:
            A tuple containing: (list of NotaFiscalOrm objects, total_count).
        """
        logger.debug(f"Buscando notas fiscais locais com filtros: {filters}, Página: {page}, TamanhoPágina: {page_size}")
        try:
            query = select(NotaFiscalOrm)
            # --- Apply Filters ---
            if 'electronic_invoice_status_list' in filters:
                status_list = filters['electronic_invoice_status_list']
                if status_list and isinstance(status_list, list):
                    status_list_lower = [s.lower() for s in status_list]
                    query = query.where(func.lower(NotaFiscalOrm.electronic_invoice_status).in_(status_list_lower))
            if 'recipient_name' in filters:
                name_filter = filters['recipient_name']
                if name_filter and isinstance(name_filter, str):
                    query = query.where(NotaFiscalOrm.person_name.ilike(f"%{name_filter}%"))
            if 'invoice_code_list' in filters:
                num_list = filters['invoice_code_list']
                if num_list and isinstance(num_list, list):
                    query = query.where(NotaFiscalOrm.invoice_code.in_(num_list))
            if 'access_key' in filters:
                 key = filters['access_key']
                 if key and isinstance(key, str):
                      query = query.where(NotaFiscalOrm.access_key == key)

            start_issue_date = parse_optional_date(filters.get('start_issue_date') or filters.get('start_date'))
            end_issue_date = parse_optional_date(filters.get('end_issue_date') or filters.get('end_date'))
            if start_issue_date:
                 query = query.where(NotaFiscalOrm.issue_date >= start_issue_date)
            if end_issue_date:
                 query = query.where(NotaFiscalOrm.issue_date <= end_issue_date)
            # --- Count Total Matching Items ---
            count_query = select(func.count()).select_from(query.subquery())
            total_count = db.scalar(count_query) or 0
            # --- Apply Ordering ---
            query = query.order_by(NotaFiscalOrm.issue_date.desc(), NotaFiscalOrm.invoice_code.desc())
            # --- Apply Pagination ---
            offset = (page - 1) * page_size
            query = query.limit(page_size).offset(offset)
            # --- Eager Loading ---
            query = query.options(
                selectinload(NotaFiscalOrm.sales_orders)
            )
            # --- Execute Query ---
            results = db.scalars(query).all()
            logger.debug(f"Busca de notas fiscais locais encontrou {len(results)} itens para página {page}. Total: {total_count}.")
            return list(results), total_count
        except SQLAlchemyError as e:
            logger.error(f"Erro de banco de dados na busca de notas fiscais locais: {e}", exc_info=True)
            raise DatabaseError(f"Erro de banco de dados durante busca de notas fiscais locais: {e}") from e
        except Exception as e:
            logger.error(f"Erro inesperado na busca de notas fiscais locais: {e}", exc_info=True)
            raise DatabaseError(f"Erro inesperado durante busca de notas fiscais locais: {e}") from e