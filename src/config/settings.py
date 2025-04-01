# src/config/settings.py
# Loads environment variables and defines the application configuration.

from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv
import os
import logging
import sys
from urllib.parse import quote_plus # Para senhas na URL

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

    # --- Database Settings ---
    DB_TYPE: str = field(default_factory=lambda: os.environ.get('DB_TYPE', 'POSTGRES').upper()) # Default to POSTGRES

    # PostgreSQL Specific Settings (read from .env)
    POSTGRES_HOST: str = field(default_factory=lambda: os.environ.get('POSTGRES_HOST', 'localhost'))
    POSTGRES_PORT: int = field(default_factory=lambda: int(os.environ.get('POSTGRES_PORT', 5432)))
    POSTGRES_USER: str = field(default_factory=lambda: os.environ.get('POSTGRES_USER', ''))
    POSTGRES_PASSWORD: str = field(default_factory=lambda: os.environ.get('POSTGRES_PASSWORD', ''))
    POSTGRES_DB: str = field(default_factory=lambda: os.environ.get('POSTGRES_DB', ''))

    # --- SQLAlchemy Database URL ---
    # Constructed based on the DB_TYPE and specific settings
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    # TOTVS ERP Company Code
    COMPANY_CODE: int = field(default_factory=lambda: int(os.environ.get('COMPANY_CODE', 1)))

    # TOTVS ERP API Integration Settings
    API_BASE_URL: str = field(default_factory=lambda: os.environ.get('API_BASE_URL', 'http://10.1.1.221:11980/api/totvsmoda'))
    PAGE_SIZE: int = field(default_factory=lambda: int(os.environ.get('PAGE_SIZE', 1000)))
    FISCAL_PAGE_SIZE: int = field(default_factory=lambda: min(int(os.environ.get('FISCAL_PAGE_SIZE', 50)), 100))
    MAX_RETRIES: int = field(default_factory=lambda: int(os.environ.get('MAX_RETRIES', 3)))

    # TOTVS ERP API Endpoints (relative to API_BASE_URL)
    BALANCES_ENDPOINT: str = field(default_factory=lambda: os.environ.get('BALANCES_ENDPOINT', '/product/v2/balances/search'))
    COSTS_ENDPOINT: str = field(default_factory=lambda: os.environ.get('COSTS_ENDPOINT', '/product/v2/costs/search'))
    PRODUCTS_ENDPOINT: str = field(default_factory=lambda: os.environ.get('PRODUCTS_ENDPOINT', '/product/v2/products/search'))
    INDIVIDUALS_ENDPOINT: str = field(default_factory=lambda: os.environ.get('INDIVIDUALS_ENDPOINT', '/person/v2/individuals/search'))
    LEGAL_ENTITIES_ENDPOINT: str = field(default_factory=lambda: os.environ.get('LEGAL_ENTITIES_ENDPOINT', '/person/v2/legal-entities/search'))
    PERSON_STATS_ENDPOINT: str = field(default_factory=lambda: os.environ.get('PERSON_STATS_ENDPOINT', '/person/v2/person-statistics'))
    TOKEN_ENDPOINT: str = field(default_factory=lambda: os.environ.get('TOKEN_ENDPOINT', '/authorization/v2/token'))
    ACCOUNTS_RECEIVABLE_DOCUMENTS_ENDPOINT: str = field(default_factory=lambda: os.environ.get('ACCOUNTS_RECEIVABLE_DOCUMENTS_ENDPOINT', '/accounts-receivable/v2/documents/search'))
    ACCOUNTS_RECEIVABLE_BANKSLIP_ENDPOINT: str = field(default_factory=lambda: os.environ.get('ACCOUNTS_RECEIVABLE_BANKSLIP_ENDPOINT', '/accounts-receivable/v2/bank-slip'))
    ACCOUNTS_RECEIVABLE_PAYMENTLINK_ENDPOINT: str = field(default_factory=lambda: os.environ.get('ACCOUNTS_RECEIVABLE_PAYMENTLINK_ENDPOINT', '/accounts-receivable/v2/payment-link'))
    FISCAL_INVOICES_ENDPOINT: str = field(default_factory=lambda: os.environ.get('FISCAL_INVOICES_ENDPOINT', '/fiscal/v2/invoices/search'))
    FISCAL_XML_ENDPOINT: str = field(default_factory=lambda: os.environ.get('FISCAL_XML_ENDPOINT', '/fiscal/v2/xml-contents'))
    FISCAL_DANFE_ENDPOINT: str = field(default_factory=lambda: os.environ.get('FISCAL_DANFE_ENDPOINT', '/fiscal/v2/danfe-search'))

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

        # --- Build SQLAlchemy Database URI ---
        if self.DB_TYPE == 'POSTGRES':
            if not all([self.POSTGRES_HOST, self.POSTGRES_USER, self.POSTGRES_PASSWORD, self.POSTGRES_DB]):
                print("Warning: Missing PostgreSQL connection details in environment variables. Database connection will likely fail.", file=sys.stderr)
                self.SQLALCHEMY_DATABASE_URI = None
            else:
                 # Use quote_plus for password in case it has special characters
                 encoded_password = quote_plus(self.POSTGRES_PASSWORD)
                 # Specify the driver (+psycopg)
                 self.SQLALCHEMY_DATABASE_URI = f"postgresql+psycopg://{self.POSTGRES_USER}:{encoded_password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        elif self.DB_TYPE == 'SQLITE':
             # Keep SQLite support if needed temporarily (requires DATABASE_PATH in .env)
             db_path = os.environ.get('DATABASE_PATH')
             if db_path:
                  abs_path = os.path.join(PROJECT_ROOT, db_path) if not os.path.isabs(db_path) else db_path
                  os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                  self.SQLALCHEMY_DATABASE_URI = f"sqlite:///{abs_path}"
             else:
                  print("Warning: DB_TYPE is SQLITE but DATABASE_PATH is not set.", file=sys.stderr)
                  self.SQLALCHEMY_DATABASE_URI = None
        else:
             print(f"Warning: Unsupported DB_TYPE '{self.DB_TYPE}'. No database URI configured.", file=sys.stderr)
             self.SQLALCHEMY_DATABASE_URI = None

        # Validate Fiscal Page Size
        if self.FISCAL_PAGE_SIZE > 100:
            print(f"Warning: FISCAL_PAGE_SIZE ({self.FISCAL_PAGE_SIZE}) exceeds ERP limit of 100. Clamping to 100.", file=sys.stderr)
            self.FISCAL_PAGE_SIZE = 100
        elif self.FISCAL_PAGE_SIZE < 1:
            print(f"Warning: FISCAL_PAGE_SIZE ({self.FISCAL_PAGE_SIZE}) is invalid. Setting to default 50.", file=sys.stderr)
            self.FISCAL_PAGE_SIZE = 50

