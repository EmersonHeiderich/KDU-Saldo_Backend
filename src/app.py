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
# Database imports (incluindo o novo repositório)
from src.database import (
    get_db_session,
    init_sqlalchemy,
    dispose_sqlalchemy_engine,
    get_user_repository,             # Função para obter UserRepository
    get_observation_repository,      # Função para obter ObservationRepository
    get_product_repository,          # Função para obter ProductRepository
    get_erp_person_repository        # Função para obter ErpPersonRepository
)
from src.utils.logger import logger, configure_logger
from src.utils.system_monitor import start_resource_monitor, stop_resource_monitor

# Services imports (incluindo o novo serviço de sync)
from src.services import (
    AuthService,
    CustomerService,
    FabricService,
    ObservationService,
    ProductService,
    FiscalService,
    AccountsReceivableService,
    PersonSyncService           # Serviço de Sync <<<--- ADICIONADO
)

# ERP Integration imports
from src.erp_integration import (
    erp_auth_service,           # Singleton
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
    CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}}) # Ajustar origins para produção
    logger.info("CORS configured.")

    # --- Database Initialization (SQLAlchemy) ---
    db_engine = None
    try:
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        if not db_uri:
             raise ConfigurationError("SQLALCHEMY_DATABASE_URI is not configured.")
        db_engine = init_sqlalchemy(db_uri) # init_sqlalchemy agora só inicializa dados essenciais
        logger.info("SQLAlchemy engine and session factory initialized successfully.")
        atexit.register(dispose_sqlalchemy_engine)
        logger.debug("Registered SQLAlchemy engine disposal for application exit.")
    except (DatabaseError, ConfigurationError, SQLAlchemyError) as db_init_err:
        logger.critical(f"Failed to initialize database: {db_init_err}", exc_info=True)
        import sys
        sys.exit(1)
    except Exception as generic_db_err:
         logger.critical(f"Unexpected error during database initialization: {generic_db_err}", exc_info=True)
         import sys
         sys.exit(1)

    # --- Dependency Injection (Repository and Service Instantiation) ---
    logger.info("Instantiating repositories and services...")
    if not db_engine:
         logger.critical("Database engine not available for service instantiation.")
         import sys
         sys.exit(1)

    try:
        # --- Repositórios ---
        # Instanciar todos os repositórios necessários, passando o engine
        # Usando as funções auxiliares para obter as classes de repositório
        UserRepository = get_user_repository()
        ObservationRepository = get_observation_repository()
        ProductRepository = get_product_repository()
        ErpPersonRepository = get_erp_person_repository()
        
        user_repo = UserRepository(db_engine)
        observation_repo = ObservationRepository(db_engine)
        product_repo = ProductRepository(db_engine) # Mesmo sendo placeholder
        erp_person_repo = ErpPersonRepository(db_engine) # <<<--- ADICIONADO

        # Adicionar repositórios ao config da app (útil para acesso via helpers ou comandos)
        app.config['user_repository'] = user_repo
        app.config['observation_repository'] = observation_repo
        app.config['product_repository'] = product_repo
        app.config['erp_person_repository'] = erp_person_repo # <<<--- ADICIONADO

        # --- ERP Integration Services ---
        # (erp_auth_service já é um singleton importado)
        erp_balance_svc = ErpBalanceService(erp_auth_service)
        erp_cost_svc = ErpCostService(erp_auth_service)
        erp_person_svc = ErpPersonService(erp_auth_service)
        erp_product_svc = ErpProductService(erp_auth_service)
        erp_fiscal_svc = ErpFiscalService(erp_auth_service)
        erp_ar_svc = ErpAccountsReceivableService(erp_auth_service)

        # --- Application Services ---
        auth_svc = AuthService(user_repo)
        customer_svc = CustomerService(erp_person_svc) # Nota: Este serviço usa dados direto do ERP, não do cache ainda.
        fabric_svc = FabricService(erp_balance_svc, erp_cost_svc, erp_product_svc)
        observation_svc = ObservationService(observation_repo) # Observação de PRODUTO (DB local)
        product_svc = ProductService(erp_balance_svc)
        fiscal_svc = FiscalService(erp_fiscal_svc)
        ar_svc = AccountsReceivableService(erp_ar_svc, erp_person_svc)

        # --- Serviço de Sincronização --- <<<--- ADICIONADO
        person_sync_svc = PersonSyncService(erp_person_svc, erp_person_repo)

        # --- Armazenar Instâncias no app.config ---
        app.config['auth_service'] = auth_svc
        app.config['customer_service'] = customer_svc
        app.config['fabric_service'] = fabric_svc
        app.config['observation_service'] = observation_svc
        app.config['product_service'] = product_svc
        app.config['fiscal_service'] = fiscal_svc
        app.config['accounts_receivable_service'] = ar_svc
        app.config['person_sync_service'] = person_sync_svc # <<<--- ADICIONADO

        logger.info("Repositories and Services instantiated and added to app config.")

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
             # Tenta obter sessão para verificar conectividade básica
             with get_db_session() as db:
                  # Opcional: fazer uma query simples como db.execute(select(1))
                  pass
        except Exception as e:
             logger.error(f"Health check database connection failed: {e}")
             db_status = "error"

        # Verificar se o serviço de sync está disponível (opcional)
        sync_service_status = "ok" if 'person_sync_service' in app.config else "unavailable"

        status_code = 200 if db_status == "ok" else 503
        return jsonify({
            "status": "ok" if status_code == 200 else "error",
            "database": db_status,
            "sync_service": sync_service_status
        }), status_code

    logger.info("Flask application configured successfully.")
    return app
