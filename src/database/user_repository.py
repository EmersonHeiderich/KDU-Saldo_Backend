# src/database/user_repository.py
# Handles database operations related to Users and UserPermissions using SQLAlchemy ORM.

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func, delete, update
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .base_repository import BaseRepository
from src.utils.logger import logger
from src.api.errors import DatabaseError, NotFoundError, ValidationError

# --- NENHUM import de src.domain.user aqui ---

class UserRepository(BaseRepository):
    """
    Repository for managing User and UserPermissions data using SQLAlchemy ORM Sessions.
    Methods now expect a Session object to be passed in.
    """

    def find_by_username(self, db: Session, username: str) -> Optional["User"]: # <<<--- Usar string 'User'
        """
        Finds an active user by their username (case-insensitive) using ORM Session.
        """
        # Importar a classe User *dentro* do método
        # Isso adia a importação até a execução, quebrando o ciclo durante a análise inicial.
        try:
            from src.domain.user import User
        except ImportError:
            logger.critical("Falha ao importar src.domain.user dentro de find_by_username. Ciclo pode persistir.")
            raise

        logger.debug(f"ORM: Finding active user by username '{username}'")
        try:
            stmt = (
                select(User) # Passar a classe importada localmente
                .options(joinedload(User.permissions)) # joinedload usa o relationship, não precisa importar UserPermissions aqui
                .where(func.lower(User.username) == func.lower(username))
                .where(User.is_active == True)
            )
            user = db.scalars(stmt).first()

            if user:
                logger.debug(f"ORM: User found by username '{username}': ID {user.id}")
            else:
                logger.debug(f"ORM: Active user not found by username '{username}'.")
            return user
        except SQLAlchemyError as e:
            logger.error(f"ORM: Database error finding user by username '{username}': {e}", exc_info=True)
            raise DatabaseError(f"Database error finding user by username: {e}") from e
        except Exception as e:
            logger.error(f"ORM: Unexpected error finding user by username '{username}': {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error finding user by username: {e}") from e

    def find_by_id(self, db: Session, user_id: int) -> Optional["User"]: # <<<--- Usar string 'User'
        """Finds a user by their ID using ORM Session (regardless of active status)."""
        # Importar a classe User *dentro* do método
        try:
            from src.domain.user import User
        except ImportError:
            logger.critical("Falha ao importar src.domain.user dentro de find_by_id. Ciclo pode persistir.")
            raise

        logger.debug(f"ORM: Finding user by ID {user_id}")
        try:
            # db.get precisa da classe concreta
            user = db.get(User, user_id, options=[joinedload(User.permissions)]) # joinedload usa o relationship
            if user:
                 logger.debug(f"ORM: User found by ID {user_id}.")
                 # A verificação de user.permissions é feita no objeto retornado
                 if user.permissions is None:
                      logger.warning(f"ORM: User ID {user_id} found, but permissions relationship is None. Data inconsistency?")
            else:
                 logger.debug(f"ORM: User not found by ID {user_id}.")
            return user
        except SQLAlchemyError as e:
            logger.error(f"ORM: Database error finding user by ID {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Database error finding user by ID: {e}") from e
        except Exception as e:
            logger.error(f"ORM: Unexpected error finding user by ID {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error finding user by ID: {e}") from e

    def get_all(self, db: Session) -> List["User"]: # <<<--- Usar string 'User'
        """Retrieves all users from the database using ORM Session."""
        # Importar a classe User *dentro* do método
        try:
            from src.domain.user import User
        except ImportError:
            logger.critical("Falha ao importar src.domain.user dentro de get_all. Ciclo pode persistir.")
            raise

        logger.debug("ORM: Retrieving all users")
        try:
            # select precisa da classe concreta
            stmt = select(User).options(joinedload(User.permissions)).order_by(User.username)
            users = db.scalars(stmt).all()
            logger.debug(f"ORM: Retrieved {len(users)} users from database.")
            return list(users)
        except SQLAlchemyError as e:
             logger.error(f"ORM: Database error retrieving all users: {e}", exc_info=True)
             raise DatabaseError(f"Database error retrieving all users: {e}") from e
        except Exception as e:
             logger.error(f"ORM: Unexpected error retrieving all users: {e}", exc_info=True)
             raise DatabaseError(f"Unexpected error retrieving all users: {e}") from e

    # Para 'add' e 'update', o tipo do argumento 'user' já está anotado como string "User".
    # Não precisamos importar a classe User aqui, pois estamos trabalhando com o objeto recebido.
    def add(self, db: Session, user: "User") -> "User":
        """Adds a new user and their permissions using ORM Session."""
        if not user.username or not user.password_hash or not user.name:
             raise ValueError("Missing required fields (username, password_hash, name) for User.")
        if user.permissions is None:
             # Se precisar *criar* UserPermissions aqui, importe localmente
             try:
                 from src.domain.user import UserPermissions
             except ImportError:
                 logger.critical("Falha ao importar src.domain.user.UserPermissions dentro de add. Ciclo pode persistir.")
                 raise
             logger.warning(f"User object for '{user.username}' is missing associated UserPermissions object. Creating default.")
             user.permissions = UserPermissions()

        logger.debug(f"ORM: Adding user '{user.username}' to session")
        try:
            if user.created_at is None:
                user.created_at = datetime.now(timezone.utc)

            db.add(user) # Adiciona o objeto user (que deve ser uma instância de User)
            db.flush() # Garante que o ID seja gerado se necessário antes do commit
            logger.info(f"ORM: User '{user.username}' added to session (ID: {user.id}, Perm ID: {getattr(user.permissions, 'id', None)}). Commit pending.")
            return user
        except IntegrityError as e:
            db.rollback()
            logger.warning(f"ORM: Database integrity error adding user '{user.username}': {e}")
            error_info = str(e.orig).lower() if e.orig else str(e).lower()
            if "users_username_key" in error_info or "uq_users_username" in error_info:
                 raise ValueError(f"Username '{user.username}' already exists.")
            if "users_email_key" in error_info or "uq_users_email" in error_info and user.email:
                 raise ValueError(f"Email '{user.email}' already exists.")
            raise DatabaseError(f"Failed to add user due to integrity constraint: {e}") from e
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"ORM: Database error adding user '{user.username}': {e}", exc_info=True)
            raise DatabaseError(f"Failed to add user: {e}") from e
        except Exception as e:
            db.rollback()
            logger.error(f"ORM: Unexpected error adding user '{user.username}': {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred while adding user: {e}") from e

    def update(self, db: Session, user_to_update: "User") -> "User":
        """Updates an existing user and their permissions using ORM Session."""
        if user_to_update.id is None: raise ValueError("Cannot update user without an ID.")
        if not user_to_update.password_hash: raise ValueError("Password hash cannot be empty for update.")

        logger.debug(f"ORM: Updating user ID {user_to_update.id} in session")
        try:
            # A abordagem mais segura é anexar o objeto à sessão se ele não estiver
            # Isso garante que as mudanças sejam rastreadas e aplicadas.
            if not db.object_session(user_to_update): # Verifica se o objeto já pertence a esta sessão
                 logger.debug(f"User object {user_to_update.id} not part of current session. Attaching or merging...")
                 # Tentar adicionar; se falhar (detached instance error), fazer merge.
                 # Ou simplesmente usar merge diretamente. Merge é geralmente seguro para upserts.
                 user_in_session = db.merge(user_to_update)
            else:
                 user_in_session = user_to_update # Já está na sessão

            db.flush() # Envia as alterações pendentes para o DB
            logger.info(f"ORM: User ID {user_in_session.id} marked for update in session. Commit pending.")
            return user_in_session
        except IntegrityError as e:
            db.rollback()
            logger.warning(f"ORM: Database integrity error updating user ID {user_to_update.id}: {e}")
            error_info = str(e.orig).lower() if e.orig else str(e).lower()
            if "users_email_key" in error_info or "uq_users_email" in error_info:
                 raise ValueError(f"Email '{user_to_update.email}' is already in use by another user.")
            raise DatabaseError(f"Failed to update user due to integrity constraint: {e}") from e
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"ORM: Database error updating user ID {user_to_update.id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to update user: {e}") from e
        except Exception as e:
            db.rollback()
            logger.error(f"ORM: Unexpected error updating user ID {user_to_update.id}: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred while updating user: {e}") from e

    def delete(self, db: Session, user_id: int) -> bool:
        """Deletes a user by their ID using ORM Session."""
        # Importar a classe User *dentro* do método
        try:
            from src.domain.user import User
        except ImportError:
            logger.critical("Falha ao importar src.domain.user dentro de delete. Ciclo pode persistir.")
            raise

        logger.debug(f"ORM: Deleting user ID {user_id}")
        try:
            user = db.get(User, user_id) # Passa a classe
            if user:
                db.delete(user) # Marca para exclusão (cascade cuidará das permissões)
                db.flush() # Opcional, mas útil para garantir que a exclusão seja processada antes do commit
                logger.info(f"ORM: User ID {user_id} marked for deletion in session. Commit pending.")
                return True
            else:
                logger.warning(f"ORM: Attempted to delete user ID {user_id}, but user was not found.")
                return False
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"ORM: Database error deleting user ID {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to delete user: {e}") from e
        except Exception as e:
            db.rollback()
            logger.error(f"ORM: Unexpected error deleting user ID {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred while deleting user: {e}") from e

    def update_last_login(self, db: Session, user_id: int) -> bool:
        """Updates the last_login timestamp for a user using ORM Session."""
        # Importar a classe User *dentro* do método
        try:
            from src.domain.user import User
        except ImportError:
            logger.critical("Falha ao importar src.domain.user dentro de update_last_login. Ciclo pode persistir.")
            raise

        logger.debug(f"ORM: Updating last_login for user ID {user_id}")
        try:
            user = db.get(User, user_id) # Passa a classe
            if user:
                user.last_login = datetime.now(timezone.utc)
                # O flush não é estritamente necessário aqui se o commit for feito logo depois,
                # mas pode ser útil se você precisar ler o valor atualizado na mesma transação.
                # db.flush()
                logger.debug(f"ORM: User ID {user_id} last_login marked for update. Commit pending.")
                return True
            else:
                 logger.warning(f"ORM: Failed to update last_login for user ID {user_id} (user not found).")
                 return False
        except SQLAlchemyError as e:
            # Não reverte a sessão aqui, pois pode ser parte de uma transação maior (login)
            logger.error(f"ORM: Failed to update last_login for user ID {user_id}: {e}", exc_info=True)
            # Retorna False, mas não levanta erro para não quebrar o login por isso
            return False
        except Exception as e:
             # Não reverte a sessão aqui
             logger.error(f"ORM: Unexpected error updating last_login for user ID {user_id}: {e}", exc_info=True)
             return False
