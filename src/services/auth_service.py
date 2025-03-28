# src/services/auth_service.py
# Handles user authentication, token generation/verification, and current user retrieval.

import jwt
from datetime import datetime, timedelta, timezone
from flask import current_app, request, session
from typing import Tuple, Optional, Dict, Any
from src.domain.user import User
from src.database.user_repository import UserRepository
from src.utils.logger import logger
from src.api.errors import AuthenticationError, InvalidTokenError, ExpiredTokenError

class AuthService:
    """
    Service layer for user authentication and authorization token management.
    """

    def __init__(self, user_repository: UserRepository):
        """
        Initializes the AuthService.

        Args:
            user_repository: Instance of UserRepository for database access.
        """
        self.user_repository = user_repository
        logger.info("AuthService initialized.")

    def login(self, username: str, password: str) -> Tuple[str, Dict[str, Any]]:
        """
        Authenticates a user and generates a JWT token.

        Args:
            username: The user's username.
            password: The user's password.

        Returns:
            A tuple containing: (jwt_token, user_data_dict).

        Raises:
            AuthenticationError: If login fails due to invalid credentials or inactive user.
            DatabaseError: If a database issue occurs.
        """
        logger.debug(f"Attempting login for user: {username}")
        user = self.user_repository.find_by_username(username)

        if not user:
            logger.warning(f"Login failed: User '{username}' not found or inactive.")
            raise AuthenticationError("Invalid username or password.") # Generic error message

        if not user.is_active:
             logger.warning(f"Login failed: User '{username}' is inactive.")
             raise AuthenticationError("User account is inactive.")

        if not user.verify_password(password):
            logger.warning(f"Login failed: Incorrect password for user '{username}'.")
            raise AuthenticationError("Invalid username or password.") # Generic error message

        # Login successful
        try:
            self.user_repository.update_last_login(user.id)
            logger.info(f"Login successful for user '{username}' (ID: {user.id}). Generating token.")
            token = self._generate_token(user)
            user_data = user.to_dict() # Get user data without password hash
            # Add permissions directly if not nested correctly in to_dict by default
            if user.permissions:
                 user_data['permissions'] = user.permissions.to_dict()

            # Store token in session (optional, alternative to Authorization header)
            session['token'] = token

            return token, user_data

        except Exception as e:
             # Catch potential errors during token generation or last login update
             logger.error(f"Error during post-login processing for user '{username}': {e}", exc_info=True)
             # Depending on the error, you might still raise AuthenticationError or a more generic 500
             raise AuthenticationError("Login process failed after authentication.") from e


    def _generate_token(self, user: User) -> str:
        """Generates a JWT token for the given user."""
        if not user or user.id is None or user.permissions is None:
            logger.error(f"Cannot generate token: Invalid user object provided. User: {user}")
            raise ValueError("Valid user object with ID and permissions required to generate token.")

        secret_key = current_app.config.get('SECRET_KEY')
        if not secret_key:
             logger.critical("JWT Secret Key is not configured!")
             raise ConfigurationError("JWT Secret Key is missing.") # Use custom ConfigurationError if defined

        expiration_hours = current_app.config.get('TOKEN_EXPIRATION_HOURS', 24)
        expiration_time = datetime.now(timezone.utc) + timedelta(hours=expiration_hours)

        payload = {
            'user_id': user.id,
            'username': user.username,
            'is_admin': user.permissions.is_admin,
            # Include specific permissions if needed for frontend checks without hitting backend
            'perms': { # Example structure for permissions payload
                 'prod': user.permissions.can_access_products,
                 'fab': user.permissions.can_access_fabrics,
                 'cust': user.permissions.can_access_customer_panel,
                 'fisc': user.permissions.can_access_fiscal,
            },
            'exp': expiration_time,
            'iat': datetime.now(timezone.utc) # Issued at time
        }
        logger.debug(f"Generating JWT token for user {user.id} with payload: {payload}")
        try:
            token = jwt.encode(payload, secret_key, algorithm='HS256')
            return token
        except Exception as e:
            logger.error(f"Failed to encode JWT token: {e}", exc_info=True)
            raise RuntimeError("Failed to generate authentication token.") from e

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verifies a JWT token and returns its payload.

        Args:
            token: The JWT token string.

        Returns:
            The decoded payload dictionary.

        Raises:
            ExpiredTokenError: If the token has expired.
            InvalidTokenError: If the token is invalid or fails verification.
            ConfigurationError: If JWT Secret Key is missing.
        """
        secret_key = current_app.config.get('SECRET_KEY')
        if not secret_key:
             logger.critical("JWT Secret Key is not configured!")
             raise ConfigurationError("JWT Secret Key is missing.")

        try:
            payload = jwt.decode(
                token,
                secret_key,
                algorithms=['HS256']
            )
            logger.debug(f"Token verified successfully for user_id: {payload.get('user_id')}")
            # Optional: Add leeway for clock skew if needed: jwt.decode(..., leeway=timedelta(seconds=30))
            # Optional: Check 'iat' if necessary
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning(f"Token verification failed: Token has expired. Token: {token[:10]}...")
            raise ExpiredTokenError("Authentication token has expired.")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token verification failed: Invalid token. Error: {e}. Token: {token[:10]}...")
            raise InvalidTokenError(f"Invalid authentication token: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during token verification: {e}", exc_info=True)
            raise InvalidTokenError(f"Token verification failed due to an unexpected error: {e}")

    def get_current_user_from_request(self) -> Optional[User]:
        """
        Retrieves the currently authenticated user based on the token
        found in the request headers or session.

        Returns:
            The User object if authenticated and active, otherwise None.
        """
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            logger.debug("Token found in Authorization header.")
        else:
            token = session.get('token')
            if token:
                 logger.debug("Token found in session.")


        if not token:
            logger.debug("No authentication token found in request header or session.")
            return None

        try:
            payload = self.verify_token(token)
            user_id = payload.get('user_id')
            if not user_id:
                 logger.warning("Invalid token payload: Missing 'user_id'.")
                 return None

            # Fetch user from repository to ensure they still exist and are active
            user = self.user_repository.find_by_id(user_id)

            if not user:
                logger.warning(f"Token valid, but user with ID {user_id} not found in database.")
                return None
            if not user.is_active:
                 logger.warning(f"Token valid, but user {user.username} (ID: {user_id}) is inactive.")
                 return None

            logger.debug(f"Authenticated user retrieved: {user.username} (ID: {user.id})")
            return user

        except (ExpiredTokenError, InvalidTokenError) as e:
            logger.debug(f"Token verification failed while getting current user: {e}")
            # Optionally clear invalid session token
            if 'token' in session:
                 session.pop('token')
            return None
        except Exception as e:
             logger.error(f"Unexpected error retrieving current user: {e}", exc_info=True)
             return None

    def logout(self):
         """Logs out the current user by clearing the session token."""
         if 'token' in session:
              session.pop('token')
              logger.info("User logged out, session token cleared.")
              return True
         logger.debug("Logout called but no session token found.")
         return False # Indicate nothing was cleared


# Import custom error at the end
from src.api.errors import ConfigurationError