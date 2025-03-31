# src/utils/logger.py
# Configures the application-wide logger using concurrent-log-handler.

import logging
import os
import sys
import traceback
from datetime import datetime
from concurrent_log_handler import ConcurrentRotatingFileHandler
from typing import Optional, Tuple, Type

# --- Configuration ---
LOG_DIRECTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
LOG_FILENAME_BASE = "app.log" # Base filename for concurrent handler
LOG_LEVEL_DEFAULT = "DEBUG" # Default if not set via config
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d | %(funcName)s] - %(message)s'
LOG_MAX_BYTES = 10 * 1024 * 1024 # 10 MB
LOG_BACKUP_COUNT = 10

# --- Logger Setup ---

class Logger:
    """Encapsulates logger configuration using ConcurrentRotatingFileHandler."""
    _instance = None
    _logger = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, name: str = "SaldoAPI", log_level: Optional[str] = None):
        """
        Initializes and configures the logger singleton.

        Args:
            name (str): Name of the logger.
            log_level (Optional[str]): Logging level string (e.g., 'DEBUG', 'INFO').
                                      Defaults to LOG_LEVEL_DEFAULT or config.
        """
        if self._initialized:
            return

        # Determine log level from argument, config, or default
        level_str = log_level
        if level_str is None:
             try:
                  from src.config import config # Lazy import to avoid circular dependency at module level
                  level_str = config.LOG_LEVEL
             except ImportError:
                  level_str = LOG_LEVEL_DEFAULT
        level_str = level_str.upper()

        # Get numeric log level
        numeric_level = getattr(logging, level_str, None)
        if not isinstance(numeric_level, int):
            print(f"Warning: Invalid log level '{level_str}'. Defaulting to DEBUG.", file=sys.stderr)
            numeric_level = logging.DEBUG
            level_str = "DEBUG" # Update string representation

        self._logger = logging.getLogger(name)
        self._logger.setLevel(numeric_level)

        # Prevent adding multiple handlers if re-initialized
        if not self._logger.handlers:
            formatter = logging.Formatter(LOG_FORMAT)

            # --- Console Handler ---
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self._logger.addHandler(console_handler)

            # --- File Handler (ConcurrentRotatingFileHandler) ---
            try:
                os.makedirs(LOG_DIRECTORY, exist_ok=True)
                # Use the base filename for the concurrent handler
                log_file_path = os.path.join(LOG_DIRECTORY, LOG_FILENAME_BASE)

                # Use ConcurrentRotatingFileHandler (typically size-based rotation)
                # This handler is designed for multi-process/thread safety.
                file_handler = ConcurrentRotatingFileHandler(
                    filename=log_file_path,
                    mode='a', # Append mode is default, but explicit is fine
                    maxBytes=LOG_MAX_BYTES,
                    backupCount=LOG_BACKUP_COUNT,
                    encoding='utf-8',
                    # delay=True # Optional: buffer logs slightly (can help under extreme load)
                )

                file_handler.setFormatter(formatter)
                self._logger.addHandler(file_handler)
                # Update print statement to reflect the handler used
                print(f"Logging configured (ConcurrentRotatingFileHandler). Level: {level_str}. Log file: {log_file_path}")

            except Exception as e:
                 print(f"Error configuring concurrent file logging: {e}", file=sys.stderr)
                 # Continue without file logging if it fails

        self._initialized = True

    def get_logger(self) -> logging.Logger:
        """Returns the configured logger instance."""
        if not self._logger:
             raise RuntimeError("Logger has not been initialized.")
        return self._logger

# --- Global Logger Instance ---
# Initialize logger instance immediately
logger_instance = Logger()
logger = logger_instance.get_logger()

# Allow re-configuration if called explicitly with a level (e.g., from app factory)
def configure_logger(level: str):
     """Reconfigures the global logger level."""
     global logger_instance, logger
     # Re-calling __init__ on the singleton will adjust the level if needed
     logger_instance = Logger(log_level=level)
     logger = logger_instance.get_logger()