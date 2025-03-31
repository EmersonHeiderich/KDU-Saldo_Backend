# src/database/user_repository.py
# Handles database operations related to Users and UserPermissions.

import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from .base_repository import BaseRepository
from .connection_pool import ConnectionPool
from src.domain.user import User, UserPermissions
from src.utils.logger import logger
from src.api.errors import DatabaseError, NotFoundError

class UserRepository(BaseRepository):
    """
    Repository for managing User and UserPermissions data in the database.
    """

    def __init__(self, connection_pool: ConnectionPool):
        super().__init__(connection_pool)
        logger.info("UserRepository initialized.")

    def _map_row_to_user(self, row: Optional[Dict[str, Any]]) -> Optional[User]:
        """Helper to map a database row (dict) to a User object."""
        if not row:
            return None

        # Pop permission fields to create UserPermissions object separately
        permission_data = {
            'id': row.pop('permission_id', None),
            'user_id': row.get('id'), # Use user's ID
            'is_admin': row.pop('is_admin', 0),
            'can_access_products': row.pop('can_access_products', 0),
            'can_access_fabrics': row.pop('can_access_fabrics', 0),
            'can_access_customer_panel': row.pop('can_access_customer_panel', 0),
            'can_access_fiscal': row.pop('can_access_fiscal', 0),
            'can_access_accounts_receivable': row.pop('can_access_accounts_receivable', 0) # <<<--- ADDED
        }
        # Remaining fields are for the User object
        user_data = row
        user_data['permissions'] = permission_data # Nest permission dict for User.from_dict

        user = User.from_dict(user_data)
        if not user:
             logger.error(f"Failed to map row to User object. Row data: {row}") # Log original row data
             return None # Handle potential errors in User.from_dict

        # Ensure permissions object is correctly formed even if no permission row existed (LEFT JOIN)
        if user and not user.permissions:
             logger.debug(f"No permission row found for user ID {user.id}, creating default permissions object.")
             # Create default permissions ensuring fiscal is False
             user.permissions = UserPermissions(
                  user_id=user.id,
                  is_admin=False,
                  can_access_products=False,
                  can_access_fabrics=False,
                  can_access_customer_panel=False,
                  can_access_fiscal=False,
                  can_access_accounts_receivable=False
             )
        elif user and user.permissions and user.permissions.user_id is None:
             # Set user_id if User.from_dict didn't get it from the base row
             user.permissions.user_id = user.id

        return user


    def find_by_username(self, username: str) -> Optional[User]:
        """
        Finds an active user by their username (case-insensitive).

        Args:
            username: The username to search for.

        Returns:
            A User object if found and active, otherwise None.
        """
        # COLLATE NOCASE in CREATE TABLE handles case-insensitivity at DB level
        query = """
            SELECT u.*, p.id as permission_id, p.is_admin, p.can_access_products,
                   p.can_access_fabrics, p.can_access_customer_panel, p.can_access_fiscal, p.can_access_accounts_receivable -- <<<--- ADDED
            FROM users u
            LEFT JOIN user_permissions p ON u.id = p.user_id
            WHERE u.username = ? AND u.is_active = 1
        """
        try:
            row = self._execute(query, (username,), fetch_mode="one")
            user = self._map_row_to_user(row)
            if user:
                 logger.debug(f"User found by username '{username}': ID {user.id}")
            else:
                 logger.debug(f"Active user not found by username '{username}'.")
            return user
        except DatabaseError as e:
             logger.error(f"Database error finding user by username '{username}': {e}", exc_info=True)
             return None
        except Exception as e:
             logger.error(f"Unexpected error finding user by username '{username}': {e}", exc_info=True)
             return None

    def find_by_id(self, user_id: int) -> Optional[User]:
        """
        Finds a user by their ID (regardless of active status).

        Args:
            user_id: The ID of the user.

        Returns:
            A User object if found, otherwise None.
        """
        query = """
            SELECT u.*, p.id as permission_id, p.is_admin, p.can_access_products,
                   p.can_access_fabrics, p.can_access_customer_panel, p.can_access_fiscal, p.can_access_accounts_receivable  -- <<<--- ADDED
            FROM users u
            LEFT JOIN user_permissions p ON u.id = p.user_id
            WHERE u.id = ?
        """
        try:
            row = self._execute(query, (user_id,), fetch_mode="one")
            user = self._map_row_to_user(row)
            if user:
                 logger.debug(f"User found by ID {user_id}.")
            else:
                 logger.debug(f"User not found by ID {user_id}.")
            return user
        except DatabaseError as e:
             logger.error(f"Database error finding user by ID {user_id}: {e}", exc_info=True)
             return None
        except Exception as e:
             logger.error(f"Unexpected error finding user by ID {user_id}: {e}", exc_info=True)
             return None

    def get_all(self) -> List[User]:
        """
        Retrieves all users from the database.

        Returns:
            A list of User objects.
        """
        query = """
            SELECT u.*, p.id as permission_id, p.is_admin, p.can_access_products,
                   p.can_access_fabrics, p.can_access_customer_panel, p.can_access_fiscal, p.can_access_accounts_receivable -- <<<--- ADDED
            FROM users u
            LEFT JOIN user_permissions p ON u.id = p.user_id
            ORDER BY u.username
        """
        try:
            rows = self._execute(query, fetch_mode="all")
            users = [self._map_row_to_user(row) for row in rows]
            # Filter out None results from potential mapping errors
            users = [user for user in users if user is not None]
            logger.debug(f"Retrieved {len(users)} users from database.")
            return users
        except DatabaseError as e:
             logger.error(f"Database error retrieving all users: {e}", exc_info=True)
             return [] # Return empty list on error
        except Exception as e:
             logger.error(f"Unexpected error retrieving all users: {e}", exc_info=True)
             return []


    def add(self, user: User) -> User:
        """
        Adds a new user and their permissions to the database.

        Args:
            user: A User object (ID should be None).

        Returns:
            The User object with the generated ID.

        Raises:
            DatabaseError: If the insertion fails.
            ValueError: If required user fields are missing or permissions are not set.
        """
        if not user.username or not user.password_hash or not user.name:
             raise ValueError("Missing required fields (username, password_hash, name) for User.")
        if user.permissions is None:
             raise ValueError("User permissions must be set before adding the user.")

        user_query = """
            INSERT INTO users (username, password_hash, name, email, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        user_params = (
            user.username, user.password_hash, user.name, user.email,
            user.created_at or datetime.now(), user.is_active
        )

        perm_query = """
            INSERT INTO user_permissions
            (user_id, is_admin, can_access_products, can_access_fabrics, can_access_customer_panel, can_access_fiscal, can_access_accounts_receivable) -- <<<--- ADDED
            VALUES (?, ?, ?, ?, ?, ?, ?) -- <<<--- ADDED Placeholder
        """

        conn = None
        try:
            conn = self._get_connection()
            conn.execute("BEGIN;") # Explicit transaction
            cursor = conn.cursor()

            # Insert user
            cursor.execute(user_query, user_params)
            user_id = cursor.lastrowid
            if user_id is None:
                 conn.rollback()
                 raise DatabaseError("Failed to insert user, no ID returned.")
            user.id = user_id
            user.permissions.user_id = user_id # Ensure permission object has user ID
            logger.debug(f"User '{user.username}' inserted with ID: {user_id}")

            # Insert permissions
            perm_params = (
                user_id,
                user.permissions.is_admin,
                user.permissions.can_access_products,
                user.permissions.can_access_fabrics,
                user.permissions.can_access_customer_panel,
                user.permissions.can_access_fiscal,
                user.permissions.can_access_customer_panel
            )
            cursor.execute(perm_query, perm_params)
            permission_id = cursor.lastrowid
            if permission_id:
                 user.permissions.id = permission_id

            conn.commit()
            logger.info(f"User '{user.username}' (ID: {user.id}) and permissions added successfully.")
            return user

        except sqlite3.IntegrityError as e:
            if conn: conn.rollback()
            logger.warning(f"Database integrity error adding user '{user.username}': {e}")
            if "UNIQUE constraint failed: users.username" in str(e):
                 raise ValueError(f"Username '{user.username}' already exists.")
            if "UNIQUE constraint failed: users.email" in str(e) and user.email:
                 raise ValueError(f"Email '{user.email}' already exists.")
            if "UNIQUE constraint failed: user_permissions.user_id" in str(e):
                 raise DatabaseError(f"Permissions already exist for user ID {user.id}. Data inconsistency.")
            raise DatabaseError(f"Failed to add user due to integrity constraint: {e}") from e
        except sqlite3.Error as e:
            if conn: conn.rollback()
            logger.error(f"Database error adding user '{user.username}': {e}", exc_info=True)
            raise DatabaseError(f"Failed to add user: {e}") from e
        except Exception as e:
            if conn: conn.rollback()
            logger.error(f"Unexpected error adding user '{user.username}': {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred while adding user: {e}") from e
        finally:
            if conn:
                self._release_connection(conn)

    def update(self, user: User) -> bool:
        """
        Updates an existing user and their permissions.

        Args:
            user: The User object with updated data (must have an ID).

        Returns:
            True if the update was successful, False otherwise.

        Raises:
            DatabaseError: If the update fails.
            ValueError: If user ID is missing or permissions are inconsistent.
        """
        if user.id is None:
            raise ValueError("Cannot update user without an ID.")
        if user.permissions is None:
             raise ValueError("User permissions are missing for update.")
        # Check user_id match only if permissions object has a user_id set
        if user.permissions.user_id is not None and user.permissions.user_id != user.id:
             raise ValueError("User permissions user_id mismatch for update.")


        user_query = """
            UPDATE users SET
                name = ?, email = ?, is_active = ?, last_login = ?, password_hash = ?
            WHERE id = ?
        """
        if not user.password_hash:
             raise ValueError("Password hash cannot be empty for update. Fetch user first if not changing password.")

        user_params = (
            user.name, user.email, user.is_active, user.last_login, user.password_hash, user.id
        )

        # Use INSERT OR REPLACE for permissions to handle cases where they might not exist yet
        # This simplifies logic compared to checking existence first.
        perm_query = """
            INSERT OR REPLACE INTO user_permissions
            (user_id, is_admin, can_access_products, can_access_fabrics, can_access_customer_panel, can_access_fiscal, can_access_accounts_receivable) -- <<<--- ADDED
            VALUES (?, ?, ?, ?, ?, ?, ?) -- <<<--- ADDED Placeholder
        """
        perm_params = (
            user.id, # Use user.id as the user_id
            user.permissions.is_admin,
            user.permissions.can_access_products,
            user.permissions.can_access_fabrics,
            user.permissions.can_access_customer_panel,
            user.permissions.can_access_fiscal,
            user.permissions.can_access_accounts_receivable
        )

        conn = None
        try:
            conn = self._get_connection()
            conn.execute("BEGIN;")
            cursor = conn.cursor()

            # Update user
            cursor.execute(user_query, user_params)
            user_rows_affected = cursor.rowcount

            # Insert or Replace permissions
            cursor.execute(perm_query, perm_params)
            perm_rows_affected = cursor.rowcount # Will be 1 if inserted/replaced

            conn.commit()
            logger.info(f"User ID {user.id} update attempted. User rows affected: {user_rows_affected}, Perm rows affected/replaced: {perm_rows_affected}")
            # Return True if user details OR permissions were potentially updated/inserted.
            return user_rows_affected > 0 or perm_rows_affected > 0

        except sqlite3.IntegrityError as e:
             if conn: conn.rollback()
             logger.warning(f"Database integrity error updating user ID {user.id}: {e}")
             if "UNIQUE constraint failed: users.email" in str(e) and user.email:
                  raise ValueError(f"Email '{user.email}' is already in use by another user.")
             raise DatabaseError(f"Failed to update user due to integrity constraint: {e}") from e
        except sqlite3.Error as e:
            if conn: conn.rollback()
            logger.error(f"Database error updating user ID {user.id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to update user: {e}") from e
        except Exception as e:
            if conn: conn.rollback()
            logger.error(f"Unexpected error updating user ID {user.id}: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred while updating user: {e}") from e
        finally:
            if conn:
                self._release_connection(conn)

    def delete(self, user_id: int) -> bool:
        """
        Deletes a user by their ID. Permissions are deleted via CASCADE.

        Args:
            user_id: The ID of the user to delete.

        Returns:
            True if deletion was successful (one user row affected), False otherwise.

        Raises:
            DatabaseError: If the deletion fails.
        """
        query = "DELETE FROM users WHERE id = ?"
        conn = None
        try:
            # Get connection and execute using BaseRepository method which handles commit/release for single ops
            rows_affected = self._execute(query, (user_id,), fetch_mode="rowcount", single_op=True)

            if rows_affected is not None and rows_affected > 0:
                logger.info(f"User ID {user_id} deleted successfully.")
                return True
            else:
                logger.warning(f"Attempted to delete user ID {user_id}, but user was not found or delete failed silently.")
                return False # Indicates no change or user not found

        except sqlite3.Error as e:
            logger.error(f"Database error deleting user ID {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to delete user: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error deleting user ID {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred while deleting user: {e}") from e
        # No finally block needed as _execute handles release

    def update_last_login(self, user_id: int) -> bool:
        """
        Updates the last_login timestamp for a user.

        Args:
            user_id: The ID of the user.

        Returns:
            True if successful, False otherwise.
        """
        query = "UPDATE users SET last_login = ? WHERE id = ?"
        params = (datetime.now(), user_id)
        try:
            # Use single_op=True to let _execute handle commit/release
            rows_affected = self._execute(query, params, fetch_mode="rowcount", single_op=True)
            if rows_affected is not None and rows_affected > 0:
                 logger.debug(f"Updated last_login for user ID {user_id}.")
                 return True
            else:
                 logger.warning(f"Failed to update last_login for user ID {user_id} (user not found or no change).")
                 return False
        except DatabaseError as e:
             logger.error(f"Failed to update last_login for user ID {user_id}: {e}", exc_info=True)
             return False
        except Exception as e:
             logger.error(f"Unexpected error updating last_login for user ID {user_id}: {e}", exc_info=True)
             return False