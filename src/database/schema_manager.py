# src/database/schema_manager.py
# Gerencia a criação inicial das tabelas do banco de dados e dados essenciais.

import bcrypt
import os
from datetime import datetime, timezone
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import text

from .base import Base
from src.utils.logger import logger
from src.api.errors import DatabaseError, ConfigurationError

DEFAULT_ADMIN_PASSWORD = 'admin'
try:
    from src.config import config
    DEFAULT_ADMIN_PASSWORD = os.environ.get('DEFAULT_ADMIN_PASSWORD', config.SECRET_KEY[:8] if config.SECRET_KEY else 'admin')
    if len(DEFAULT_ADMIN_PASSWORD) < 6:
        logger.warning("Senha padrão do admin é muito curta, usando 'admin123' como alternativa.")
        DEFAULT_ADMIN_PASSWORD = 'admin123'
except (ImportError, ConfigurationError) as e:
    print(f"Aviso: Não foi possível carregar a configuração para senha do admin, usando '{DEFAULT_ADMIN_PASSWORD}'. Erro: {e}")

class SchemaManager:
    def __init__(self, engine: Engine):
        self.engine = engine
        logger.debug("SchemaManager inicializado com o engine do SQLAlchemy.")

    def initialize_schema(self):
        try:
            logger.info("Iniciando a criação do esquema do banco de dados...")
            Base.metadata.create_all(bind=self.engine)
            logger.info("Tabelas criadas/verificadas com sucesso.")

            with self.engine.connect() as connection:
                with connection.begin():
                    logger.debug("Verificando existência do usuário admin...")
                    self._ensure_admin_user_exists(connection)
                    logger.debug("Verificação do usuário admin concluída.")

            logger.info("Esquema do banco de dados inicializado com sucesso.")

        except SQLAlchemyError as e:
            logger.critical(f"Falha na inicialização do esquema do banco de dados: {e}", exc_info=True)
            raise DatabaseError(f"Falha na inicialização do esquema: {e}") from e
        except Exception as e:
            logger.critical(f"Erro inesperado na inicialização do esquema: {e}", exc_info=True)
            raise DatabaseError(f"Falha na inicialização do esquema: {e}") from e

    def _ensure_admin_user_exists(self, connection: Connection):
        logger.debug("Verificando existência do usuário admin...")
        try:
            check_query = text("SELECT id FROM users WHERE LOWER(username) = LOWER(:username)")
            result = connection.execute(check_query, {'username': 'admin'})
            admin_user_row = result.fetchone()

            if not admin_user_row:
                logger.info("Usuário admin não encontrado. Criando...")
                password = DEFAULT_ADMIN_PASSWORD
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                now_utc = datetime.now(timezone.utc)

                user_insert_query = text("""
                    INSERT INTO users (username, password_hash, name, email, created_at, is_active)
                    VALUES (:username, :password_hash, :name, :email, :created_at, :is_active)
                    RETURNING id
                """)
                user_result = connection.execute(user_insert_query, {
                    'username': 'admin', 'password_hash': hashed_password, 'name': 'Administrator',
                    'email': 'admin@example.com', 'created_at': now_utc, 'is_active': True
                })
                admin_id = user_result.scalar_one()
                logger.debug(f"Usuário admin criado com ID: {admin_id}")

                perm_insert_query = text("""
                    INSERT INTO user_permissions
                    (user_id, is_admin, can_access_products, can_access_fabrics, can_access_customer_panel, can_access_fiscal, can_access_accounts_receivable)
                    VALUES (:user_id, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE)
                """)
                connection.execute(perm_insert_query, {'user_id': admin_id})
                logger.info("Usuário admin criado com permissões totais.")
            else:
                admin_id = admin_user_row[0]
                logger.debug(f"Usuário admin já existe (ID: {admin_id}). Verificando permissões...")
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
                logger.debug(f"Permissões garantidas para o usuário admin (ID: {admin_id}).")

        except IntegrityError as e:
            logger.warning(f"Falha ao criar/atualizar usuário admin devido a restrição de integridade: {e}")
        except SQLAlchemyError as e:
            logger.error(f"Erro SQLAlchemy ao garantir usuário admin: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao garantir usuário admin: {e}", exc_info=True)
            raise
