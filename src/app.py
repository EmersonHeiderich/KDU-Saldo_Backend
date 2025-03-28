# src/app.py
# Contains the Flask application factory.

from flask import Flask, jsonify
from flask_cors import CORS
import atexit

from src.config import Config
from src.api import register_blueprints
from src.api.errors import register_error_handlers, ConfigurationError # Import error
from src.database import init_db, close_db_pool, release_db_connection, get_db_pool
from src.utils.logger import logger, configure_logger
from src.utils.system_monitor import start_resource_monitor, stop_resource_monitor # Import monitor functions

# Import Services
from src.services import (
    AuthService,
    CustomerService,
    FabricService,
    ObservationService,
    ProductService,
    FiscalService # <<<--- ADDED
)
# Import Repositories/ERP Services needed for Service instantiation
from src.database import (
    get_user_repository,
    get_observation_repository
)
from src.erp_integration import (
    erp_auth_service, # Use singleton auth service
    ErpBalanceService,
    ErpCostService,
    ErpPersonService,
    ErpProductService,
    ErpFiscalService # <<<--- ADDED
)


def create_app(config_object: Config) -> Flask:
    """
    Factory function to create and configure the Flask application.

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
            # Optionally raise an error in non-debug mode?
            if not app.config.get('APP_DEBUG', False):
                raise ConfigurationError("SECRET_KEY must be set to a secure, unique value in production.")
            else:
                logger.warning("Using default/insecure SECRET_KEY in debug mode.")


    # --- CORS Configuration ---
    # TODO: Restrict origins for production
    CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}}) # Allow all for now
    logger.info("CORS configured to allow all origins (Update for production).")

    # --- Database Initialization ---
    try:
        init_db(app.config['DATABASE_PATH'])
        logger.info("Database pool initialized successfully.")
        # Register teardown function to release DB connections
        app.teardown_appcontext(release_db_connection)
        logger.debug("Registered database connection release for app context teardown.")
        # Register function to close pool on app exit
        atexit.register(close_db_pool)
        logger.debug("Registered database pool closure for application exit.")
    except Exception as db_init_err:
        logger.critical(f"Failed to initialize database: {db_init_err}", exc_info=True)
        # Exit? Or let it run without DB? Let it run but endpoints needing DB will fail.
        # sys.exit(1) # Uncomment to force exit on DB init failure

    # --- Dependency Injection (Service Instantiation) ---
    logger.info("Instantiating services...")
    try:
        # Database Repositories (using factory functions)
        user_repo = get_user_repository()
        observation_repo = get_observation_repository()

        # ERP Integration Services
        erp_balance_svc = ErpBalanceService(erp_auth_service)
        erp_cost_svc = ErpCostService(erp_auth_service)
        erp_person_svc = ErpPersonService(erp_auth_service)
        erp_product_svc = ErpProductService(erp_auth_service)
        erp_fiscal_svc = ErpFiscalService(erp_auth_service) # <<<--- ADDED

        # Application Services
        auth_svc = AuthService(user_repo)
        customer_svc = CustomerService(erp_person_svc)
        fabric_svc = FabricService(erp_balance_svc, erp_cost_svc, erp_product_svc)
        observation_svc = ObservationService(observation_repo)
        product_svc = ProductService(erp_balance_svc)
        fiscal_svc = FiscalService(erp_fiscal_svc) # <<<--- ADDED

        # Store service instances in app config for access in routes/decorators
        app.config['auth_service'] = auth_svc
        app.config['customer_service'] = customer_svc
        app.config['fabric_service'] = fabric_svc
        app.config['observation_service'] = observation_svc
        app.config['product_service'] = product_svc
        app.config['fiscal_service'] = fiscal_svc # <<<--- ADDED
        logger.info("Services instantiated and added to app config.")

    except Exception as service_init_err:
        logger.critical(f"Failed to instantiate services: {service_init_err}", exc_info=True)
        # Exit if services are critical?
        # sys.exit(1)

    # --- Register Blueprints (API Routes) ---
    register_blueprints(app)

    # --- Register Error Handlers ---
    register_error_handlers(app)

    # --- Resource Monitoring ---
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # Start monitor only in main process (or if not in debug)
        start_resource_monitor(interval_seconds=300) # Log every 5 mins
        atexit.register(stop_resource_monitor) # Register stop on exit

    # --- Simple Health Check Endpoint ---
    @app.route('/health', methods=['GET'])
    def health_check():
        # Basic check, can be expanded later (e.g., check DB connection)
        return jsonify({"status": "ok"}), 200

    logger.info("Flask application configured successfully.")
    return app