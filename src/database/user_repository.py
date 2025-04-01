# src/database/user_repository.py
# Handles database operations related to Users and UserPermissions using SQLAlchemy.

import sqlite3 # Manter temporariamente para capturar sqlite3.IntegrityError se ocorrer transição
from datetime import timezone, datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import text
from sqlalchemy.engine import Engine # Importar Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError # Importar erros SQLAlchemy

# Importar BaseRepository atualizado
from .base_repository import BaseRepository
from src.domain.user import User, UserPermissions
from src.utils.logger import logger
# Importar DatabaseError (NotFound não é mais lançado daqui)
from src.api.errors import DatabaseError, ValidationError

class UserRepository(BaseRepository):
    """
    Repository for managing User and UserPermissions data using SQLAlchemy.
    """

    # Aceita Engine no construtor
    def __init__(self, engine: Engine):
        super().__init__(engine)
        logger.info("UserRepository initialized with SQLAlchemy engine.")

    def _map_row_to_user(self, row: Optional[Dict[str, Any]]) -> Optional[User]:
        """Helper to map a database row (dict) to a User object."""
        # Esta função deve funcionar majoritariamente como antes,
        # pois SQLAlchemy RowMapping se comporta como dict.
        if not row:
            return None

        # Adapte nomes das colunas se mudaram (ex: permission_id)
        permission_data = {
            'id': row.get('permission_id'), # Usar .get() para segurança
            'user_id': row.get('id'),
            'is_admin': row.get('is_admin', False), # Default para False se ausente
            'can_access_products': row.get('can_access_products', False),
            'can_access_fabrics': row.get('can_access_fabrics', False),
            'can_access_customer_panel': row.get('can_access_customer_panel', False),
            'can_access_fiscal': row.get('can_access_fiscal', False),
            'can_access_accounts_receivable': row.get('can_access_accounts_receivable', False)
        }
        # Remover chaves de permissão do dict principal 'row'
        perm_keys_in_row = ['permission_id', 'is_admin', 'can_access_products', 'can_access_fabrics',
                            'can_access_customer_panel', 'can_access_fiscal', 'can_access_accounts_receivable']
        user_data = {k: v for k, v in row.items() if k not in perm_keys_in_row}

        # Adicionar dados de permissão ao dict do usuário
        user_data['permissions'] = permission_data

        user = User.from_dict(user_data) # Assume que User.from_dict pode lidar com isso
        if not user:
             logger.error(f"Failed to map row to User object. Row data: {row}")
             return None

        # Assegurar objeto de permissões (caso LEFT JOIN não encontre correspondência)
        if user and not user.permissions:
            logger.debug(f"No permission row found for user ID {user.id}, creating default permissions object.")
            user.permissions = UserPermissions(user_id=user.id) # Cria default
        elif user and user.permissions and user.permissions.user_id is None:
             # Define user_id se não veio da linha base
             user.permissions.user_id = user.id

        return user


    def find_by_username(self, username: str) -> Optional[User]:
        """
        Finds an active user by their username (case-insensitive - handled by DB if configured, otherwise use LOWER).
        """
        # CORRIGIR O PLACEHOLDER NA QUERY SQL AQUI
        query = """
            SELECT u.*,
                   p.id as permission_id, p.is_admin, p.can_access_products,
                   p.can_access_fabrics, p.can_access_customer_panel, p.can_access_fiscal,
                   p.can_access_accounts_receivable
            FROM users u
            LEFT JOIN user_permissions p ON u.id = p.user_id
            WHERE LOWER(u.username) = LOWER(:username) AND u.is_active = TRUE -- Usando LOWER() e :username
        """
        # Params já está correto como dicionário
        params = {'username': username}
        try:
            # Chama _execute do BaseRepository atualizado
            row = self._execute(query, params=params, fetch_mode="one")
            user = self._map_row_to_user(row)
            # Logging adaptado
            if user:
                 logger.debug(f"User found by username '{username}': ID {user.id}")
            else:
                 logger.debug(f"Active user not found by username '{username}'.")
            return user
        # TRATAMENTO DE ERRO PERMANECE O MESMO
        except DatabaseError as e:
             logger.error(f"Database error finding user by username '{username}': {e}", exc_info=True)
             # É importante retornar None aqui para que AuthService lance o AuthenticationError correto
             return None
        except Exception as e:
             logger.error(f"Unexpected error finding user by username '{username}': {e}", exc_info=True)
             return None

    def find_by_id(self, user_id: int) -> Optional[User]:
        """Finds a user by their ID (regardless of active status)."""
        # CORRIGIR O PLACEHOLDER NA QUERY SQL AQUI
        query = """
            SELECT u.*,
                   p.id as permission_id, p.is_admin, p.can_access_products,
                   p.can_access_fabrics, p.can_access_customer_panel, p.can_access_fiscal,
                   p.can_access_accounts_receivable
            FROM users u
            LEFT JOIN user_permissions p ON u.id = p.user_id
            WHERE u.id = :user_id -- Usando :user_id
        """
        # Params já está correto como dicionário
        params = {'user_id': user_id}
        try:
            row = self._execute(query, params=params, fetch_mode="one")
            user = self._map_row_to_user(row)
            if user:
                 logger.debug(f"User found by ID {user_id}.")
            else:
                 # Este log pode acontecer se o ID for inválido, não necessariamente um erro
                 logger.debug(f"User not found by ID {user_id}.")
            return user
        except DatabaseError as e:
             logger.error(f"Database error finding user by ID {user_id}: {e}", exc_info=True)
             return None
        except Exception as e:
             logger.error(f"Unexpected error finding user by ID {user_id}: {e}", exc_info=True)
             return None

    def get_all(self) -> List[User]:
        """Retrieves all users from the database."""
        query = """
            SELECT u.*,
                   p.id as permission_id, p.is_admin, p.can_access_products,
                   p.can_access_fabrics, p.can_access_customer_panel, p.can_access_fiscal,
                   p.can_access_accounts_receivable
            FROM users u
            LEFT JOIN user_permissions p ON u.id = p.user_id
            ORDER BY u.username
        """
        try:
            rows = self._execute(query, fetch_mode="all") # Sem params aqui
            users = [self._map_row_to_user(row) for row in rows]
            users = [user for user in users if user is not None]
            logger.debug(f"Retrieved {len(users)} users from database.")
            return users
        except DatabaseError as e:
             logger.error(f"Database error retrieving all users: {e}", exc_info=True)
             return []
        except Exception as e:
             logger.error(f"Unexpected error retrieving all users: {e}", exc_info=True)
             return []


    def add(self, user: User) -> User:
        """Adds a new user and their permissions within a single transaction."""
        if not user.username or not user.password_hash or not user.name:
             raise ValueError("Missing required fields (username, password_hash, name) for User.")
        if user.permissions is None:
             raise ValueError("User permissions must be set before adding the user.")

        user_query = """
            INSERT INTO users (username, password_hash, name, email, created_at, is_active)
            VALUES (:username, :password_hash, :name, :email, :created_at, :is_active)
            RETURNING id
        """
        user_params = {
            'username': user.username,
            'password_hash': user.password_hash,
            'name': user.name,
            'email': user.email,
            'created_at': user.created_at or datetime.now(timezone.utc), # Usar UTC se a coluna for TIMESTAMPTZ
            'is_active': user.is_active
        }

        perm_query = """
            INSERT INTO user_permissions
            (user_id, is_admin, can_access_products, can_access_fabrics, can_access_customer_panel, can_access_fiscal, can_access_accounts_receivable)
            VALUES (:user_id, :is_admin, :can_access_products, :can_access_fabrics, :can_access_customer_panel, :can_access_fiscal, :can_access_accounts_receivable)
            RETURNING id
        """
        # Perm params definidos depois de obter user_id

        try:
            # --- CORREÇÃO: Executar diretamente na conexão da transação ---
            with self.engine.connect() as connection:
                with connection.begin(): # Inicia transação explícita
                    # Executar INSERT do usuário
                    result_user = connection.execute(text(user_query), user_params)
                    user_id = result_user.scalar_one() # Obter o ID retornado

                    user.id = user_id
                    if user.permissions: # Garantir que permissions existe
                        user.permissions.user_id = user_id
                    logger.debug(f"User '{user.username}' inserted with ID: {user_id} (within transaction).")

                    # Preparar e executar INSERT de permissões NA MESMA TRANSAÇÃO
                    if user.permissions:
                         perm_params = {
                            'user_id': user_id,
                            'is_admin': user.permissions.is_admin,
                            'can_access_products': user.permissions.can_access_products,
                            'can_access_fabrics': user.permissions.can_access_fabrics,
                            'can_access_customer_panel': user.permissions.can_access_customer_panel,
                            'can_access_fiscal': user.permissions.can_access_fiscal,
                            'can_access_accounts_receivable': user.permissions.can_access_accounts_receivable
                         }
                         result_perm = connection.execute(text(perm_query), perm_params)
                         perm_id = result_perm.scalar_one_or_none()
                         if perm_id:
                              user.permissions.id = perm_id
                         logger.debug(f"User permissions for user ID {user_id} inserted (within transaction).")
                    else:
                        # Deveria ter sido pego pela validação inicial, mas por segurança:
                        logger.error(f"User object for ID {user_id} is missing permissions during add operation.")
                        raise DatabaseError(f"Internal inconsistency: Permissions object missing for user {user_id} during creation.")

                # Se sair do 'with connection.begin()' sem erro, COMMIT é feito.
                logger.info(f"User '{user.username}' (ID: {user.id}) and permissions added and committed successfully.")
                return user
            # ----------------------------------------------------------------

        # Tratamento de erro permanece o mesmo, pois o rollback é automático
        except IntegrityError as e:
            logger.warning(f"Database integrity error adding user '{user.username}': {e}")
            error_str = str(e).lower()
            if "users_username_key" in error_str or "unique constraint" in error_str and "username" in error_str:
                 raise ValueError(f"Username '{user.username}' already exists.")
            if "users_email_key" in error_str or "unique constraint" in error_str and "email" in error_str and user.email:
                 raise ValueError(f"Email '{user.email}' already exists.")
            # A FK violation não deve ocorrer aqui com a lógica corrigida, mas manter por segurança
            if "user_permissions_user_id_fkey" in error_str:
                 raise DatabaseError(f"Permissions foreign key error for user ID {user.id}. Data inconsistency.")
            raise DatabaseError(f"Failed to add user due to integrity constraint: {e}") from e
        except SQLAlchemyError as e:
            logger.error(f"Database error adding user '{user.username}': {e}", exc_info=True)
            if "No rows returned for scalar_one()" in str(e):
                 raise DatabaseError("Failed to get generated ID after insert.") from e
            raise DatabaseError(f"Failed to add user: {e}") from e
        except Exception as e:
             logger.error(f"Unexpected error adding user '{user.username}': {e}", exc_info=True)
             raise DatabaseError(f"An unexpected error occurred while adding user: {e}") from e

    def update(self, user: User) -> bool:
        """Updates an existing user and their permissions within a transaction."""
        if user.id is None:
            raise ValueError("Cannot update user without an ID.")
        if user.permissions is None:
             raise ValueError("User permissions are missing for update.")
        if user.permissions.user_id is not None and user.permissions.user_id != user.id:
             raise ValueError("User permissions user_id mismatch for update.")
        if not user.password_hash:
             raise ValueError("Password hash cannot be empty for update.")

        user_query = """
            UPDATE users SET
                name = :name, email = :email, is_active = :is_active,
                last_login = :last_login, password_hash = :password_hash
            WHERE id = :user_id
        """
        user_params = {
            'name': user.name, 'email': user.email, 'is_active': user.is_active,
            'last_login': user.last_login, 'password_hash': user.password_hash,
            'user_id': user.id
        }

        perm_update_query = """
            UPDATE user_permissions SET
                is_admin = :is_admin,
                can_access_products = :can_access_products,
                can_access_fabrics = :can_access_fabrics,
                can_access_customer_panel = :can_access_customer_panel,
                can_access_fiscal = :can_access_fiscal,
                can_access_accounts_receivable = :can_access_accounts_receivable
            WHERE user_id = :user_id
        """
        perm_insert_query = """
            INSERT INTO user_permissions
            (user_id, is_admin, can_access_products, can_access_fabrics, can_access_customer_panel, can_access_fiscal, can_access_accounts_receivable)
            VALUES (:user_id, :is_admin, :can_access_products, :can_access_fabrics, :can_access_customer_panel, :can_access_fiscal, :can_access_accounts_receivable)
        """
        perm_params = {
            'user_id': user.id,
            'is_admin': user.permissions.is_admin,
            'can_access_products': user.permissions.can_access_products,
            'can_access_fabrics': user.permissions.can_access_fabrics,
            'can_access_customer_panel': user.permissions.can_access_customer_panel,
            'can_access_fiscal': user.permissions.can_access_fiscal,
            'can_access_accounts_receivable': user.permissions.can_access_accounts_receivable
        }
        perm_check_query = "SELECT 1 FROM user_permissions WHERE user_id = :user_id"
        perm_check_params = {'user_id': user.id}

        user_rows_affected = 0
        perm_rows_affected = 0

        try:
            with self.engine.connect() as connection:
                with connection.begin(): # Inicia transação
                    # Atualizar usuário
                    result_user = connection.execute(text(user_query), user_params)
                    user_rows_affected = result_user.rowcount

                    # Verificar se permissões existem
                    perm_exists = connection.execute(text(perm_check_query), perm_check_params).scalar_one_or_none()

                    if perm_exists:
                         # Atualizar permissões existentes
                         result_perm = connection.execute(text(perm_update_query), perm_params)
                         perm_rows_affected = result_perm.rowcount
                    else:
                         # Inserir permissões se não existirem
                         connection.execute(text(perm_insert_query), perm_params)
                         perm_rows_affected = 1 # Assumimos 1 linha inserida

            logger.info(f"User ID {user.id} update transaction completed. User rows: {user_rows_affected}, Perm rows: {perm_rows_affected}")
            return user_rows_affected > 0 or perm_rows_affected > 0

        except IntegrityError as e:
             logger.warning(f"Database integrity error updating user ID {user.id}: {e}")
             error_str = str(e).lower()
             # Verificar constraint de email ÚNICO aqui também
             if "users_email_key" in error_str or "unique constraint" in error_str and "email" in error_str:
                  raise ValueError(f"Email '{user.email}' is already in use by another user.")
             raise DatabaseError(f"Failed to update user due to integrity constraint: {e}") from e
        except SQLAlchemyError as e:
            logger.error(f"Database error updating user ID {user.id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to update user: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error updating user ID {user.id}: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred while updating user: {e}") from e


    def delete(self, user_id: int) -> bool:
        """Deletes a user by their ID within a transaction."""
        query = "DELETE FROM users WHERE id = :user_id"
        params = {'user_id': user_id}
        rows_affected = 0
        try:
            # --- CORREÇÃO: Usar transação explícita ---
            with self.engine.connect() as connection:
                with connection.begin(): # Inicia transação
                    result = connection.execute(text(query), params)
                    rows_affected = result.rowcount
            # -----------------------------------------

            if rows_affected > 0:
                logger.info(f"User ID {user_id} deleted successfully (Permissions CASCADE expected).")
                return True
            else:
                logger.warning(f"Attempted to delete user ID {user_id}, but user was not found or delete failed.")
                return False

        except IntegrityError as e:
             logger.error(f"Integrity error deleting user ID {user_id}: {e}", exc_info=True)
             raise DatabaseError(f"Failed to delete user due to integrity constraint: {e}") from e
        except SQLAlchemyError as e:
            logger.error(f"Database error deleting user ID {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to delete user: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error deleting user ID {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred while deleting user: {e}") from e

    def update_last_login(self, user_id: int) -> bool:
        """Updates the last_login timestamp for a user within a transaction."""
        query = "UPDATE users SET last_login = :now WHERE id = :user_id"
        from datetime import timezone # Importar timezone
        params = {'now': datetime.now(timezone.utc), 'user_id': user_id}
        rows_affected = 0
        try:
            with self.engine.connect() as connection:
                with connection.begin(): # Inicia transação
                    result = connection.execute(text(query), params)
                    rows_affected = result.rowcount

            if rows_affected > 0:
                 logger.debug(f"Updated last_login for user ID {user_id}.")
                 return True
            else:
                 logger.warning(f"Failed to update last_login for user ID {user_id} (user not found?).")
                 return False
        except SQLAlchemyError as e:
             logger.error(f"Failed to update last_login for user ID {user_id}: {e}", exc_info=True)
             return False
        except Exception as e:
             logger.error(f"Unexpected error updating last_login for user ID {user_id}: {e}", exc_info=True)
             return False

    def update_last_login(self, user_id: int) -> bool:
        """Updates the last_login timestamp for a user."""
        query = "UPDATE users SET last_login = :now WHERE id = :user_id"
        params = {'now': datetime.now(), 'user_id': user_id}
        try:
            # Envolve em transação para garantir atomicidade (boa prática)
            with self.engine.connect() as connection:
                with connection.begin():
                    result = connection.execute(text(query), params)
                    rows_affected = result.rowcount

            if rows_affected is not None and rows_affected > 0:
                 logger.debug(f"Updated last_login for user ID {user_id}.")
                 return True
            else:
                 logger.warning(f"Failed to update last_login for user ID {user_id} (user not found?).")
                 return False
        except SQLAlchemyError as e:
             logger.error(f"Failed to update last_login for user ID {user_id}: {e}", exc_info=True)
             # Não relançar como DatabaseError para não quebrar o fluxo de login necessariamente
             return False
        except Exception as e:
             logger.error(f"Unexpected error updating last_login for user ID {user_id}: {e}", exc_info=True)
             return False