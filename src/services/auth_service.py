# src/services/auth_service.py
# Handles user authentication, token generation/verification, and current user retrieval.

import jwt
from datetime import datetime, timedelta, timezone
from flask import current_app, request, session
from typing import Tuple, Optional, Dict, Any

# Import ORM models and Repository
from src.domain.user import User
from src.database.user_repository import UserRepository

# Import Session and session manager
from sqlalchemy.orm import Session
from src.database import get_db_session # Import the session context manager

from src.utils.logger import logger
from src.api.errors import AuthenticationError, InvalidTokenError, ExpiredTokenError, DatabaseError, ConfigurationError

class AuthService:
    """
    Service layer for user authentication and authorization token management using ORM.
    """

    def __init__(self, user_repository: UserRepository):
        """
        Initializes the AuthService.

        Args:
            user_repository: Instance of UserRepository.
        """
        self.user_repository = user_repository
        logger.info("AuthService initialized (ORM).")

    def login(self, username: str, password: str) -> Tuple[str, Dict[str, Any]]:
        """
        Authenticates a user, updates last login, and generates a JWT token.
        Uses a database session.

        Args:
            username: The user's username.
            password: The user's password.

        Returns:
            A tuple containing: (jwt_token, user_data_dict).

        Raises:
            AuthenticationError: If login fails due to invalid credentials or inactive user.
            DatabaseError: If a database issue occurs during user lookup or update.
        """
        logger.debug(f"Attempting login for user: {username}")

        try:
            # Obter sessão do banco de dados usando o context manager
            with get_db_session() as db:
                # 1. Buscar usuário
                user = self.user_repository.find_by_username(db, username)

                if not user:
                    logger.warning(f"Login failed: User '{username}' not found or inactive.")
                    raise AuthenticationError("Invalid username or password.")

                if not user.is_active:
                    logger.warning(f"Login failed: User '{username}' is inactive.")
                    raise AuthenticationError("User account is inactive.")

                if not user.verify_password(password):
                    logger.warning(f"Login failed: Incorrect password for user '{username}'.")
                    raise AuthenticationError("Invalid username or password.")

                # 2. Atualizar último login (dentro da mesma transação)
                self.user_repository.update_last_login(db, user.id)

                # 3. Gerar token e dados do usuário (após a lógica do DB)
                logger.info(f"Login successful for user '{username}' (ID: {user.id}). Generating token.")
                token = self._generate_token(user)

                # Obter dados do usuário APÓS o flush/commit potencial da sessão
                # O objeto 'user' pode ter sido atualizado (ex: last_login).
                # Usar to_dict para serializar.
                user_data = user.to_dict(include_hash=False)

                # Armazenar token na sessão Flask (opcional)
                session['token'] = token

                # A transação será commitada automaticamente ao sair do bloco 'with get_db_session()'

                return token, user_data

        except (AuthenticationError, DatabaseError):
            # Re-raise specific errors
            raise
        except Exception as e:
            # Capturar outros erros (ex: falha na geração do token)
            logger.error(f"Error during post-login processing for user '{username}': {e}", exc_info=True)
            raise AuthenticationError("Login process failed after authentication.") from e


    def _generate_token(self, user: User) -> str:
        """Generates a JWT token for the given user."""
        # Lógica interna não muda significativamente com ORM
        if not user or user.id is None: # User.permissions é carregado via relationship agora
            logger.error(f"Cannot generate token: Invalid user object provided. User: {user}")
            raise ValueError("Valid user object with ID required to generate token.")

        secret_key = current_app.config.get('SECRET_KEY')
        if not secret_key:
             logger.critical("JWT Secret Key is not configured!")
             raise ConfigurationError("JWT Secret Key is missing.")

        expiration_hours = current_app.config.get('TOKEN_EXPIRATION_HOURS', 24)
        expiration_time = datetime.now(timezone.utc) + timedelta(hours=expiration_hours)

        # Obter permissões do objeto relacionado
        perms_payload = {}
        if user.permissions:
             perms_payload = {
                  'adm': user.permissions.is_admin, # Usar nomes curtos no token se desejar
                  'prod': user.permissions.can_access_products,
                  'fab': user.permissions.can_access_fabrics,
                  'cust': user.permissions.can_access_customer_panel,
                  'fisc': user.permissions.can_access_fiscal,
                  'ar': user.permissions.can_access_accounts_receivable,
             }

        payload = {
            'user_id': user.id,
            'username': user.username,
            'perms': perms_payload, # Incluir permissões simplificadas
            'exp': expiration_time,
            'iat': datetime.now(timezone.utc)
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
        (Não interage com DB, permanece igual)
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
        found in the request headers or session, using a database session.

        Returns:
            The User object if authenticated and active, otherwise None.
        """
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        else:
            token = session.get('token')

        if not token:
            logger.debug("No authentication token found in request header or session.")
            return None

        try:
            payload = self.verify_token(token)
            user_id = payload.get('user_id')
            if not user_id:
                 logger.warning("Invalid token payload: Missing 'user_id'.")
                 return None

            # Usar sessão para buscar o usuário no banco
            with get_db_session() as db:
                # Fetch user from repository to ensure they still exist and are active
                user = self.user_repository.find_by_id(db, user_id)

                if not user:
                    logger.warning(f"Token valid, but user with ID {user_id} not found in database.")
                    return None
                if not user.is_active:
                    logger.warning(f"Token valid, but user {user.username} (ID: {user_id}) is inactive.")
                    return None

                # O objeto 'user' buscado pela sessão pode ser retornado.
                # O SQLAlchemy garante que os dados (inclusive permissões com joinedload)
                # estejam carregados.
                logger.debug(f"Authenticated user retrieved: {user.username} (ID: {user.id})")
                return user

        except (ExpiredTokenError, InvalidTokenError) as e:
            logger.debug(f"Token verification failed while getting current user: {e}")
            if 'token' in session: session.pop('token')
            return None
        except DatabaseError as e:
            # Erro ao buscar usuário no banco após token válido
            logger.error(f"Database error retrieving current user (ID: {user_id}): {e}", exc_info=True)
            return None
        except Exception as e:
             logger.error(f"Unexpected error retrieving current user: {e}", exc_info=True)
             return None

    def logout(self):
         """Logs out the current user by clearing the session token."""
         # Não interage com DB, permanece igual
         if 'token' in session:
              session.pop('token')
              logger.info("User logged out, session token cleared.")
              return True
         logger.debug("Logout called but no session token found.")
         return False