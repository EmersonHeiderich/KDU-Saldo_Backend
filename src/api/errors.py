# src/api/errors.py

from flask import jsonify, request
from werkzeug.exceptions import HTTPException
from src.utils.logger import logger

class ApiError(Exception):
    """Base class for custom API errors."""
    status_code = 500
    message = "An internal server error occurred."

    def __init__(self, message=None, status_code=None, payload=None):
        super().__init__()
        if message is not None:
            self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv

class ValidationError(ApiError):
    """Indicates invalid data provided by the client."""
    status_code = 400
    message = "Validation failed."

class AuthenticationError(ApiError):
    """Indicates failure to authenticate."""
    status_code = 401
    message = "Authentication failed."

class InvalidTokenError(AuthenticationError):
    """Indicates the provided token is invalid."""
    message = "Invalid authentication token provided."

class ExpiredTokenError(AuthenticationError):
    """Indicates the provided token has expired."""
    message = "Authentication token has expired."

class ForbiddenError(ApiError):
    """Indicates the user does not have permission for the action."""
    status_code = 403
    message = "You do not have permission to perform this action."

class NotFoundError(ApiError):
    """Indicates a requested resource was not found."""
    status_code = 404
    message = "The requested resource was not found."

class ServiceError(ApiError):
     """Indicates a general error within a service layer operation."""
     status_code = 500
     message = "A service error occurred."

class DatabaseError(ApiError):
    """Indicates an error during a database operation."""
    status_code = 500
    message = "A database error occurred."

class ErpIntegrationError(ApiError):
    """Indicates an error during communication with the external ERP."""
    status_code = 502
    message = "Error communicating with the ERP system."

class ErpNotFoundError(NotFoundError):
     """Indicates a resource was specifically not found in the ERP."""
     message = "Resource not found in the ERP system."

class ConfigurationError(ApiError):
     """Indicates a problem with the application's configuration."""
     status_code = 500
     message = "Application configuration error."


def register_error_handlers(app):
    """Registers custom error handlers with the Flask app."""

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        """Handler for custom ApiError exceptions."""
        logger.warning(f"Erro de API tratado: {type(error).__name__} - Status: {error.status_code} - Msg: {error.message}")
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        """Handler for standard werkzeug HTTPExceptions (like 404, 405)."""
        logger.warning(f"Exceção HTTP tratada: {error.code} {error.name} - Path: {request.path} - Msg: {error.description}")
        response = jsonify({"error": f"{error.name}: {error.description}"})
        response.status_code = error.code
        return response

    @app.errorhandler(Exception)
    def handle_generic_exception(error):
        """Handler for any other unhandled exceptions."""
        logger.error(f"Exceção não tratada: {error}", exc_info=True)
        response = jsonify({"error": "An unexpected internal server error occurred."})
        response.status_code = 500
        return response

    logger.info("Handlers de erro personalizados registrados.")