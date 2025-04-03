import logging
import os
import sys
import traceback
from datetime import datetime
from concurrent_log_handler import ConcurrentRotatingFileHandler
from typing import Optional

# --- Configuração ---
LOG_DIRECTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
LOG_FILENAME_BASE = "app.log"  # Nome base do arquivo de log
LOG_LEVEL_DEFAULT = "DEBUG"  # Nível de log padrão
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d | %(funcName)s] - %(message)s'
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 10

class Logger:
    """Encapsula a configuração do logger usando ConcurrentRotatingFileHandler."""
    _instance = None
    _logger = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, name: str = "SaldoAPI", log_level: Optional[str] = None):
        if self._initialized:
            return

        # Determinar nível de log
        level_str = log_level
        if level_str is None:
            try:
                from src.config import config  # Importação atrasada para evitar dependências circulares
                level_str = config.LOG_LEVEL
            except ImportError:
                level_str = LOG_LEVEL_DEFAULT
        level_str = level_str.upper()

        numeric_level = getattr(logging, level_str, None)
        if not isinstance(numeric_level, int):
            print(f"Aviso: Nível de log inválido '{level_str}'. Usando DEBUG por padrão.", file=sys.stderr)
            numeric_level = logging.DEBUG
            level_str = "DEBUG"

        self._logger = logging.getLogger(name)
        self._logger.setLevel(numeric_level)

        if not self._logger.handlers:
            formatter = logging.Formatter(LOG_FORMAT)

            # Console
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self._logger.addHandler(console_handler)

            # Arquivo (ConcurrentRotatingFileHandler)
            try:
                os.makedirs(LOG_DIRECTORY, exist_ok=True)
                log_file_path = os.path.join(LOG_DIRECTORY, LOG_FILENAME_BASE)

                file_handler = ConcurrentRotatingFileHandler(
                    filename=log_file_path,
                    mode='a',
                    maxBytes=LOG_MAX_BYTES,
                    backupCount=LOG_BACKUP_COUNT,
                    encoding='utf-8',
                )
                file_handler.setFormatter(formatter)
                self._logger.addHandler(file_handler)
                print(f"Log configurado (ConcurrentRotatingFileHandler). Nível: {level_str}. Arquivo: {log_file_path}")
            except Exception as e:
                print(f"Erro ao configurar log de arquivo: {e}", file=sys.stderr)

        self._initialized = True

    def get_logger(self) -> logging.Logger:
        """Retorna a instância do logger configurado."""
        if not self._logger:
            raise RuntimeError("Logger não foi inicializado.")
        return self._logger

# Instância global do logger
logger_instance = Logger()
logger = logger_instance.get_logger()

def configure_logger(level: str):
    """Reconfigura o nível global do logger."""
    global logger_instance, logger
    logger_instance = Logger(log_level=level)
    logger = logger_instance.get_logger()
