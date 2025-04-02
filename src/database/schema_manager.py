# src/database/schema_manager.py
# Manages the creation and migration of the database schema using SQLAlchemy ORM Metadata.

import bcrypt
import os
from datetime import datetime, timezone
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import text, inspect # Import inspect para verificar colunas

# Importar Base para usar metadata
from .base import Base
from src.utils.logger import logger
from src.api.errors import DatabaseError, ConfigurationError

# Lógica para obter senha admin padrão permanece a mesma
DEFAULT_ADMIN_PASSWORD = 'admin'
try:
     from src.config import config
     DEFAULT_ADMIN_PASSWORD = os.environ.get('DEFAULT_ADMIN_PASSWORD', config.SECRET_KEY[:8] if config.SECRET_KEY else 'admin')
     if len(DEFAULT_ADMIN_PASSWORD) < 6:
          logger.warning("Default admin password is too short, using 'admin123' instead.")
          DEFAULT_ADMIN_PASSWORD = 'admin123'
except (ImportError, ConfigurationError) as e:
     logger.warning(f"Could not load config for default admin password, using fallback '{DEFAULT_ADMIN_PASSWORD}'. Error: {e}")


class SchemaManager:
    """
    Manages the database schema (PostgreSQL), including table creation via ORM metadata,
    migrations, and initial data setup using SQLAlchemy Engine.
    """

    def __init__(self, engine: Engine):
        """
        Initializes the SchemaManager.

        Args:
            engine: The SQLAlchemy Engine instance.
        """
        self.engine = engine
        logger.debug("SchemaManager initialized with SQLAlchemy engine.")

    def initialize_schema(self):
        """
        Initializes the PostgreSQL database schema. Creates tables defined in ORM models
        if they don't exist, runs necessary migrations, and ensures essential initial data.
        """
        try:
            logger.info("Starting database schema initialization...")

            # --- Create Tables using ORM Metadata ---
            logger.debug("Creating tables based on ORM metadata if they don't exist...")
            # Base.metadata contém todas as tabelas definidas nos modelos que herdam de Base
            Base.metadata.create_all(bind=self.engine)
            logger.info("ORM tables checked/created successfully.")

            # --- Run Manual Migrations (Add Columns, Create Indexes) ---
            # create_all não adiciona colunas a tabelas existentes nem cria todos os índices
            # Use uma conexão para executar DDL manual necessário
            with self.engine.connect() as connection:
                with connection.begin(): # Use transação para migrações
                     logger.debug("Running manual schema migrations (add columns, indexes)...")
                     self._run_migrations(connection)
                     logger.debug("Manual schema migrations checked/applied.")

                # --- Ensure Admin User (fora da transação de migração DDL se preferir) ---
                with connection.begin():
                     logger.debug("Ensuring default admin user exists...")
                     self._ensure_admin_user_exists(connection)
                     logger.debug("Default admin user check completed.")

            logger.info("Database schema initialization completed successfully.")

        except SQLAlchemyError as e:
            logger.critical(f"Database schema initialization failed: {e}", exc_info=True)
            raise DatabaseError(f"Schema initialization failed: {e}") from e
        except Exception as e:
            logger.critical(f"Unexpected error during schema initialization: {e}", exc_info=True)
            raise DatabaseError(f"Schema initialization failed: {e}") from e

    # _create_tables não é mais necessário, pois Base.metadata.create_all() faz isso.

    def _run_migrations(self, connection: Connection):
        """Applies necessary schema alterations (migrations) using manual DDL."""
        # Usar Inspector para verificar existência de colunas antes de tentar adicionar
        inspector = inspect(self.engine)

        # Exemplo: Adicionar coluna can_access_accounts_receivable a user_permissions
        table_name = 'user_permissions'
        column_name = 'can_access_accounts_receivable'
        column_definition = 'BOOLEAN DEFAULT FALSE NOT NULL'
        self._add_column_if_not_exists(connection, inspector, table_name, column_name, column_definition)

        # Exemplo: Adicionar coluna can_access_fiscal a user_permissions
        column_name = 'can_access_fiscal'
        self._add_column_if_not_exists(connection, inspector, table_name, column_name, column_definition)

        # Exemplo: Adicionar coluna can_access_customer_panel a user_permissions
        column_name = 'can_access_customer_panel'
        self._add_column_if_not_exists(connection, inspector, table_name, column_name, column_definition)

        # Adicionar futuras migrações aqui
        logger.debug("Schema migrations checked/applied.")

        # --- Criar Índices Manuais ---
        # create_all cria índices para PKs, FKs (se especificado), e colunas com unique=True/index=True.
        # Índices mais complexos (como em LOWER(column)) precisam ser criados manualmente.
        logger.debug("Creating/checking custom indexes (PostgreSQL)...")
        try:
            # Índice funcional para busca case-insensitive (se não criado pelo ORM com index=True)
            # O SQLAlchemy >= 1.4 tenta criar índices normais para colunas com index=True.
            # Verifique se o índice funcional é realmente necessário ou se o índice normal basta.
            connection.execute(text("CREATE INDEX IF NOT EXISTS idx_users_username_lower ON users(LOWER(username));"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS idx_users_email_lower ON users(LOWER(email));"))
            # Índices em colunas booleanas podem não ser muito úteis dependendo da seletividade, mas mantendo por ora.
            # O SQLAlchemy já deve ter criado idx_product_observations_resolved se index=True foi usado no modelo.
            connection.execute(text("CREATE INDEX IF NOT EXISTS idx_product_observations_resolved_timestamp ON product_observations(resolved, timestamp);"))

            logger.debug("Custom indexes checked/created.")
        except SQLAlchemyError as e:
            logger.error(f"Error creating custom indexes: {e}", exc_info=True)
            raise # Propaga erro para rollback da transação

    def _add_column_if_not_exists(self, connection: Connection, inspector, table_name: str, column_name: str, column_definition: str):
        """Helper function to add a column if it doesn't exist using Inspector."""
        columns = inspector.get_columns(table_name)
        column_exists = any(c['name'] == column_name for c in columns)

        if not column_exists:
            try:
                alter_query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                logger.info(f"Applying migration: Adding column '{column_name}' to table '{table_name}'.")
                connection.execute(text(alter_query))
                logger.info(f"Successfully added column '{column_name}'.")
            except SQLAlchemyError as e:
                logger.error(f"Error adding column '{column_name}' to table '{table_name}': {e}", exc_info=True)
                raise # Reraise para indicar falha na migração
        else:
            logger.debug(f"Column '{column_name}' already exists in table '{table_name}'. Skipping.")


    def _ensure_admin_user_exists(self, connection: Connection):
        """Checks for the default admin user and creates it if missing using ORM-like logic but with raw SQL for now."""
        # Esta lógica permanece a mesma, pois precisa garantir o usuário
        # antes que a aplicação possa usar o ORM completamente. Usa a conexão direta.
        logger.debug("Ensuring default admin user exists (using connection)...")
        try:
            # Verificar se admin existe
            check_query = text("SELECT id FROM users WHERE LOWER(username) = LOWER(:username)")
            check_params = {'username': 'admin'}
            result = connection.execute(check_query, check_params)
            admin_user_row = result.fetchone()

            if not admin_user_row:
                logger.info("Default admin user not found. Creating...")
                password = DEFAULT_ADMIN_PASSWORD
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                now_utc = datetime.now(timezone.utc)

                # Inserir usuário com RETURNING id
                user_insert_query = text("""
                    INSERT INTO users (username, password_hash, name, email, created_at, is_active)
                    VALUES (:username, :password_hash, :name, :email, :created_at, :is_active)
                    RETURNING id
                """)
                user_insert_params = {
                    'username': 'admin', 'password_hash': hashed_password, 'name': 'Administrator',
                    'email': 'admin@example.com', 'created_at': now_utc, 'is_active': True
                }
                user_result = connection.execute(user_insert_query, user_insert_params)
                admin_id = user_result.scalar_one()
                logger.debug(f"Admin user created with ID: {admin_id}")

                # Inserir permissões
                perm_insert_query = text("""
                    INSERT INTO user_permissions
                    (user_id, is_admin, can_access_products, can_access_fabrics, can_access_customer_panel, can_access_fiscal, can_access_accounts_receivable)
                    VALUES (:user_id, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE)
                """)
                perm_insert_params = {'user_id': admin_id}
                connection.execute(perm_insert_query, perm_insert_params)
                logger.info(f"Default admin user created successfully with full permissions (Password: {'******' if password else 'N/A'}'). Please change the password if default was used.")

            else:
                admin_id = admin_user_row[0]
                logger.debug(f"Default admin user (ID: {admin_id}) already exists. Ensuring permissions...")
                # Garantir que as permissões existem e estão corretas (UPSERT ou UPDATE/INSERT)
                perm_upsert_query = text("""
                    INSERT INTO user_permissions (user_id, is_admin, can_access_products, can_access_fabrics, can_access_customer_panel, can_access_fiscal, can_access_accounts_receivable)
                    VALUES (:user_id, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE)
                    ON CONFLICT (user_id) DO UPDATE SET
                        is_admin = EXCLUDED.is_admin,
                        can_access_products = EXCLUDED.can_access_products,
                        can_access_fabrics = EXCLUDED.can_access_fabrics,
                        can_access_customer_panel = EXCLUDED.can_access_customer_panel,
                        can_access_fiscal = EXCLUDED.can_access_fiscal,
                        can_access_accounts_receivable = EXCLUDED.can_access_accounts_receivable;
                """)
                connection.execute(perm_upsert_query, {'user_id': admin_id})
                logger.debug(f"Permissions ensured for admin user ID {admin_id}.")

        except IntegrityError as e: # Captura erros de constraint UNIQUE etc.
            logger.warning(f"Admin user creation/update failed due to integrity constraint (likely race condition or schema issue): {e}")
            # Não relançar aqui necessariamente, pois o admin pode ter sido criado por outro processo/thread.
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError ensuring admin user exists: {e}", exc_info=True)
            raise # Propaga erro para rollback da transação principal do schema init
        except Exception as e:
            logger.error(f"Unexpected error ensuring admin user exists: {e}", exc_info=True)
            raise