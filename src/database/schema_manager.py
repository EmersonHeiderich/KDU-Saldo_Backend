# src/database/schema_manager.py
# Manages the creation and migration of the database schema.

import sqlite3
import bcrypt
import os
from datetime import datetime
from .connection_pool import ConnectionPool
from src.utils.logger import logger
from src.api.errors import DatabaseError, ConfigurationError # Added ConfigurationError

# Attempt to import config for default admin password (handle potential failure)
DEFAULT_ADMIN_PASSWORD = 'admin' # Fallback default
try:
     from src.config import config
     DEFAULT_ADMIN_PASSWORD = os.environ.get('DEFAULT_ADMIN_PASSWORD', config.SECRET_KEY[:8] if config.SECRET_KEY else 'admin') # Use env var or derived/fallback
     if len(DEFAULT_ADMIN_PASSWORD) < 6:
          logger.warning("Default admin password is too short, using 'admin123' instead.")
          DEFAULT_ADMIN_PASSWORD = 'admin123'
except (ImportError, ConfigurationError) as e:
     logger.warning(f"Could not load config for default admin password, using fallback '{DEFAULT_ADMIN_PASSWORD}'. Error: {e}")


class SchemaManager:
    """
    Manages the database schema, including table creation, migrations,
    and initial data setup (like the admin user).
    """

    def __init__(self, connection_pool: ConnectionPool):
        """
        Initializes the SchemaManager.

        Args:
            connection_pool: The ConnectionPool instance.
        """
        self.connection_pool = connection_pool
        logger.debug("SchemaManager initialized.")

    def initialize_schema(self):
        """
        Initializes the database schema. Creates tables if they don't exist,
        runs necessary migrations, and ensures essential initial data is present.

        Should be called once during application startup.

        Raises:
            DatabaseError: If schema initialization fails.
        """
        conn = None
        try:
            logger.info("Starting database schema initialization...")
            conn = self.connection_pool.get_connection() # Use pool's get method

            # Use Row factory for PRAGMA results
            conn.row_factory = sqlite3.Row

            # Start transaction
            conn.execute("BEGIN;")
            logger.debug("Transaction started for schema initialization.")

            self._create_tables(conn)
            self._run_migrations(conn)
            self._ensure_admin_user_exists(conn)

            # Commit transaction
            conn.commit()
            logger.info("Database schema initialization completed successfully.")

        except Exception as e:
            logger.critical(f"Database schema initialization failed: {e}", exc_info=True)
            if conn:
                try:
                    logger.warning("Rolling back schema changes due to error.")
                    conn.rollback()
                except Exception as rb_err:
                    logger.error(f"Error during schema rollback: {rb_err}", exc_info=True)
            # Re-raise as a specific error type
            raise DatabaseError(f"Schema initialization failed: {e}") from e
        finally:
            if conn:
                # Reset row factory before releasing if changed
                conn.row_factory = sqlite3.Row # Ensure it's reset to expected default for pool
                self.connection_pool.release_connection(conn) # Use pool's release method


    def _create_tables(self, conn: sqlite3.Connection):
        """Creates all necessary tables if they do not exist."""
        logger.debug("Creating database tables if they don't exist...")
        cursor = conn.cursor()
        try:
            # Users Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL COLLATE NOCASE, -- Case-insensitive unique username
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT UNIQUE COLLATE NOCASE, -- Case-insensitive unique email
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1 NOT NULL CHECK(is_active IN (0, 1))
            );
            """)
            logger.debug("Table 'users' checked/created.")

            # User Permissions Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE, -- One-to-one relationship with users
                is_admin BOOLEAN DEFAULT 0 NOT NULL CHECK(is_admin IN (0, 1)),
                can_access_products BOOLEAN DEFAULT 0 NOT NULL CHECK(can_access_products IN (0, 1)),
                can_access_fabrics BOOLEAN DEFAULT 0 NOT NULL CHECK(can_access_fabrics IN (0, 1)),
                can_access_customer_panel BOOLEAN DEFAULT 0 NOT NULL CHECK(can_access_customer_panel IN (0, 1)),
                can_access_fiscal BOOLEAN DEFAULT 0 NOT NULL CHECK(can_access_fiscal IN (0, 1)), -- <<<--- ADDED
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """)
            logger.debug("Table 'user_permissions' checked/created.")

            # Product Observations Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference_code TEXT NOT NULL,
                observation TEXT NOT NULL,
                user TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                resolved BOOLEAN DEFAULT 0 NOT NULL CHECK(resolved IN (0, 1)),
                resolved_user TEXT,
                resolved_timestamp TIMESTAMP
            );
            """)
            logger.debug("Table 'product_observations' checked/created.")

            # --- Indexes ---
            logger.debug("Creating indexes...")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_permissions_user_id ON user_permissions(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_observations_ref_code ON product_observations(reference_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_observations_resolved_timestamp ON product_observations(resolved, timestamp);")
            logger.debug("Indexes checked/created.")

        except sqlite3.Error as e:
            logger.error(f"Error creating tables: {e}", exc_info=True)
            raise # Propagate error to trigger rollback
        finally:
             if cursor: cursor.close()


    def _run_migrations(self, conn: sqlite3.Connection):
        """Applies necessary schema alterations (migrations)."""
        logger.debug("Running schema migrations...")
        # Add the new fiscal permission column if it doesn't exist
        self._add_column_if_not_exists(conn, 'user_permissions', 'can_access_fiscal', 'BOOLEAN DEFAULT 0 NOT NULL CHECK(can_access_fiscal IN (0, 1))')
        # Add more migration calls here as needed
        logger.debug("Schema migrations checked/applied.")


    def _add_column_if_not_exists(self, conn: sqlite3.Connection, table_name: str, column_name: str, column_definition: str):
        """Helper function to add a column to a table if it doesn't already exist."""
        cursor = conn.cursor()
        try:
            # Use PRAGMA table_info which works well with sqlite3.Row factory
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [row['name'] for row in cursor.fetchall()]

            if column_name not in columns:
                logger.info(f"Adding column '{column_name}' to table '{table_name}'...")
                alter_query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                cursor.execute(alter_query)
                logger.info(f"Column '{column_name}' added successfully.")
            else:
                logger.debug(f"Column '{column_name}' already exists in table '{table_name}'.")

        except sqlite3.Error as e:
            logger.error(f"Error adding column '{column_name}' to table '{table_name}': {e}", exc_info=True)
            raise # Reraise to indicate migration failure
        finally:
             if cursor: cursor.close()

    def _ensure_admin_user_exists(self, conn: sqlite3.Connection):
        """Checks for the default admin user and creates it if missing."""
        logger.debug("Ensuring default admin user exists...")
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM users WHERE username = ?", ('admin',))
            admin_exists = cursor.fetchone()

            if not admin_exists:
                logger.info("Default admin user not found. Creating...")

                password = DEFAULT_ADMIN_PASSWORD # Use the resolved password
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                now = datetime.now()

                # Insert user
                cursor.execute("""
                    INSERT INTO users (username, password_hash, name, email, created_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ('admin', hashed_password, 'Administrator', 'admin@example.com', now, 1))
                admin_id = cursor.lastrowid
                logger.debug(f"Admin user created with ID: {admin_id}")
                if not admin_id:
                     raise DatabaseError("Failed to create admin user, lastrowid is null.")

                # Insert permissions (ensure table exists first - handled by _create_tables)
                cursor.execute("""
                    INSERT INTO user_permissions
                    (user_id, is_admin, can_access_products, can_access_fabrics, can_access_customer_panel, can_access_fiscal)
                    VALUES (?, 1, 1, 1, 1, 1) -- Admin gets all permissions
                """, (admin_id,))
                logger.info(f"Default admin user created successfully with full permissions (Password: '{'******' if password else 'N/A'}'). Please change the password if default was used.")
            else:
                logger.debug("Default admin user already exists.")
                # Optionally: Update admin permissions if needed on startup?
                admin_id = admin_exists['id']
                logger.debug(f"Ensuring admin user (ID: {admin_id}) has all permissions...")
                cursor.execute("""
                    UPDATE user_permissions SET
                        is_admin = 1,
                        can_access_products = 1,
                        can_access_fabrics = 1,
                        can_access_customer_panel = 1,
                        can_access_fiscal = 1
                    WHERE user_id = ?
                """, (admin_id,))
                if cursor.rowcount > 0:
                     logger.info(f"Updated permissions for admin user ID {admin_id}.")
                else:
                     # Check if permissions row exists at all
                     cursor.execute("SELECT 1 FROM user_permissions WHERE user_id = ?", (admin_id,))
                     perm_exists = cursor.fetchone()
                     if not perm_exists:
                          logger.warning(f"Admin user ID {admin_id} exists, but no permissions row found. Creating.")
                          cursor.execute("""
                               INSERT INTO user_permissions
                               (user_id, is_admin, can_access_products, can_access_fabrics, can_access_customer_panel, can_access_fiscal)
                               VALUES (?, 1, 1, 1, 1, 1)
                          """, (admin_id,))
                     else:
                          logger.debug(f"Admin user ID {admin_id} permissions already up-to-date.")


        except sqlite3.IntegrityError as e:
            logger.warning(f"Admin user creation failed due to integrity constraint (likely exists): {e}")
        except sqlite3.Error as e:
            logger.error(f"Error ensuring admin user exists: {e}", exc_info=True)
            raise # Propagate error
        finally:
            if cursor: cursor.close()