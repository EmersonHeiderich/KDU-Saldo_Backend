# src/utils/logger.py
# Configures the application-wide logger.

import logging
import os
import sys
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional, Tuple, Type

# --- Configuration ---
LOG_DIRECTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
LOG_FILENAME_FORMAT = "app_%Y-%m-%d.log" # Daily rotation
LOG_LEVEL_DEFAULT = "DEBUG" # Default if not set via config
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d | %(funcName)s] - %(message)s'
LOG_MAX_BYTES = 10 * 1024 * 1024 # 10 MB
LOG_BACKUP_COUNT = 10

# --- Logger Setup ---

class Logger:
    """Encapsulates logger configuration."""
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

        # Prevent adding multiple handlers if re-initialized (though Singleton should prevent this)
        if not self._logger.handlers:
            formatter = logging.Formatter(LOG_FORMAT)

            # Console Handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            # Optionally set different level for console
            # console_handler.setLevel(logging.INFO)
            self._logger.addHandler(console_handler)

            # File Handler (Timed Rotating)
            try:
                os.makedirs(LOG_DIRECTORY, exist_ok=True)
                log_file_path = os.path.join(LOG_DIRECTORY, datetime.now().strftime(LOG_FILENAME_FORMAT))

                # Use TimedRotatingFileHandler for daily rotation
                file_handler = TimedRotatingFileHandler(
                    filename=os.path.join(LOG_DIRECTORY, "app.log"), # Base name
                    when="midnight", # Rotate daily at midnight
                    interval=1,
                    backupCount=LOG_BACKUP_COUNT,
                    encoding='utf-8',
                    # suffix=LOG_FILENAME_FORMAT # Not needed, handler manages naming
                )
                # Customize the rollover filename (optional)
                file_handler.namer = lambda name: name.replace(".log", "") + "_" + datetime.now().strftime('%Y-%m-%d') + ".log"

                # --- Alternative: RotatingFileHandler (by size) ---
                # file_handler = RotatingFileHandler(
                #     filename=log_file_path, # Full path with date initially
                #     maxBytes=LOG_MAX_BYTES,
                #     backupCount=LOG_BACKUP_COUNT,
                #     encoding='utf-8'
                # )
                # ----------------------------------------------------

                file_handler.setFormatter(formatter)
                self._logger.addHandler(file_handler)
                print(f"Logging configured. Level: {level_str}. Log directory: {LOG_DIRECTORY}")

            except Exception as e:
                 print(f"Error configuring file logging: {e}", file=sys.stderr)
                 # Continue without file logging if it fails

            # Install handler for uncaught exceptions
            # sys.excepthook = self._handle_uncaught_exception # Disabled for now, Flask handles errors better

        self._initialized = True


    def get_logger(self) -> logging.Logger:
        """Returns the configured logger instance."""
        if not self._logger:
             # This should not happen if __init__ was called
             raise RuntimeError("Logger has not been initialized.")
        return self._logger

    # def _handle_uncaught_exception(self, exc_type: Type[BaseException], exc_value: BaseException, exc_traceback) -> None:
    #     """Logs uncaught exceptions."""
    #     if issubclass(exc_type, KeyboardInterrupt):
    #         # Don't log Ctrl+C
    #         sys.__excepthook__(exc_type, exc_value, exc_traceback)
    #         return
    #     if self._logger:
    #         self._logger.critical("Unhandled exception caught by excepthook:", exc_info=(exc_type, exc_value, exc_traceback))
    #         self._logger.critical(f"Traceback details: {''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))}")
    #     else:
    #          # Fallback if logger failed init
    #          print("FATAL: Unhandled exception occurred before logger was fully initialized.", file=sys.stderr)
    #          sys.__excepthook__(exc_type, exc_value, exc_traceback)


# --- Global Logger Instance ---
# Initialize logger instance immediately, allowing config override later if needed
logger_instance = Logger()
logger = logger_instance.get_logger()

# Allow re-configuration if called explicitly with a level (e.g., from app factory)
def configure_logger(level: str):
     """Reconfigures the global logger level."""
     global logger_instance, logger
     logger_instance = Logger(log_level=level) # Re-init potentially changes level
     logger = logger_instance.get_logger()