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
    init_sqlalchemy_engine,
    dispose_sqlalchemy_engine,
    get_sqlalchemy_engine
)
from src.utils.logger import logger, configure_logger
from src.utils.system_monitor import start_resource_monitor, stop_resource_monitor

from src.services import (
    AuthService,
    CustomerService,
    FabricService,
    ObservationService,
    ProductService,
    FiscalService,
    AccountsReceivableService
)

from src.database import (
    get_user_repository,
    get_observation_repository
)
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
    try:
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        if not db_uri:
             raise ConfigurationError("SQLALCHEMY_DATABASE_URI is not configured.")

        # Chamar a nova função de inicialização do SQLAlchemy Engine
        init_sqlalchemy_engine(db_uri)
        logger.info("SQLAlchemy engine initialized successfully.")

        # Registrar função para fechar pool do engine no desligamento da app
        atexit.register(dispose_sqlalchemy_engine)
        logger.debug("Registered SQLAlchemy engine disposal for application exit.")

    except (DatabaseError, ConfigurationError, SQLAlchemyError) as db_init_err:
        logger.critical(f"Failed to initialize database engine or schema: {db_init_err}", exc_info=True)
        # Considerar se a aplicação pode rodar sem banco, ou forçar saída:
        # import sys
        # sys.exit(1)
    except Exception as generic_db_err:
         logger.critical(f"Unexpected error during database initialization: {generic_db_err}", exc_info=True)
         # import sys
         # sys.exit(1)


    # --- Dependency Injection (Service Instantiation) ---
    # Esta parte não muda, pois as fábricas get_user_repository/get_observation_repository
    # foram atualizadas para usar o engine SQLAlchemy internamente.
    logger.info("Instantiating services...")
    try:
        # Database Repositories (usando fábricas atualizadas)
        user_repo = get_user_repository()
        observation_repo = get_observation_repository()

        # ERP Integration Services
        erp_balance_svc = ErpBalanceService(erp_auth_service)
        erp_cost_svc = ErpCostService(erp_auth_service)
        erp_person_svc = ErpPersonService(erp_auth_service)
        erp_product_svc = ErpProductService(erp_auth_service)
        erp_fiscal_svc = ErpFiscalService(erp_auth_service)
        erp_ar_svc = ErpAccountsReceivableService(erp_auth_service)

        # Application Services
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
        # Exit if services are critical?
        # import sys
        # sys.exit(1)

    # --- Register Blueprints (API Routes) ---
    register_blueprints(app)

    # --- Register Error Handlers ---
    register_error_handlers(app)

    # --- Resource Monitoring ---
    # Adicionado cheque para WERKZEUG_RUN_MAIN para evitar iniciar duas vezes em modo debug
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        start_resource_monitor(interval_seconds=300)
        atexit.register(stop_resource_monitor)

    # --- Simple Health Check Endpoint ---
    @app.route('/health', methods=['GET'])
    def health_check():
        db_status = "ok"
        try:
             # Teste rápido de conexão com o banco
             engine = get_sqlalchemy_engine()
             with engine.connect() as connection:
                  # connection.execute(text("SELECT 1")) # Opcional
                  pass # A conexão em si já é um bom teste
        except Exception as e:
             logger.error(f"Health check database connection failed: {e}")
             db_status = "error"

        return jsonify({"status": "ok", "database": db_status}), 200 if db_status == "ok" else 503

    logger.info("Flask application configured successfully with SQLAlchemy.")
    return app