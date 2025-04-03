# run.py
# Entry point for running the Flask application.
import os
import sys
import traceback
from src.app import create_app
from src.utils.logger import logger
from src.config.settings import load_config

# Load configuration early
config = load_config()

if __name__ == '__main__':
    app = create_app(config)
    logger.info(f"Starting server on {config.APP_HOST}:{config.APP_PORT}")

    try:
        # Use waitress or gunicorn for production instead of app.run
        app.run(host=config.APP_HOST, port=config.APP_PORT, debug=config.APP_DEBUG)
    except Exception as e:
        logger.critical(f"Fatal error starting server: {e}", exc_info=True)
        logger.critical(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
