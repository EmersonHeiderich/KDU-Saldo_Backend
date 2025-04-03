# src/app.py
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
)
from src.utils.logger import logger, configure_logger
from src.utils.system_monitor import start_resource_monitor, stop_resource_monitor

from src.database.user_repository import UserRepository
from src.database.observation_repository import ObservationRepository
from src.database.fiscal_repository import FiscalRepository

from src.services import (
    AuthService,
    CustomerService,
    FabricService,
    ObservationService,
    ProductService,
    FiscalService,
    AccountsReceivableService,
    FiscalSyncService
)
from src.services.fiscal_sync_service import (
    start_fiscal_sync_scheduler,
    stop_fiscal_sync_scheduler
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
    app = Flask("Connector-Backend")
    app.config.from_object(config_object)

    # --- Logging ---
    configure_logger(config_object.LOG_LEVEL)
    logger.info("Iniciando a aplicação Flask para o Connector-Backend.")
    logger.info(f"Nome da aplicação: {app.name}")
    logger.info(f"Modo de depuração: {app.config.get('APP_DEBUG')}")

    # --- Secret Key Check ---
    if not app.config.get('SECRET_KEY') or app.config.get('SECRET_KEY') == 'default_secret_key_change_me_in_env':
            logger.critical("ALERTA CRÍTICO DE SEGURANÇA: SECRET_KEY não está definida ou está usando o valor padrão!")
            if not app.config.get('APP_DEBUG', False):
                raise ConfigurationError("SECRET_KEY deve ser configurada com um valor seguro e único em produção.")
            else:
                logger.warning("Usando SECRET_KEY padrão/insegura no modo de depuração.")

    # --- CORS Configuration ---
    CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}})
    logger.info("CORS configurado para permitir todas as origens (Atualizar para produção).")

    # --- Database Initialization (SQLAlchemy) ---
    db_engine = None
    try:
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        if not db_uri:
             raise ConfigurationError("SQLALCHEMY_DATABASE_URI não está configurado.")

        db_engine = init_sqlalchemy(db_uri)
        logger.info("Motor SQLAlchemy e fábrica de sessões inicializados com sucesso.")

        atexit.register(dispose_sqlalchemy_engine)
        logger.debug("Registrado descarte do motor SQLAlchemy para saída da aplicação.")

    except (DatabaseError, ConfigurationError, SQLAlchemyError) as db_init_err:
        logger.critical(f"Falha ao inicializar o banco de dados: {db_init_err}", exc_info=True)
        import sys
        sys.exit(1)
    except Exception as generic_db_err:
         logger.critical(f"Erro inesperado durante a inicialização do banco de dados: {generic_db_err}", exc_info=True)
         import sys
         sys.exit(1)

    # --- Dependency Injection (Service Instantiation) ---
    logger.info("Instanciando serviços...")
    if not db_engine:
         logger.critical("Motor de banco de dados não disponível para instanciação de serviços.")
         import sys
         sys.exit(1)

    try:
        # --- Instanciar Repositórios Diretamente ---
        user_repo = UserRepository(db_engine)
        observation_repo = ObservationRepository(db_engine)
        fiscal_repo = FiscalRepository(db_engine)

        # Adicionar repositórios ao config da app
        app.config['user_repository'] = user_repo
        app.config['observation_repository'] = observation_repo
        app.config['fiscal_repository'] = fiscal_repo

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
        fiscal_svc = FiscalService(fiscal_repo, erp_fiscal_svc)
        ar_svc = AccountsReceivableService(erp_ar_svc, erp_person_svc)
        fiscal_sync_svc = FiscalSyncService(erp_fiscal_svc, fiscal_repo)

        # Store service instances in app config
        app.config['auth_service'] = auth_svc
        app.config['customer_service'] = customer_svc
        app.config['fabric_service'] = fabric_svc
        app.config['observation_service'] = observation_svc
        app.config['product_service'] = product_svc
        app.config['fiscal_service'] = fiscal_svc
        app.config['accounts_receivable_service'] = ar_svc
        app.config['fiscal_sync_service'] = fiscal_sync_svc

        logger.info("Serviços instanciados e adicionados à configuração do aplicativo.")

    except Exception as service_init_err:
        logger.critical(f"Falha ao instanciar serviços: {service_init_err}", exc_info=True)
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

    # --- Start Background Schedulers ---
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        logger.info("Iniciando agendadores de tarefas em segundo plano...")
        start_fiscal_sync_scheduler(fiscal_sync_svc)
        atexit.register(stop_fiscal_sync_scheduler)
        logger.info("Agendador de sincronização fiscal iniciado.")

    # --- Simple Health Check Endpoint ---
    @app.route('/health', methods=['GET'])
    def health_check():
        db_status = "ok"
        db_error = None
        try:
             with get_db_session() as db:
                 pass
        except Exception as e:
             logger.error(f"Verificação de saúde da sessão do banco de dados falhou: {e}")
             db_status = "error"
             db_error = str(e)

        sync_running = FiscalSyncService._is_running

        return jsonify({
            "status": "ok",
            "database": db_status,
            "database_error": db_error if db_error else None,
            "sync_service_running": sync_running
        }), 200 if db_status == "ok" else 503

    logger.info("Aplicação Connector-Backend configurada com sucesso.")
    return app