# src/api/decorators.py
# Defines custom decorators for API endpoints, primarily for authentication and authorization.

from functools import wraps
from flask import request, current_app, jsonify
from src.services.auth_service import AuthService
from src.api.errors import AuthenticationError, ForbiddenError, ApiError, ConfigurationError # Added Config Error
from src.utils.logger import logger

# Helper to get auth_service instance from app context
def _get_auth_service() -> AuthService:
        service = current_app.config.get('auth_service')
        if not service:
            logger.critical("AuthService not found in application config!")
            # Raising allows Flask's error handlers to catch it
            raise ApiError("Authentication service is unavailable.", 503)
        return service

def login_required(f):
    """
    Decorator to ensure the user is logged in (valid token).
    Attaches the user object to request.current_user.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            auth_service = _get_auth_service()
            user = auth_service.get_current_user_from_request()
            if not user:
                    logger.debug("Access denied: No valid token/user found.")
                    # Raise specific error type for handler
                    raise AuthenticationError("Authentication required. Please log in.")

            # Attach user to the request context for use in the endpoint
            request.current_user = user
            logger.debug(f"Access granted for user: {user.username} (ID: {user.id})")
            return f(*args, **kwargs)
        except AuthenticationError as e:
                # Handle auth errors specifically (e.g., token expired, invalid)
                return jsonify({"error": str(e)}), 401
        except ConfigurationError as e: # Handle missing secret key during verification
                logger.critical(f"Auth configuration error during login_required: {e}")
                return jsonify({"error": "Internal server configuration error."}), 500
        except ApiError as e:
                # Handle service unavailable error
                return jsonify({"error": e.message}), e.status_code
        except Exception as e:
                # Catch unexpected errors during user retrieval
                logger.error(f"Error during login_required check: {e}", exc_info=True)
                return jsonify({"error": "Internal server error during authentication check."}), 500
    return decorated_function

def admin_required(f):
    """
    Decorator to ensure the user is logged in AND is an administrator.
    Must be used *after* @login_required.
    """
    @wraps(f)
    @login_required # Ensures login_required runs first and sets request.current_user
    def decorated_function(*args, **kwargs):
        # request.current_user is guaranteed to exist here if @login_required passed
        user = request.current_user
        # Check permissions object exists before accessing attributes
        if not user.permissions or not user.permissions.is_admin:
            logger.warning(f"Access denied: User '{user.username}' (ID: {user.id}) is not an admin.")
            # Raise specific error type for handler
            raise ForbiddenError("Admin privileges required.")

        logger.debug(f"Admin access granted for user: {user.username}")
        return f(*args, **kwargs)
    return decorated_function

# --- Permission-specific decorators ---

def _permission_required(permission_attr: str, error_message: str):
    """Generic factory for permission decorators."""
    def decorator(f):
        @wraps(f)
        @login_required # Always require login first
        def decorated_function(*args, **kwargs):
            user = request.current_user
            # Check if user has permissions object and the specific permission OR is admin
            has_perm = (user.permissions and getattr(user.permissions, permission_attr, False))
            is_admin = (user.permissions and user.permissions.is_admin)

            if not (has_perm or is_admin):
                logger.warning(f"Access denied for user '{user.username}': Lacks permission '{permission_attr}'.")
                raise ForbiddenError(error_message)

            logger.debug(f"Permission '{permission_attr}' granted for user: {user.username} (Admin={is_admin})")
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Define specific permission decorators using the factory
products_access_required = _permission_required(
    'can_access_products',
    'Access to product information required.'
)

fabrics_access_required = _permission_required(
    'can_access_fabrics',
    'Access to fabric information required.'
)

customer_panel_access_required = _permission_required(
    'can_access_customer_panel',
    'Access to customer panel required.'
)

fiscal_access_required = _permission_required(
    'can_access_fiscal',
    'Access to fiscal module required.'
)

accounts_receivable_access_required = _permission_required( # <<<--- ADDED
    'can_access_accounts_receivable',
    'Access to accounts receivable module required.'
)