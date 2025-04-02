# src/services/sync/person_sync_service.py
# Serviço para sincronizar dados de Pessoas (PF/PJ) e Estatísticas do ERP para o cache local.

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple # <<<--- VERIFIQUE SE Tuple ESTÁ AQUI
import math
import time # <<<--- VERIFIQUE SE time ESTÁ AQUI

# Imports do SQLAlchemy e domínio
from sqlalchemy import select
from src.domain.erp_cache.person_cache import Person # Importar Person para a query em sync_all_statistics

# ERP Integration Services
from src.erp_integration.erp_person_service import ErpPersonService

# Database Cache Repository
from src.database.erp_cache.erp_person_repository import ErpPersonRepository

# Database Session Management
from src.database import get_db_session

# Errors and Logging
from src.utils.logger import logger
from src.api.errors import ServiceError, ErpIntegrationError, DatabaseError, NotFoundError
from src.config import config # Para page size, etc.

# Constante para tamanho do lote de processamento no banco
DB_BATCH_SIZE = 100

class PersonSyncService:
    """
    Orquestra a sincronização de dados de Pessoas (PF/PJ) e Estatísticas
    entre o ERP e o banco de dados de cache local.
    """

    def __init__(self,
                 erp_person_service: ErpPersonService,
                 erp_person_repository: ErpPersonRepository):
        """
        Inicializa o serviço de sincronização de pessoas.

        Args:
            erp_person_service: Instância do serviço de integração ERP para pessoas.
            erp_person_repository: Instância do repositório do cache local para pessoas.
        """
        self.erp_person_service = erp_person_service
        self.erp_person_repository = erp_person_repository
        logger.info("PersonSyncService initialized.")

    def perform_full_sync(self, batch_size_erp: int = 500) -> Dict[str, int]:
        """
        Executa uma sincronização completa, buscando todos os registros de PF e PJ do ERP
        e atualizando o cache local. Ideal para a carga inicial ou recargas periódicas.

        Args:
            batch_size_erp: Quantidade de registros a buscar por página do ERP.

        Returns:
            Um dicionário com estatísticas da sincronização (processados, falhas).
        """
        logger.info("Iniciando sincronização completa de Pessoas (PF/PJ)...")
        stats = {"pf_processed": 0, "pf_failed": 0, "pj_processed": 0, "pj_failed": 0, "stats_synced": 0, "stats_failed": 0}
        start_time_sync = time.time() # Nome da variável corrigido

        # Definir um período amplo para garantir que pegue tudo na carga inicial
        start_date = "2000-01-01T00:00:00Z"
        end_date = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        try:
            # Sincronizar Pessoas Físicas
            logger.info("Sincronizando Pessoas Físicas (PF)...")
            pf_stats = self._sync_person_type(
                person_type='PF',
                start_date_filter=start_date,
                end_date_filter=end_date,
                batch_size_erp=batch_size_erp
            )
            stats["pf_processed"] = pf_stats["processed"]
            stats["pf_failed"] = pf_stats["failed"]

            # Sincronizar Pessoas Jurídicas
            logger.info("Sincronizando Pessoas Jurídicas (PJ)...")
            pj_stats = self._sync_person_type(
                person_type='PJ',
                start_date_filter=start_date,
                end_date_filter=end_date,
                batch_size_erp=batch_size_erp
            )
            stats["pj_processed"] = pj_stats["processed"]
            stats["pj_failed"] = pj_stats["failed"]

            # Sincronizar Estatísticas após sincronizar pessoas
            logger.info("Sincronizando Estatísticas de Clientes...")
            stats_sync_result = self.sync_all_statistics()
            stats["stats_synced"] = stats_sync_result["synced"]
            stats["stats_failed"] = stats_sync_result["failed"]


        except (ErpIntegrationError, DatabaseError, ServiceError) as e:
            logger.critical(f"Erro crítico durante a sincronização completa: {e}", exc_info=True)
        except Exception as e:
            logger.critical(f"Erro inesperado durante a sincronização completa: {e}", exc_info=True)

        end_time_sync = time.time() # Nome da variável corrigido
        logger.info(f"Sincronização completa de Pessoas finalizada em {end_time_sync - start_time_sync:.2f} segundos. Estatísticas: {stats}")
        return stats

    def perform_incremental_sync(self, lookback_minutes: int = 60, batch_size_erp: int = 500) -> Dict[str, int]:
        """
        Executa uma sincronização incremental, buscando apenas os registros de PF e PJ
        alterados no ERP desde a última verificação (ou um período definido).

        Args:
            lookback_minutes: Quantos minutos atrás verificar por alterações.
            batch_size_erp: Quantidade de registros a buscar por página do ERP.

        Returns:
            Um dicionário com estatísticas da sincronização incremental.
        """
        logger.info(f"Iniciando sincronização incremental de Pessoas (Lookback: {lookback_minutes} min)...")
        stats = {"pf_processed": 0, "pf_failed": 0, "pj_processed": 0, "pj_failed": 0}
        start_time_sync = time.time()

        # Calcula a data/hora de início para o filtro 'change' do ERP
        end_date_dt = datetime.now(timezone.utc)
        start_date_dt = end_date_dt - timedelta(minutes=lookback_minutes)
        start_date_filter = start_date_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_date_filter = end_date_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        logger.info(f"Período de verificação de alterações: {start_date_filter} a {end_date_filter}")

        try:
            # Sincronizar Pessoas Físicas alteradas
            logger.info("Sincronizando Pessoas Físicas (PF) alteradas...")
            pf_stats = self._sync_person_type(
                person_type='PF',
                start_date_filter=start_date_filter,
                end_date_filter=end_date_filter,
                batch_size_erp=batch_size_erp
            )
            stats["pf_processed"] = pf_stats["processed"]
            stats["pf_failed"] = pf_stats["failed"]

            # Sincronizar Pessoas Jurídicas alteradas
            logger.info("Sincronizando Pessoas Jurídicas (PJ) alteradas...")
            pj_stats = self._sync_person_type(
                person_type='PJ',
                start_date_filter=start_date_filter,
                end_date_filter=end_date_filter,
                batch_size_erp=batch_size_erp
            )
            stats["pj_processed"] = pj_stats["processed"]
            stats["pj_failed"] = pj_stats["failed"]

        except (ErpIntegrationError, DatabaseError, ServiceError) as e:
            logger.error(f"Erro durante a sincronização incremental: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Erro inesperado durante a sincronização incremental: {e}", exc_info=True)

        end_time_sync = time.time()
        logger.info(f"Sincronização incremental de Pessoas finalizada em {end_time_sync - start_time_sync:.2f} segundos. Estatísticas: {stats}")
        return stats


    def _sync_person_type(self, person_type: str, start_date_filter: str, end_date_filter: str, batch_size_erp: int) -> Dict[str, int]:
        """Lógica interna para sincronizar um tipo específico de pessoa (PF ou PJ)."""
        erp_page = 1
        has_next_erp = True
        processed_count = 0
        failed_count = 0
        db_batch: List[Dict[str, Any]] = []

        erp_filter_change = {
            "startDate": start_date_filter, "endDate": end_date_filter,
            "inClassification": True, "inAddress": True, "inPhone": True, "inEmail": True,
            "inObservation": True, "inPerson": True, "inCustomer": True,
            "inSupplier": True, "inRepresentative": True, "inReference": True,
            "inContact": True, "inCustomerObservation": True, "inEmployee": True,
            "inPreference": True, "inPartner": True,
        }
        erp_expand = "phones,addresses,emails,classifications,additionalFields,references,observations,relateds,partners,contacts,paymentMethods,preferences,socialNetworks,representatives,familiars"

        while has_next_erp:
            logger.info(f"Buscando página {erp_page} de {person_type} no ERP...")
            try:
                erp_payload = {
                    "filter": {"change": erp_filter_change},
                    "expand": erp_expand,
                    "page": erp_page,
                    "pageSize": batch_size_erp
                }

                if person_type == 'PF':
                    # Idealmente, chame um método público no ErpPersonService
                    # Ex: response_data = self.erp_person_service.search_individuals_page(erp_payload)
                    response_data = self.erp_person_service._make_request(
                        self.erp_person_service.individuals_url, method="POST", json_payload=erp_payload
                    )
                elif person_type == 'PJ':
                    # Idealmente, chame um método público no ErpPersonService
                    # Ex: response_data = self.erp_person_service.search_legal_entities_page(erp_payload)
                     response_data = self.erp_person_service._make_request(
                         self.erp_person_service.legal_entities_url, method="POST", json_payload=erp_payload
                     )
                else:
                    raise ValueError(f"Tipo de pessoa inválido: {person_type}")

                items = response_data.get('items', [])
                has_next_erp = response_data.get('hasNext', False)
                total_items_erp = response_data.get('totalItems', 0)
                total_pages_erp = response_data.get('totalPages', 0)
                logger.info(f"Recebida página {erp_page}/{total_pages_erp if total_pages_erp else '?'} de {person_type} do ERP. Items: {len(items)}. Total ERP: {total_items_erp}. Próxima? {has_next_erp}")

                if not items:
                     if has_next_erp:
                          logger.warning(f"ERP indicou 'hasNext=True' mas a página {erp_page} de {person_type} veio vazia.")
                     break

                db_batch.extend(items)

                if len(db_batch) >= DB_BATCH_SIZE or not has_next_erp:
                    logger.info(f"Processando lote de {len(db_batch)} registros {person_type} no banco de dados...")
                    batch_processed, batch_failed = self._process_db_batch(db_batch, person_type)
                    processed_count += batch_processed
                    failed_count += batch_failed
                    db_batch = []

                erp_page += 1
                if erp_page > 10000:
                    logger.error(f"Limite de páginas (10000) atingido durante sync de {person_type}. Interrompendo.")
                    break

            except ErpIntegrationError as e:
                logger.error(f"Erro de integração ERP ao buscar página {erp_page} de {person_type}: {e}", exc_info=True)
                failed_count += len(db_batch)
                db_batch = []
                has_next_erp = False
                logger.warning(f"Interrompendo sincronização de {person_type} devido a erro de integração.") # Correção na f-string
            except Exception as e:
                logger.error(f"Erro inesperado ao buscar/processar página {erp_page} de {person_type}: {e}", exc_info=True)
                failed_count += len(db_batch)
                db_batch = []
                has_next_erp = False
                logger.error(f"Interrompendo sincronização de {person_type} devido a erro inesperado.") # Correção na f-string

        logger.info(f"Sincronização para {person_type} finalizada. Processados: {processed_count}, Falhas: {failed_count}")
        return {"processed": processed_count, "failed": failed_count}

    # --- A assinatura do método _process_db_batch agora está correta ---
    def _process_db_batch(self, batch_data: List[Dict[str, Any]], person_type: str) -> Tuple[int, int]:
        """Processa um lote de dados de pessoas no banco de dados."""
        processed = 0
        failed = 0
        try:
            with get_db_session() as db:
                for person_data in batch_data:
                    try:
                        self.erp_person_repository.upsert_person(db, person_data, person_type)
                        processed += 1
                    except (ValueError, DatabaseError) as e:
                        erp_code = person_data.get('code', 'N/A')
                        logger.error(f"Falha ao processar pessoa ERP {erp_code} (Tipo: {person_type}) no banco: {e}")
                        failed += 1
                logger.info(f"Lote DB {person_type} processado. Sucesso: {processed}, Falhas: {failed}.")
        except Exception as e:
             logger.error(f"Erro grave durante processamento do lote DB {person_type}: {e}", exc_info=True)
             failed += len(batch_data) - processed
             processed = 0
        return processed, failed


    def sync_all_statistics(self) -> Dict[str, int]:
        """
        Busca e atualiza/insere estatísticas para TODAS as pessoas (clientes)
        existentes no cache local.
        """
        logger.info("Iniciando sincronização de todas as estatísticas de clientes...")
        synced_count = 0
        failed_count = 0
        person_codes_to_sync: List[int] = []

        try:
             with get_db_session() as db:
                 # Importar Person aqui ou garantir que esteja no escopo global do módulo
                 from src.domain.erp_cache.person_cache import Person
                 person_tuples = db.execute(select(Person.erp_code).where(Person.is_customer == True)).scalars().all()
                 person_codes_to_sync = list(person_tuples)
             logger.info(f"Encontrados {len(person_codes_to_sync)} clientes no cache para buscar estatísticas.")
        except Exception as e:
             logger.error(f"Erro ao buscar códigos de clientes no cache para sync de estatísticas: {e}", exc_info=True)
             return {"synced": 0, "failed": len(person_codes_to_sync)}

        if not person_codes_to_sync:
             logger.info("Nenhum cliente encontrado no cache para sincronizar estatísticas.")
             return {"synced": 0, "failed": 0}

        for erp_code in person_codes_to_sync:
             try:
                 logger.debug(f"Buscando estatísticas do ERP para cliente {erp_code}...")
                 stats_data = self.erp_person_service.get_customer_statistics(erp_code, is_admin=False) # Ajustar is_admin se necessário

                 if stats_data:
                     with get_db_session() as db:
                         self.erp_person_repository.upsert_statistics(db, erp_code, stats_data.to_dict())
                     synced_count += 1
                     logger.debug(f"Estatísticas para cliente {erp_code} sincronizadas com sucesso.")
                 else:
                     logger.warning(f"Nenhuma estatística encontrada no ERP para cliente {erp_code}.")

             except (ErpIntegrationError, NotFoundError) as e:
                 logger.error(f"Erro de integração/não encontrado ao buscar estatísticas para cliente {erp_code}: {e}")
                 failed_count += 1
             except DatabaseError as e:
                 logger.error(f"Erro de banco de dados ao salvar estatísticas para cliente {erp_code}: {e}")
                 failed_count += 1
             except Exception as e:
                 logger.error(f"Erro inesperado ao sincronizar estatísticas para cliente {erp_code}: {e}", exc_info=True)
                 failed_count += 1
             # time.sleep(0.1) # Considerar pequeno delay

        logger.info(f"Sincronização de estatísticas finalizada. Sincronizados: {synced_count}, Falhas: {failed_count}")
        return {"synced": synced_count, "failed": failed_count}