# Singleton instance, created by load_config
_config_instance: Optional[Config] = None

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
        print(f"  DB_TYPE: {_config_instance.DB_TYPE}")
        # Mask password in logged URI
        db_uri_log = str(_config_instance.SQLALCHEMY_DATABASE_URI)
        if _config_instance.POSTGRES_PASSWORD:
             db_uri_log = db_uri_log.replace(quote_plus(_config_instance.POSTGRES_PASSWORD), '********')
        print(f"  SQLALCHEMY_DATABASE_URI: {db_uri_log}")
        print(f"  API_BASE_URL: {_config_instance.API_BASE_URL}")
        print(f"  API_USERNAME: {'*' * len(_config_instance.API_USERNAME) if _config_instance.API_USERNAME else 'Not Set'}")
        print(f"  COMPANY_CODE: {_config_instance.COMPANY_CODE}")
        print(f"  PAGE_SIZE (General): {_config_instance.PAGE_SIZE}")
        print(f"  FISCAL_PAGE_SIZE: {_config_instance.FISCAL_PAGE_SIZE}")
        print("--------------------------")
    return _config_instance

# Expose the singleton instance directly
config = load_config()

# Helper to get PROJECT_ROOT if needed elsewhere
def get_project_root() -> str:
    return PROJECT_ROOT