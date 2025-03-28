# src/api/__init__.py
# Initializes the API layer and registers blueprints.

from flask import Flask
from .routes.auth import auth_bp
from .routes.users import users_bp
from .routes.products import products_bp
from .routes.fabrics import fabrics_bp
from .routes.observations import observations_bp
from .routes.customer_panel import customer_panel_bp
from .routes.fiscal import fiscal_bp # <<<--- ADDED
from src.utils.logger import logger

# List of blueprints to register
# Add new blueprints here as they are created
BLUEPRINTS = [
    (auth_bp, '/api/auth'),
    (users_bp, '/api/users'),
    (products_bp, '/api/products'),
    (fabrics_bp, '/api/fabrics'),
    (observations_bp, '/api/observations'),
    (customer_panel_bp, '/api/customer_panel'),
    (fiscal_bp, '/api/fiscal'), # <<<--- ADDED
]

def register_blueprints(app: Flask):
    """
    Registers all defined blueprints with the Flask application.

    Args:
        app: The Flask application instance.
    """
    logger.info("Registering API blueprints...")
    for bp, prefix in BLUEPRINTS:
        app.register_blueprint(bp, url_prefix=prefix)
        logger.debug(f"Blueprint '{bp.name}' registered with prefix '{prefix}'.")
    logger.info("All API blueprints registered.")

__all__ = ["register_blueprints"]