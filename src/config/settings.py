# src/config/settings.py
# Loads environment variables and defines the application configuration.

from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv
import os
import logging # Use standard logging levels
import sys # Import sys

# Determine the project root directory dynamically
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
dotenv_path = os.path.join(PROJECT_ROOT, '.env')
load_dotenv(dotenv_path=dotenv_path)
print(f"Loading .env file from: {dotenv_path}") # Debug print

@dataclass
class Config:
    """
    Application configuration loaded from environment variables.
    Provides type hints and default values.
    """
    # Flask Settings
    SECRET_KEY: str = field(default_factory=lambda: os.environ.get('SECRET_KEY', 'default_secret_key_change_me_in_env'))
    APP_HOST: str = field(default_factory=lambda: os.environ.get('APP_HOST', '0.0.0.0'))
    APP_PORT: int = field(default_factory=lambda: int(os.environ.get('APP_PORT', 5004)))
    APP_DEBUG: bool = field(default_factory=lambda: os.environ.get('APP_DEBUG', 'True').lower() == 'true')
    TOKEN_EXPIRATION_HOURS: int = field(default_factory=lambda: int(os.environ.get('TOKEN_EXPIRATION_HOURS', 24)))
    LOG_LEVEL: str = field(default_factory=lambda: os.environ.get('LOG_LEVEL', 'DEBUG').upper())

    # Database Settings
    DATABASE_PATH: str = field(default_factory=lambda: os.path.join(PROJECT_ROOT, os.environ.get('DATABASE_PATH', 'database/app.db')))

    # TOTVS ERP Company Code
    COMPANY_CODE: int = field(default_factory=lambda: int(os.environ.get('COMPANY_CODE', 1)))

    # TOTVS ERP API Integration Settings
    API_BASE_URL: str = field(default_factory=lambda: os.environ.get('API_BASE_URL', 'http://10.1.1.221:11980/api/totvsmoda'))
    PAGE_SIZE: int = field(default_factory=lambda: int(os.environ.get('PAGE_SIZE', 1000))) # General page size
    # <<<--- ADDED FISCAL PAGE SIZE (Respecting ERP limit) --- >>>
    FISCAL_PAGE_SIZE: int = field(default_factory=lambda: min(int(os.environ.get('FISCAL_PAGE_SIZE', 50)), 100)) # Default 50, Max 100
    MAX_RETRIES: int = field(default_factory=lambda: int(os.environ.get('MAX_RETRIES', 3)))

    # TOTVS ERP API Endpoints (relative to API_BASE_URL)
    BALANCES_ENDPOINT: str = field(default_factory=lambda: os.environ.get('BALANCES_ENDPOINT', '/product/v2/balances/search'))
    COSTS_ENDPOINT: str = field(default_factory=lambda: os.environ.get('COSTS_ENDPOINT', '/product/v2/costs/search'))
    PRODUCTS_ENDPOINT: str = field(default_factory=lambda: os.environ.get('PRODUCTS_ENDPOINT', '/product/v2/products/search'))
    INDIVIDUALS_ENDPOINT: str = field(default_factory=lambda: os.environ.get('INDIVIDUALS_ENDPOINT', '/person/v2/individuals/search'))
    LEGAL_ENTITIES_ENDPOINT: str = field(default_factory=lambda: os.environ.get('LEGAL_ENTITIES_ENDPOINT', '/person/v2/legal-entities/search'))
    PERSON_STATS_ENDPOINT: str = field(default_factory=lambda: os.environ.get('PERSON_STATS_ENDPOINT', '/person/v2/person-statistics'))
    TOKEN_ENDPOINT: str = field(default_factory=lambda: os.environ.get('TOKEN_ENDPOINT', '/authorization/v2/token'))
    # --- Accounts Receivable Endpoints ---
    ACCOUNTS_RECEIVABLE_DOCUMENTS_ENDPOINT: str = field(default_factory=lambda: os.environ.get('ACCOUNTS_RECEIVABLE_DOCUMENTS_ENDPOINT', '/accounts-receivable/v2/documents/search'))
    ACCOUNTS_RECEIVABLE_BANKSLIP_ENDPOINT: str = field(default_factory=lambda: os.environ.get('ACCOUNTS_RECEIVABLE_BANKSLIP_ENDPOINT', '/accounts-receivable/v2/bank-slip'))
    ACCOUNTS_RECEIVABLE_PAYMENTLINK_ENDPOINT: str = field(default_factory=lambda: os.environ.get('ACCOUNTS_RECEIVABLE_PAYMENTLINK_ENDPOINT', '/accounts-receivable/v2/payment-link'))
    # --- Fiscal Endpoints ---
    # Renamed config keys for consistency (used in older version provided)
    FISCAL_INVOICES_ENDPOINT: str = field(default_factory=lambda: os.environ.get('FISCAL_INVOICES_ENDPOINT', '/fiscal/v2/invoices/search'))
    FISCAL_XML_ENDPOINT: str = field(default_factory=lambda: os.environ.get('FISCAL_XML_ENDPOINT', '/fiscal/v2/xml-contents'))
    FISCAL_DANFE_ENDPOINT: str = field(default_factory=lambda: os.environ.get('FISCAL_DANFE_ENDPOINT', '/fiscal/v2/danfe-search'))
    # -------------------------

    # TOTVS ERP API Credentials
    API_USERNAME: str = field(default_factory=lambda: os.environ.get('API_USERNAME', ''))
    API_PASSWORD: str = field(default_factory=lambda: os.environ.get('API_PASSWORD', ''))
    CLIENT_ID: str = field(default_factory=lambda: os.environ.get('CLIENT_ID', 'kduapiv2'))
    CLIENT_SECRET: str = field(default_factory=lambda: os.environ.get('CLIENT_SECRET', ''))
    GRANT_TYPE: str = field(default_factory=lambda: os.environ.get('GRANT_TYPE', 'password'))

    def __post_init__(self):
        # Validate log level
        valid_levels = list(logging._nameToLevel.keys())
        if self.LOG_LEVEL not in valid_levels:
             print(f"Warning: Invalid LOG_LEVEL '{self.LOG_LEVEL}'. Valid levels: {valid_levels}. Defaulting to DEBUG.", file=sys.stderr)
             self.LOG_LEVEL = 'DEBUG'
        # Ensure DATABASE_PATH is absolute
        if not os.path.isabs(self.DATABASE_PATH):
             self.DATABASE_PATH = os.path.join(PROJECT_ROOT, self.DATABASE_PATH)
        # Ensure database directory exists
        db_dir = os.path.dirname(self.DATABASE_PATH)
        os.makedirs(db_dir, exist_ok=True)
        # Ensure Fiscal Page Size is within bounds
        if self.FISCAL_PAGE_SIZE > 100:
            print(f"Warning: FISCAL_PAGE_SIZE ({self.FISCAL_PAGE_SIZE}) exceeds ERP limit of 100. Clamping to 100.", file=sys.stderr)
            self.FISCAL_PAGE_SIZE = 100
        elif self.FISCAL_PAGE_SIZE < 1:
            print(f"Warning: FISCAL_PAGE_SIZE ({self.FISCAL_PAGE_SIZE}) is invalid. Setting to default 50.", file=sys.stderr)
            self.FISCAL_PAGE_SIZE = 50

