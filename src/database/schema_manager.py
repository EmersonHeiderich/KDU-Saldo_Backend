# src/database/schema_manager.py
# Manages the initial creation of database tables and essential data.

import bcrypt
import os
from datetime import datetime, timezone
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import text, inspect

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
     print(f"Warning: Could not load config for default admin password, using fallback '{DEFAULT_ADMIN_PASSWORD}'. Error: {e}")


class SchemaManager:
    """
    Manages the database schema (PostgreSQL), focando em:
    1.  Configuração inicial: Garante dados essenciais como o usuário admin.

    A criação/alteração de tabelas, colunas, índices, etc., é
    agora gerenciada exclusivamente pelo Alembic.
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
        Inicializa o schema do banco de dados PostgreSQL.
        Garante apenas dados iniciais essenciais (usuário admin).
        A criação/migração de tabelas é feita pelo Alembic.
        """
        try:
            logger.info("Starting database schema initialization (data only)...")

            # --- NÃO CRIAR TABELAS AQUI ---
            # A linha abaixo foi removida/comentada para que o Alembic seja o único responsável pelo schema.
            # Base.metadata.create_all(bind=self.engine)
            # logger.info("Table creation via create_all() skipped. Relying on Alembic.")
            # ------------------------------

            # --- Garantir Usuário Admin ---
            with self.engine.connect() as connection:
                with connection.begin(): # Inicia uma transação
                    logger.debug("Ensuring default admin user exists...")
                    self._ensure_admin_user_exists(connection)
                    logger.debug("Default admin user check completed.")
                # O bloco 'with connection.begin()' faz commit ou rollback automaticamente.

            logger.info("Database essential data initialization completed successfully.")

        except SQLAlchemyError as e:
            logger.critical(f"Database essential data initialization failed: {e}", exc_info=True)
            raise DatabaseError(f"Schema/Data initialization failed: {e}") from e
        except Exception as e:
            logger.critical(f"Unexpected error during schema/data initialization: {e}", exc_info=True)
            raise DatabaseError(f"Schema/Data initialization failed: {e}") from e


    def _ensure_admin_user_exists(self, connection: Connection):
        """Verifica o usuário admin padrão e o cria se ausente usando SQL direto."""
        # Esta lógica permanece a mesma, pois é para dados essenciais.
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
                # Usar ON CONFLICT (UPSERT) é mais robusto
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

        except IntegrityError as e:
            logger.warning(f"Admin user creation/update failed due to integrity constraint (likely race condition or schema issue): {e}")
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemyError ensuring admin user exists: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error ensuring admin user exists: {e}", exc_info=True)
            raise