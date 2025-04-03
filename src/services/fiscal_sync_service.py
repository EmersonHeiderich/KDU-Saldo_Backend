# src/services/fiscal_sync_service.py
# Service responsible for synchronizing fiscal invoice data from ERP to local DB.

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.database import get_db_session
from src.database.fiscal_repository import FiscalRepository
from src.erp_integration.erp_fiscal_service import ErpFiscalService, ERP_FISCAL_PAGE_SIZE
from src.utils.logger import logger
from src.api.errors import ServiceError, DatabaseError, ErpIntegrationError
from src.config import config

# --- Constants for Sync Logic ---
INITIAL_SYNC_START_YEAR = 2010
SYNC_INTERVAL_MINUTES = 5
MAX_INVOICES_PER_TRANSACTION = 500

class FiscalSyncService:
    """
    Orchestrates the synchronization of fiscal invoices from the ERP
    to the local database. Handles initial bulk load in chunks and incremental updates.
    """
    _lock = threading.Lock()
    _is_running = False

    def __init__(self, erp_fiscal_service: ErpFiscalService, fiscal_repository: FiscalRepository):
        self.erp_fiscal_service = erp_fiscal_service
        self.fiscal_repository = fiscal_repository
        self.company_code = config.COMPANY_CODE
        logger.info("Serviço de sincronização fiscal inicializado.")

    def _get_last_sync_time(self) -> Optional[datetime]:
        """Fetches the latest 'lastchange_date' from the local database."""
        try:
            with get_db_session() as db:
                return self.fiscal_repository.get_latest_sync_timestamp(db)
        except (DatabaseError, SQLAlchemyError) as e:
            logger.error(f"Falha ao obter timestamp da última sincronização: {e}. Usando lógica de sincronização inicial.", exc_info=True)
            return None

    def run_sync(self, full_sync: bool = False):
        """
        Executes the synchronization process. Prevents concurrent runs.
        """
        if FiscalSyncService._is_running:
             logger.warning("Sincronização fiscal já está em execução. Ignorando esta chamada.")
             return

        with FiscalSyncService._lock:
             if FiscalSyncService._is_running:
                  logger.warning("Sincronização fiscal obteve o lock mas já está em execução. Ignorando.")
                  return
             FiscalSyncService._is_running = True
             logger.info(f"[CICLO INÍCIO] Iniciando ciclo de sincronização fiscal (Sincronização Completa: {full_sync}).")

        try:
            start_time_cycle = time.monotonic()
            total_processed_cycle = 0
            perform_initial_sync_logic = False

            if full_sync:
                logger.info("Sincronização completa solicitada pelo parâmetro.")
                perform_initial_sync_logic = True
            else:
                logger.info("Verificando timestamp da última sincronização para modo incremental...")
                last_sync_time = self._get_last_sync_time()

                if last_sync_time is None:
                    logger.info("Nenhuma sincronização anterior encontrada. Realizando sincronização inicial.")
                    perform_initial_sync_logic = True
                else:
                    # --- Incremental Sync Logic ---
                    start_date_inc = last_sync_time - timedelta(minutes=10)
                    end_date_inc = datetime.now(timezone.utc)
                    logger.info(f"Executando sincronização incremental de {start_date_inc.date()} até {end_date_inc.date()}")
                    try:
                        total_processed_cycle = self._sync_time_range(start_date_inc, end_date_inc)
                        logger.info(f"Sincronização incremental concluída. Processadas: {total_processed_cycle} notas fiscais.")
                    except Exception as e:
                         logger.error(f"Falha na sincronização incremental: {e}", exc_info=True)
                         raise

            # --- Initial Sync Logic (if needed) ---
            if perform_initial_sync_logic:
                logger.info("Iniciando processo de sincronização inicial em blocos de 6 meses.")
                try:
                    total_processed_cycle = self._perform_initial_sync_in_chunks()
                    logger.info(f"Processo de sincronização inicial concluído. Total processado: {total_processed_cycle} notas fiscais")
                except Exception as e:
                    logger.error(f"Falha no processo de sincronização inicial: {e}", exc_info=True)
                    raise

            elapsed_time_cycle = time.monotonic() - start_time_cycle
            elapsed_str = self._format_time_duration(elapsed_time_cycle)
            logger.info(f"[CICLO FIM] Ciclo de sincronização fiscal concluído com sucesso em {elapsed_str}. Processadas: {total_processed_cycle} notas fiscais.")

        except Exception as cycle_error:
             elapsed_time_cycle = time.monotonic() - start_time_cycle
             elapsed_str = self._format_time_duration(elapsed_time_cycle)
             logger.error(f"[CICLO ERRO] Ciclo de sincronização fiscal falhou após {elapsed_str}: {cycle_error}", exc_info=True)
        finally:
            with FiscalSyncService._lock:
                FiscalSyncService._is_running = False

    def _format_time_duration(self, seconds: float) -> str:
        """Formata duração de tempo em formato legível."""
        if seconds < 60:
            return f"{seconds:.2f} segundos"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.2f} minutos ({seconds:.2f} segundos)"
        else:
            hours = seconds / 3600
            minutes = (seconds % 3600) / 60
            return f"{hours:.2f} horas ({minutes:.2f} minutos)"

    def _perform_initial_sync_in_chunks(self) -> int:
        """
        Performs the initial data synchronization by fetching data in 6-month chunks
        and estimates remaining time.
        """
        total_processed_initial = 0
        start_year = INITIAL_SYNC_START_YEAR
        current_time = datetime.now(timezone.utc)
        end_year = current_time.year

        # --- Cálculo da Estimativa ---
        total_chunks = (end_year - start_year + 1) * 2
        chunks_processed = 0
        start_time_initial_sync = time.monotonic()

        for year in range(start_year, end_year + 1):
            logger.info(f"--- Processando sincronização inicial para o ano {year} ---")

            for half in [1, 2]:
                if year == end_year and half == 2 and current_time.month <= 6:
                     logger.info(f"Data atual está no primeiro semestre de {year}. Pulando segundo semestre.")
                     continue

                start_chunk, end_chunk = self._get_chunk_dates(year, half)
                effective_end_chunk = min(end_chunk, current_time)

                if start_chunk >= effective_end_chunk:
                    logger.info(f"Pulando bloco S{half}-{year} pois a data de início não é anterior à data de fim.")
                    continue

                # --- Log de Início do Chunk com Estimativa ---
                chunks_processed += 1
                avg_time_per_chunk = (time.monotonic() - start_time_initial_sync) / chunks_processed if chunks_processed > 0 else 0
                remaining_chunks = total_chunks - chunks_processed
                estimated_remaining_time = avg_time_per_chunk * remaining_chunks if avg_time_per_chunk > 0 else 0
                estimated_total_time = avg_time_per_chunk * total_chunks if avg_time_per_chunk > 0 else 0

                # Formatação mais clara das estimativas
                est_rem_str = self._format_time_duration(estimated_remaining_time) if estimated_remaining_time > 0 else "Calculando..."
                est_tot_str = self._format_time_duration(estimated_total_time) if estimated_total_time > 0 else "Calculando..."

                logger.info(f"""
[ESTIMATIVA]
Sincronizando bloco S{half}-{year} ({start_chunk.date()} até {effective_end_chunk.date()})
Progresso: Bloco {chunks_processed}/{total_chunks} ({(chunks_processed/total_chunks*100):.1f}%)
Tempo restante estimado: {est_rem_str}
Tempo total estimado: {est_tot_str}
[FIM ESTIMATIVA]""")

                start_time_chunk = time.monotonic()
                try:
                    processed_in_chunk = self._sync_time_range(start_chunk, effective_end_chunk)
                    total_processed_initial += processed_in_chunk
                    elapsed_chunk = time.monotonic() - start_time_chunk
                    elapsed_str = self._format_time_duration(elapsed_chunk)
                    logger.info(f"Concluído bloco S{half}-{year} em {elapsed_str}. Processadas: {processed_in_chunk} notas fiscais")
                except Exception as e:
                    logger.error(f"Erro sincronizando bloco S{half}-{year} ({start_chunk.date()} até {effective_end_chunk.date()}): {e}. Interrompendo sincronização inicial.")
                    raise

        logger.info("Processamento de blocos da sincronização inicial concluído.")
        return total_processed_initial

    def _get_chunk_dates(self, year: int, half: int) -> tuple[datetime, datetime]:
        """Calculates start and end dates for a 6-month chunk."""
        if half == 1:
            start_date = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            end_date = datetime(year, 6, 30, 23, 59, 59, 999999, tzinfo=timezone.utc)
        elif half == 2:
            start_date = datetime(year, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
            end_date = datetime(year, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)
        else:
            raise ValueError("Semestre inválido especificado")
        return start_date, end_date


    def _sync_time_range(self, start_date: datetime, end_date: datetime) -> int:
        """
        Fetches and processes invoices within a specific time range based on 'lastchangeDate'.
        Manages ERP pagination and commits data in batches. Returns the number of processed items.
        """
        current_page = 1
        has_next = True
        processed_count_range = 0
        invoices_in_batch = 0
        db: Optional[Session] = None
        db_context = None

        try:
            while has_next:
                logger.debug(f"Buscando página {current_page} do ERP para período {start_date.date()} até {end_date.date()}...")

                filter_payload = {
                    "change": {
                        "startDate": start_date.isoformat(timespec='milliseconds'),
                        "endDate": end_date.isoformat(timespec='milliseconds')
                    },
                    "branchCodeList": [self.company_code],
                    "origin": "Own",
                    "documentTypeCodeList": [55]
                }
                erp_request_payload = {
                    "filter": filter_payload,
                    "expand": "shippingCompany, salesOrder, eletronic, items, payments, observationNF, observationNFE",
                    "order": "lastchangeDate",
                    "page": current_page,
                    "pageSize": ERP_FISCAL_PAGE_SIZE
                }

                erp_response = self.erp_fiscal_service.fetch_invoices_page(erp_request_payload)
                items = erp_response.get('items', [])
                has_next = erp_response.get('hasNext', False)
                
                if items:
                     logger.info(f"Página {current_page} do ERP: Recebidas {len(items)} notas fiscais. Próxima={has_next}")
                elif has_next:
                     logger.debug(f"Página {current_page} do ERP: Recebidas 0 notas fiscais. Próxima={has_next}")

                if not items and not has_next:
                    logger.debug(f"Não há mais notas fiscais no ERP para a página {current_page} e período.")
                    break

                if not items:
                     current_page += 1
                     continue

                # --- Process Batch ---
                if db is None:
                    db_context = get_db_session()
                    db = db_context.__enter__()

                for invoice_data in items:
                    if not isinstance(invoice_data, dict): continue
                    upserted = self.fiscal_repository.upsert_invoice(db, invoice_data)
                    if upserted:
                        processed_count_range += 1
                        invoices_in_batch += 1

                    if invoices_in_batch >= MAX_INVOICES_PER_TRANSACTION:
                        logger.info(f"Confirmando lote de {invoices_in_batch} notas fiscais (Período {start_date.date()}-{end_date.date()}, Página ~{current_page})...")
                        db.commit()
                        logger.info("Lote confirmado com sucesso.")
                        invoices_in_batch = 0

                current_page += 1

        except Exception as e:
             logger.error(f"Erro durante sincronização de período ({start_date.date()} até {end_date.date()}): {e}", exc_info=True)
             if db: db.rollback()
             raise
        finally:
            if db_context:
                try:
                    if db and invoices_in_batch > 0:
                        logger.info(f"Confirmando lote final de {invoices_in_batch} notas fiscais para período {start_date.date()}-{end_date.date()}.")
                        db.commit()
                        logger.info("Lote final confirmado.")
                    db_context.__exit__(None, None, None)
                except Exception as final_err:
                    logger.error(f"Erro durante confirmação/fechamento final para sincronização de período: {final_err}", exc_info=True)
                    try:
                         if db: db.rollback()
                         db_context.__exit__(type(final_err), final_err, final_err.__traceback__)
                    except:
                          pass

        logger.info(f"Sincronização concluída para período {start_date.isoformat()} até {end_date.isoformat()}. Processadas/Atualizadas: {processed_count_range}")
        return processed_count_range


# --- Background Task Setup ---
_sync_thread: Optional[threading.Thread] = None
_stop_sync_event = threading.Event()

def _fiscal_sync_task(sync_service: FiscalSyncService, initial_delay_sec: int, interval_min: int):
    """The actual function run by the background thread."""
    logger.info(f"Tarefa de sincronização fiscal em background iniciada. Atraso inicial: {initial_delay_sec}s, Intervalo: {interval_min}min.")
    first_run = True
    while not _stop_sync_event.is_set():
        if first_run:
            logger.info(f"Aguardando {initial_delay_sec}s antes da primeira execução de sincronização fiscal...")
            wait_time = initial_delay_sec
            first_run = False
        else:
            wait_time = interval_min * 60

        interrupted = _stop_sync_event.wait(timeout=wait_time)
        if interrupted:
             logger.info("Tarefa de sincronização fiscal interrompida pelo evento de parada durante espera.")
             break

        logger.info("Tarefa de sincronização fiscal iniciando ciclo de trabalho...")
        try:
            sync_service.run_sync(full_sync=False)
        except Exception as e:
            logger.error(f"Erro não tratado durante ciclo de sincronização fiscal agendado: {e}", exc_info=True)

        logger.info(f"Ciclo de trabalho de sincronização fiscal finalizado. Aguardando próximo gatilho ({interval_min} min)...")

    logger.info("Tarefa de sincronização fiscal em background finalizada.")

def start_fiscal_sync_scheduler(sync_service: FiscalSyncService, initial_delay_sec: int = 30, interval_min: int = SYNC_INTERVAL_MINUTES):
    global _sync_thread
    if _sync_thread is None or not _sync_thread.is_alive():
        _stop_sync_event.clear()
        _sync_thread = threading.Thread(
            target=_fiscal_sync_task,
            args=(sync_service, initial_delay_sec, interval_min),
            daemon=True
        )
        _sync_thread.start()
        logger.info("Thread do agendador de sincronização fiscal iniciada.")
    else:
        logger.warning("Thread do agendador de sincronização fiscal já está em execução.")

def stop_fiscal_sync_scheduler():
    global _sync_thread
    if _sync_thread and _sync_thread.is_alive():
        logger.info("Parando thread do agendador de sincronização fiscal...")
        _stop_sync_event.set()
        _sync_thread.join(timeout=10)
        if _sync_thread.is_alive():
            logger.warning("Thread do agendador de sincronização fiscal não parou adequadamente após 10s.")
        _sync_thread = None
    else:
        logger.info("Thread do agendador de sincronização fiscal não está em execução ou já foi parada.")