# Singleton instance, created by load_config
_config_instance: Optional[Config] = None # Optional type hint

def load_config() -> Config:
    """Loads or returns the singleton Config instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
        # Log loaded config values (mask sensitive ones)
        print("--- Configuration Loaded ---")
        print(f"  APP_HOST: {_config_instance.APP_HOST}")
        print(f"  APP_PORT: {_config_instance.APP_PORT}")
        print(f"  APP_DEBUG: {_config_instance.APP_DEBUG}")
        print(f"  LOG_LEVEL: {_config_instance.LOG_LEVEL}")
        print(f"  DATABASE_PATH: {_config_instance.DATABASE_PATH}")
        print(f"  API_BASE_URL: {_config_instance.API_BASE_URL}")
        print(f"  API_USERNAME: {'*' * len(_config_instance.API_USERNAME) if _config_instance.API_USERNAME else 'Not Set'}")
        print(f"  COMPANY_CODE: {_config_instance.COMPANY_CODE}")
        print(f"  PAGE_SIZE (General): {_config_instance.PAGE_SIZE}")
        print(f"  ACCOUNTS_RECEIVABLE_DOCUMENTS_ENDPOINT: {_config_instance.ACCOUNTS_RECEIVABLE_DOCUMENTS_ENDPOINT}")
        print(f"  ACCOUNTS_RECEIVABLE_BANKSLIP_ENDPOINT: {_config_instance.ACCOUNTS_RECEIVABLE_BANKSLIP_ENDPOINT}")
        print(f"  FISCAL_PAGE_SIZE: {_config_instance.FISCAL_PAGE_SIZE}") # Log new setting
        print(f"  FISCAL_INVOICES_ENDPOINT: {_config_instance.FISCAL_INVOICES_ENDPOINT}")
        print(f"  FISCAL_XML_ENDPOINT: {_config_instance.FISCAL_XML_ENDPOINT}")
        print(f"  FISCAL_DANFE_ENDPOINT: {_config_instance.FISCAL_DANFE_ENDPOINT}")
        print("--------------------------")
    return _config_instance

# Expose the singleton instance directly
config = load_config()

# Helper to get PROJECT_ROOT if needed elsewhere
def get_project_root() -> str:
    return PROJECT_ROOT