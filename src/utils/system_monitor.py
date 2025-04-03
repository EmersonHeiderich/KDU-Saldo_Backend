# src/utils/system_monitor.py
import os
import psutil
import threading
import time
from typing import Optional
from .logger import logger

_monitor_thread: Optional[threading.Thread] = None
_stop_monitor = threading.Event()

def log_system_resources():
    """Registra informações sobre o uso atual de recursos do sistema (Memória, CPU, Threads, etc.)."""
    try:
        process = psutil.Process(os.getpid())

        memoria_info = process.memory_info()
        mem_mb = memoria_info.rss / (1024 * 1024)
        logger.info(f"Uso de Recursos - Memória (RSS): {mem_mb:.2f} MB")

        cpu_percent = process.cpu_percent(interval=0.1)
        logger.info(f"Uso de Recursos - CPU: {cpu_percent:.2f}%")

        threads = process.num_threads()
        logger.info(f"Uso de Recursos - Threads: {threads}")

        try:
            arquivos_abertos = len(process.open_files())
            logger.info(f"Uso de Recursos - Arquivos Abertos: {arquivos_abertos}")
        except (psutil.AccessDenied, NotImplementedError, Exception) as e:
            logger.debug(f"Não foi possível obter a contagem de arquivos abertos: {type(e).__name__}")

        try:
            conexoes = len(process.connections(kind='inet'))
            logger.info(f"Uso de Recursos - Conexões de Rede (inet): {conexoes}")
        except (psutil.AccessDenied, NotImplementedError, Exception) as e:
            logger.debug(f"Não foi possível obter a contagem de conexões de rede: {type(e).__name__}")

    except psutil.NoSuchProcess:
        logger.warning("Não foi possível obter informações do processo para monitoramento de recursos (processo finalizado?).")
    except Exception as e:
        logger.error(f"Erro ao registrar uso de recursos do sistema: {e}", exc_info=True)

def _monitor_task(interval_seconds: int = 300):
    """Tarefa em segundo plano que registra recursos periodicamente."""
    logger.info(f"Iniciando monitoramento periódico de recursos (Intervalo: {interval_seconds}s)")
    while not _stop_monitor.is_set():
        log_system_resources()
        _stop_monitor.wait(timeout=interval_seconds)
    logger.info("Monitoramento periódico de recursos finalizado.")

def start_resource_monitor(interval_seconds: int = 300):
    """
    Inicia a thread em segundo plano para monitoramento periódico de recursos.
    Garante que apenas um monitor esteja em execução.
    
    Args:
        interval_seconds: Intervalo de tempo entre logs de recursos (em segundos). Padrão: 5 minutos.
    """
    global _monitor_thread
    if _monitor_thread is None or not _monitor_thread.is_alive():
        _stop_monitor.clear()
        _monitor_thread = threading.Thread(target=_monitor_task, args=(interval_seconds,), daemon=True)
        _monitor_thread.start()
    else:
        logger.debug("Thread de monitoramento de recursos já está em execução.")

def stop_resource_monitor():
    """Envia sinal para a thread de monitoramento em segundo plano parar."""
    global _monitor_thread
    if _monitor_thread and _monitor_thread.is_alive():
        logger.info("Parando a thread de monitoramento de recursos...")
        _stop_monitor.set()
        _monitor_thread.join(timeout=5)
        if _monitor_thread.is_alive():
            logger.warning("A thread de monitoramento de recursos não parou corretamente.")
        _monitor_thread = None
    else:
        logger.debug("Thread de monitoramento de recursos não está em execução ou já foi parada.")
