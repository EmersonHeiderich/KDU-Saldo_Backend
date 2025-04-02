# src/database/user_repository.py
# Handles database operations related to Users and UserPermissions using SQLAlchemy ORM.

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, delete, update # Import select, func, delete, update
from sqlalchemy.orm import Session, joinedload, selectinload # Import Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .base_repository import BaseRepository
from src.domain.user import User, UserPermissions # Import ORM models
from src.utils.logger import logger
from src.api.errors import DatabaseError, NotFoundError, ValidationError # Import custom errors

class UserRepository(BaseRepository):
    """
    Repository for managing User and UserPermissions data using SQLAlchemy ORM Sessions.
    Methods now expect a Session object to be passed in.
    """

    # O construtor ainda recebe Engine, mas não o usaremos diretamente nos métodos ORM.
    # def __init__(self, engine: Engine):
    #     super().__init__(engine)
    #     logger.info("UserRepository initialized with SQLAlchemy engine (ready for ORM sessions).")

    # _map_row_to_user removido, ORM cuida disso.

    def find_by_username(self, db: Session, username: str) -> Optional[User]:
        """
        Finds an active user by their username (case-insensitive) using ORM Session.
        """
        logger.debug(f"ORM: Finding active user by username '{username}'")
        try:
            # Usar select e options para carregar relacionamento
            stmt = (
                select(User)
                .options(joinedload(User.permissions)) # Eager load permissions
                .where(func.lower(User.username) == func.lower(username))
                .where(User.is_active == True)
            )
            user = db.scalars(stmt).first() # Pega o primeiro resultado ou None

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

    def find_by_id(self, db: Session, user_id: int) -> Optional[User]:
        """Finds a user by their ID using ORM Session (regardless of active status)."""
        logger.debug(f"ORM: Finding user by ID {user_id}")
        try:
            # session.get é otimizado para busca por PK
            # Usar options para carregar o relacionamento junto
            user = db.get(User, user_id, options=[joinedload(User.permissions)])
            if user:
                 logger.debug(f"ORM: User found by ID {user_id}.")
                 # Se permissions for None após joinedload, pode indicar inconsistência
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

    def get_all(self, db: Session) -> List[User]:
        """Retrieves all users from the database using ORM Session."""
        logger.debug("ORM: Retrieving all users")
        try:
            stmt = select(User).options(joinedload(User.permissions)).order_by(User.username)
            users = db.scalars(stmt).all()
            logger.debug(f"ORM: Retrieved {len(users)} users from database.")
            return list(users) # Converter para lista
        except SQLAlchemyError as e:
             logger.error(f"ORM: Database error retrieving all users: {e}", exc_info=True)
             raise DatabaseError(f"Database error retrieving all users: {e}") from e
        except Exception as e:
             logger.error(f"ORM: Unexpected error retrieving all users: {e}", exc_info=True)
             raise DatabaseError(f"Unexpected error retrieving all users: {e}") from e

    def add(self, db: Session, user: User) -> User:
        """Adds a new user and their permissions using ORM Session."""
        if not user.username or not user.password_hash or not user.name:
             raise ValueError("Missing required fields (username, password_hash, name) for User.")
        if user.permissions is None:
             # O relacionamento cascade deve cuidar disso, mas validar é bom.
             # Se você criar User sem UserPermissions, o cascade não vai criar permissões automaticamente.
             # É melhor garantir que o objeto User já tenha o objeto UserPermissions associado antes de chamar add.
             logger.warning(f"User object for '{user.username}' is missing associated UserPermissions object. Creating default.")
             user.permissions = UserPermissions() # Cria permissões padrão associadas
             # O backref/cascade cuidará do user_id ao adicionar o User.

        logger.debug(f"ORM: Adding user '{user.username}' to session")
        try:
            # Define timestamp se não estiver definido
            if user.created_at is None:
                user.created_at = datetime.now(timezone.utc)

            db.add(user) # Adiciona o usuário (e permissões via cascade) à sessão
            db.flush() # Opcional: Envia as alterações para o DB para obter IDs gerados, sem commitar.
                       # Útil se precisar do ID imediatamente após adicionar.
            logger.info(f"ORM: User '{user.username}' added to session (ID: {user.id}, Perm ID: {getattr(user.permissions, 'id', None)}). Commit pending.")
            # Commit é tratado externamente pelo get_db_session
            return user
        except IntegrityError as e:
            db.rollback() # Importante reverter em caso de erro
            logger.warning(f"ORM: Database integrity error adding user '{user.username}': {e}")
            # Analisar o erro para retornar mensagem mais específica (ex: duplicate username/email)
            error_info = str(e.orig).lower() if e.orig else str(e).lower()
            if "users_username_key" in error_info or "unique constraint" in error_info and "username" in error_info:
                 raise ValueError(f"Username '{user.username}' already exists.")
            if "users_email_key" in error_info or "unique constraint" in error_info and "email" in error_info and user.email:
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


    def update(self, db: Session, user_to_update: User) -> User:
        """Updates an existing user and their permissions using ORM Session."""
        if user_to_update.id is None:
            raise ValueError("Cannot update user without an ID.")
        if not user_to_update.password_hash: # Validar hash não vazio
             raise ValueError("Password hash cannot be empty for update.")

        logger.debug(f"ORM: Updating user ID {user_to_update.id} in session")
        try:
            # O objeto user_to_update já deve estar associado à sessão se foi
            # buscado anteriormente com find_by_id. Se for um objeto novo
            # representando um existente, usar db.merge() ou buscar primeiro.
            # Assumindo que user_to_update foi buscado ou está sendo merged.
            # Se user_to_update não veio da sessão atual, buscar primeiro:
            # existing_user = db.get(User, user_to_update.id)
            # if not existing_user:
            #     raise NotFoundError(f"User with ID {user_to_update.id} not found for update.")
            # # Copiar atributos atualizados (exceto ID e talvez permissões)
            # existing_user.name = user_to_update.name
            # existing_user.email = user_to_update.email
            # # ... etc ...
            # # Tratar permissões:
            # if existing_user.permissions and user_to_update.permissions:
            #     existing_user.permissions.is_admin = user_to_update.permissions.is_admin
            #     # ... copiar outras permissões ...
            # elif user_to_update.permissions:
            #     # Criar permissões se não existiam
            #     existing_user.permissions = user_to_update.permissions # Associa novo objeto
            # # A sessão detectará as mudanças em existing_user e seu relacionamento

            # Se user_to_update *já é* o objeto da sessão:
            # As modificações feitas nele já estão rastreadas pela sessão.
            # Apenas garantir que as permissões sejam tratadas.
            if user_to_update.permissions:
                 # Se o objeto permissions também veio da sessão, ok.
                 # Se for um novo objeto, ele precisa ser adicionado ou merged
                 # ou associado ao usuário que está na sessão. O cascade pode ajudar.
                 pass # Assumindo que o objeto User e Permissions foram manipulados corretamente antes de chamar update.

            db.flush() # Opcional: Enviar alterações para o DB sem commitar.
            logger.info(f"ORM: User ID {user_to_update.id} marked for update in session. Commit pending.")
            # Commit é tratado externamente
            return user_to_update
        except IntegrityError as e:
            db.rollback()
            logger.warning(f"ORM: Database integrity error updating user ID {user_to_update.id}: {e}")
            error_info = str(e.orig).lower() if e.orig else str(e).lower()
            if "users_email_key" in error_info or "unique constraint" in error_info and "email" in error_info:
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
        logger.debug(f"ORM: Deleting user ID {user_id}")
        try:
            user = db.get(User, user_id) # Busca o usuário
            if user:
                db.delete(user) # Marca para exclusão (cascade cuidará das permissões)
                db.flush() # Opcional
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
        logger.debug(f"ORM: Updating last_login for user ID {user_id}")
        try:
            user = db.get(User, user_id)
            if user:
                user.last_login = datetime.now(timezone.utc)
                db.flush() # Opcional
                logger.debug(f"ORM: User ID {user_id} last_login marked for update. Commit pending.")
                return True
            else:
                 logger.warning(f"ORM: Failed to update last_login for user ID {user_id} (user not found).")
                 return False
        except SQLAlchemyError as e:
            db.rollback() # Reverter se falhar
            logger.error(f"ORM: Failed to update last_login for user ID {user_id}: {e}", exc_info=True)
            # Não levantar DatabaseError aqui pode ser aceitável para não quebrar o login
            return False
        except Exception as e:
             db.rollback()
             logger.error(f"ORM: Unexpected error updating last_login for user ID {user_id}: {e}", exc_info=True)
             return False