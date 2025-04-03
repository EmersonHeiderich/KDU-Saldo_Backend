# src/services/auth_service.py
# Handles user authentication, token generation/verification, and current user retrieval.

import jwt
from datetime import datetime, timedelta, timezone
from flask import current_app, request, session
from typing import Tuple, Optional, Dict, Any

from src.domain.user import User
from src.database.user_repository import UserRepository
from src.database import get_db_session

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
        logger.debug(f"Tentando login para usuário: {username}")

        try:
            with get_db_session() as db:
                user = self.user_repository.find_by_username(db, username)

                if not user:
                    logger.warning(f"Login falhou: Usuário '{username}' não encontrado ou inativo.")
                    raise AuthenticationError("Invalid username or password.")

                if not user.is_active:
                    logger.warning(f"Login falhou: Usuário '{username}' está inativo.")
                    raise AuthenticationError("User account is inactive.")

                if not user.verify_password(password):
                    logger.warning(f"Login falhou: Senha incorreta para usuário '{username}'.")
                    raise AuthenticationError("Invalid username or password.")

                self.user_repository.update_last_login(db, user.id)

                logger.info(f"Login bem-sucedido para usuário '{username}' (ID: {user.id}). Gerando token.")
                token = self._generate_token(user)

                user_data = user.to_dict(include_hash=False)

                session['token'] = token

                return token, user_data

        except (AuthenticationError, DatabaseError):
            raise
        except Exception as e:
            logger.error(f"Erro durante processamento pós-login para usuário '{username}': {e}", exc_info=True)
            raise AuthenticationError("Login process failed after authentication.") from e


    def _generate_token(self, user: User) -> str:
        """Generates a JWT token for the given user."""
        if not user or user.id is None:
            logger.error(f"Não é possível gerar token: Objeto de usuário inválido fornecido. Usuário: {user}")
            raise ValueError("Valid user object with ID required to generate token.")

        secret_key = current_app.config.get('SECRET_KEY')
        if not secret_key:
             logger.critical("Chave Secreta JWT não está configurada!")
             raise ConfigurationError("JWT Secret Key is missing.")

        expiration_hours = current_app.config.get('TOKEN_EXPIRATION_HOURS', 24)
        expiration_time = datetime.now(timezone.utc) + timedelta(hours=expiration_hours)

        perms_payload = {}
        if user.permissions:
             perms_payload = {
                  'adm': user.permissions.is_admin,
                  'prod': user.permissions.can_access_products,
                  'fab': user.permissions.can_access_fabrics,
                  'cust': user.permissions.can_access_customer_panel,
                  'fisc': user.permissions.can_access_fiscal,
                  'ar': user.permissions.can_access_accounts_receivable,
             }

        payload = {
            'user_id': user.id,
            'username': user.username,
            'perms': perms_payload,
            'exp': expiration_time,
            'iat': datetime.now(timezone.utc)
        }
        logger.debug(f"Gerando token JWT para usuário {user.id} com payload: {payload}")
        try:
            token = jwt.encode(payload, secret_key, algorithm='HS256')
            return token
        except Exception as e:
            logger.error(f"Falha ao codificar token JWT: {e}", exc_info=True)
            raise RuntimeError("Failed to generate authentication token.") from e

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verifies a JWT token and returns its payload.
        """
        secret_key = current_app.config.get('SECRET_KEY')
        if not secret_key:
             logger.critical("Chave Secreta JWT não está configurada!")
             raise ConfigurationError("JWT Secret Key is missing.")

        try:
            payload = jwt.decode(
                token,
                secret_key,
                algorithms=['HS256']
            )
            logger.debug(f"Token verificado com sucesso para user_id: {payload.get('user_id')}")
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning(f"Verificação de token falhou: Token expirado. Token: {token[:10]}...")
            raise ExpiredTokenError("Authentication token has expired.")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Verificação de token falhou: Token inválido. Erro: {e}. Token: {token[:10]}...")
            raise InvalidTokenError(f"Invalid authentication token: {e}")
        except Exception as e:
            logger.error(f"Erro inesperado durante verificação de token: {e}", exc_info=True)
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
            logger.debug("Nenhum token de autenticação encontrado no cabeçalho da requisição ou na sessão.")
            return None

        try:
            payload = self.verify_token(token)
            user_id = payload.get('user_id')
            if not user_id:
                 logger.warning("Payload de token inválido: 'user_id' ausente.")
                 return None

            with get_db_session() as db:
                user = self.user_repository.find_by_id(db, user_id)

                if not user:
                    logger.warning(f"Token válido, mas usuário com ID {user_id} não encontrado no banco de dados.")
                    return None
                if not user.is_active:
                    logger.warning(f"Token válido, mas usuário {user.username} (ID: {user_id}) está inativo.")
                    return None

                logger.debug(f"Usuário autenticado recuperado: {user.username} (ID: {user.id})")
                return user

        except (ExpiredTokenError, InvalidTokenError) as e:
            logger.debug(f"Verificação de token falhou ao obter usuário atual: {e}")
            if 'token' in session: session.pop('token')
            return None
        except DatabaseError as e:
            logger.error(f"Erro de banco de dados ao recuperar usuário atual (ID: {user_id}): {e}", exc_info=True)
            return None
        except Exception as e:
             logger.error(f"Erro inesperado ao recuperar usuário atual: {e}", exc_info=True)
             return None

    def logout(self):
         """Logs out the current user by clearing the session token."""
         if 'token' in session:
              session.pop('token')
              logger.info("Usuário deslogado, token de sessão removido.")
              return True
         logger.debug("Logout chamado mas nenhum token de sessão encontrado.")
         return False