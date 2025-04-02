# src/app.py
# Contains the Flask application factory using SQLAlchemy.

from flask import Flask, jsonify
from flask_cors import CORS
import atexit
import os
from sqlalchemy.exc import SQLAlchemyError

from src.config import Config
from src.api import register_blueprints
from src.api.errors import register_error_handlers, ConfigurationError, DatabaseError
from src.database import (
    get_db_session,
    init_sqlalchemy,
    dispose_sqlalchemy_engine,
    # Engine não precisa ser importado aqui diretamente
)
from src.utils.logger import logger, configure_logger
from src.utils.system_monitor import start_resource_monitor, stop_resource_monitor

# --- Importar Repositórios Diretamente ---
from src.database.user_repository import UserRepository
from src.database.observation_repository import ObservationRepository
# ---------------------------------------

from src.services import (
    AuthService,
    CustomerService,
    FabricService,
    ObservationService,
    ProductService,
    FiscalService,
    AccountsReceivableService
)

# Remover import das funções fábrica dos repositórios
# from src.database import (
#     get_user_repository,
#     get_observation_repository
# )

from src.erp_integration import (
    erp_auth_service,
    ErpBalanceService,
    ErpCostService,
    ErpPersonService,
    ErpProductService,
    ErpFiscalService,
    ErpAccountsReceivableService
)


def create_app(config_object: Config) -> Flask:
    """
    Factory function to create and configure the Flask application with SQLAlchemy.

    Args:
        config_object: The configuration object for the application.

    Returns:
        The configured Flask application instance.
    """
    app = Flask(__name__)
    app.config.from_object(config_object)

    # --- Logging ---
    configure_logger(config_object.LOG_LEVEL)
    logger.info("Flask application factory started.")
    logger.info(f"App Name: {app.name}")
    logger.info(f"Debug Mode: {app.config.get('APP_DEBUG')}")

    # --- Secret Key Check ---
    if not app.config.get('SECRET_KEY') or app.config.get('SECRET_KEY') == 'default_secret_key_change_me_in_env':
            logger.critical("CRITICAL SECURITY WARNING: SECRET_KEY is not set or is using the default value!")
            if not app.config.get('APP_DEBUG', False):
                raise ConfigurationError("SECRET_KEY must be set to a secure, unique value in production.")
            else:
                logger.warning("Using default/insecure SECRET_KEY in debug mode.")

    # --- CORS Configuration ---
    CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}})
    logger.info("CORS configured to allow all origins (Update for production).")

    # --- Database Initialization (SQLAlchemy) ---
    db_engine = None # Para passar para os repositórios
    try:
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        if not db_uri:
             raise ConfigurationError("SQLALCHEMY_DATABASE_URI is not configured.")

        # init_sqlalchemy agora retorna o engine
        db_engine = init_sqlalchemy(db_uri)
        logger.info("SQLAlchemy engine and session factory initialized successfully.")

        atexit.register(dispose_sqlalchemy_engine)
        logger.debug("Registered SQLAlchemy engine disposal for application exit.")

    except (DatabaseError, ConfigurationError, SQLAlchemyError) as db_init_err:
        logger.critical(f"Failed to initialize database: {db_init_err}", exc_info=True)
        # Parar a app se o banco falhar é uma boa prática
        import sys
        sys.exit(1)
    except Exception as generic_db_err:
         logger.critical(f"Unexpected error during database initialization: {generic_db_err}", exc_info=True)
         import sys
         sys.exit(1)

    # --- Dependency Injection (Service Instantiation) ---
    logger.info("Instantiating services...")
    if not db_engine:
         logger.critical("Database engine not available for service instantiation.")
         import sys
         sys.exit(1)

    try:
        # --- Instanciar Repositórios Diretamente ---
        # Passar o engine obtido do init_sqlalchemy
        user_repo = UserRepository(db_engine)
        observation_repo = ObservationRepository(db_engine)
        # -----------------------------------------

        # Adicionar repositórios ao config da app para acesso fácil se necessário
        # (ex: no helper _get_user_repository dentro de users.py)
        app.config['user_repository'] = user_repo
        app.config['observation_repository'] = observation_repo

        # ERP Integration Services (permanece igual)
        erp_balance_svc = ErpBalanceService(erp_auth_service)
        erp_cost_svc = ErpCostService(erp_auth_service)
        erp_person_svc = ErpPersonService(erp_auth_service)
        erp_product_svc = ErpProductService(erp_auth_service)
        erp_fiscal_svc = ErpFiscalService(erp_auth_service)
        erp_ar_svc = ErpAccountsReceivableService(erp_auth_service)

        # Application Services (recebem instâncias dos repositórios)
        auth_svc = AuthService(user_repo)
        customer_svc = CustomerService(erp_person_svc)
        fabric_svc = FabricService(erp_balance_svc, erp_cost_svc, erp_product_svc)
        observation_svc = ObservationService(observation_repo)
        product_svc = ProductService(erp_balance_svc)
        fiscal_svc = FiscalService(erp_fiscal_svc)
        ar_svc = AccountsReceivableService(erp_ar_svc, erp_person_svc)

        # Store service instances in app config
        app.config['auth_service'] = auth_svc
        app.config['customer_service'] = customer_svc
        app.config['fabric_service'] = fabric_svc
        app.config['observation_service'] = observation_svc
        app.config['product_service'] = product_svc
        app.config['fiscal_service'] = fiscal_svc
        app.config['accounts_receivable_service'] = ar_svc
        logger.info("Services instantiated and added to app config.")

    except Exception as service_init_err:
        logger.critical(f"Failed to instantiate services: {service_init_err}", exc_info=True)
        import sys
        sys.exit(1)

    # --- Register Blueprints (API Routes) ---
    register_blueprints(app)

    # --- Register Error Handlers ---
    register_error_handlers(app)

    # --- Resource Monitoring ---
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        start_resource_monitor(interval_seconds=300)
        atexit.register(stop_resource_monitor)

    # --- Simple Health Check Endpoint ---
    @app.route('/health', methods=['GET'])
    def health_check():
        db_status = "ok"
        try:
             with get_db_session() as db:
                  pass # Apenas obter a sessão testa a factory e o engine
        except Exception as e:
             logger.error(f"Health check database session failed: {e}")
             db_status = "error"

        return jsonify({"status": "ok", "database": db_status}), 200 if db_status == "ok" else 503

    logger.info("Flask application configured successfully with SQLAlchemy ORM.")
    return app