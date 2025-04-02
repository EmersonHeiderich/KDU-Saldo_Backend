# src/database/__init__.py
# Initializes SQLAlchemy components and exports DB access utilities and repositories.

import threading
from typing import Optional, Generator
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

# Importar Base diretamente - ESSENCIAL para Alembic
from .base import Base
# Importar Repositórios principais
# Usamos importação tardia para repositórios para evitar ciclos de importação
# Especialmente importante para o Alembic
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .user_repository import UserRepository
    from .observation_repository import ObservationRepository
    from .product_repository import ProductRepository
    from .erp_cache.erp_person_repository import ErpPersonRepository

# NÃO importar logger, errors, ConfigurationError, SchemaManager aqui no topo

# --- SQLAlchemy Engine and Session Factory Globals ---
_sqla_engine: Optional[Engine] = None
_SessionLocalFactory: Optional[sessionmaker[Session]] = None
_engine_lock = threading.Lock()

# --- Função de Inicialização do Engine e Session Factory ---
def init_sqlalchemy(database_uri: str, pool_size: int = 10, max_overflow: int = 20) -> Engine:
    """
    Initializes the SQLAlchemy engine, session factory, and essential data.
    Should be called once during application startup.
    Uses local imports for logger/errors/SchemaManager.
    """
    # --- Importações locais ---
    from src.utils.logger import logger
    from src.api.errors import DatabaseError, ConfigurationError
    from .schema_manager import SchemaManager # SchemaManager agora só garante dados
    # -------------------------

    global _sqla_engine, _SessionLocalFactory
    with _engine_lock:
        if _sqla_engine and _SessionLocalFactory:
            logger.warning("SQLAlchemy engine and session factory already initialized.")
            return _sqla_engine

        if not database_uri:
            raise ConfigurationError("Database URI is missing in configuration.")

        logger.info(f"Initializing SQLAlchemy engine and session factory...")
        try:
            # 1. Create the Engine
            engine = create_engine(
                database_uri,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_recycle=3600,
                echo=False # Mantenha False para produção
            )

            # 2. Test Connection
            try:
                with engine.connect() as connection:
                    logger.info("Database connection successful.")
            except SQLAlchemyError as conn_err:
                logger.critical(f"Database connection failed: {conn_err}", exc_info=True)
                raise DatabaseError(f"Failed to connect to the database: {conn_err}") from conn_err

            # 3. Create Session Factory (SessionLocal)
            _SessionLocalFactory = sessionmaker(
                autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
            )
            logger.info("SQLAlchemy session factory (SessionLocal) created.")

            # 4. Initialize Schema (Data only - User Admin)
            try:
                logger.info("Initializing essential database data (Admin User)...")
                schema_manager = SchemaManager(engine)
                schema_manager.initialize_schema() # Agora só garante o usuário admin
                logger.info("Essential database data initialization complete.")
            except Exception as schema_err:
                # Log crítico, mas talvez não precise parar a app se for só o admin
                logger.error(f"Essential database data initialization failed: {schema_err}", exc_info=True)
                # Decidir se quer levantar erro aqui ou só logar
                # raise DatabaseError(f"Essential Data initialization failed: {schema_err}") from schema_err

            # Store the initialized engine
            _sqla_engine = engine
            logger.info("SQLAlchemy initialization complete.")
            return _sqla_engine

        except (DatabaseError, ConfigurationError) as e:
             print(f"ERROR: Database/Configuration error during SQLAlchemy initialization: {e}")
             raise
        except SQLAlchemyError as e:
             print(f"ERROR: SQLAlchemy error during initialization: {e}")
             logger.critical(f"SQLAlchemy engine/session factory initialization failed: {e}", exc_info=True)
             raise DatabaseError(f"SQLAlchemy initialization failed: {e}") from e
        except Exception as e:
             print(f"ERROR: Unexpected error during SQLAlchemy initialization: {e}")
             logger.critical(f"Unexpected error during SQLAlchemy initialization: {e}", exc_info=True)
             if 'engine' in locals() and engine: engine.dispose()
             raise DatabaseError(f"Unexpected error during database initialization: {e}") from e

# --- Função para Obter uma Sessão (Gerenciador de Contexto) ---
@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Dependency function/context manager to get a database session.
    Manages session lifecycle (commit, rollback, close).
    Uses local imports for logger/errors.
    """
    # --- Importações locais ---
    from src.utils.logger import logger
    from src.api.errors import DatabaseError
    # -------------------------

    if not _SessionLocalFactory:
        print("CRITICAL ERROR: Database session factory has not been initialized.")
        raise RuntimeError("Database session factory has not been initialized.")

    db: Optional[Session] = None
    try:
        db = _SessionLocalFactory()
        yield db
        db.commit()
        # logger.debug("Database session committed successfully.") # Log muito verboso
    except SQLAlchemyError as sql_ex:
        logger.error(f"Database error occurred in session: {sql_ex}", exc_info=True)
        if db:
            db.rollback()
            logger.warning("Database session rolled back due to SQLAlchemyError.")
        # Simplificar mensagem de erro para o usuário, detalhes no log
        raise DatabaseError("Database operation failed.") from sql_ex
    except Exception as e:
        logger.error(f"Error occurred in database session: {e}", exc_info=True)
        if db:
            db.rollback()
            logger.warning("Database session rolled back due to exception.")
        raise # Re-raise a exceção original ou uma DatabaseError mais genérica
    finally:
        if db:
            db.close()
            # logger.debug("Database session closed.") # Log muito verboso

# --- Função de Desligamento do Engine ---
def dispose_sqlalchemy_engine():
    """Closes all connections in the engine's pool. Call during application shutdown."""
    from src.utils.logger import logger

    global _sqla_engine, _SessionLocalFactory
    with _engine_lock:
        if _sqla_engine:
            logger.info("Disposing SQLAlchemy engine connection pool...")
            try:
                _sqla_engine.dispose()
                _sqla_engine = None
                _SessionLocalFactory = None
                logger.info("SQLAlchemy engine connection pool disposed.")
            except Exception as e:
                logger.error(f"Error disposing SQLAlchemy engine pool: {e}", exc_info=True)
        else:
            logger.debug("SQLAlchemy engine shutdown called, but engine already disposed or not initialized.")

# --- Implementação de importação tardia para tempo de execução ---
def get_user_repository():
    """Importa UserRepository apenas quando necessário."""
    from .user_repository import UserRepository
    return UserRepository

def get_observation_repository():
    """Importa ObservationRepository apenas quando necessário."""
    from .observation_repository import ObservationRepository
    return ObservationRepository

def get_product_repository():
    """Importa ProductRepository apenas quando necessário."""
    from .product_repository import ProductRepository
    return ProductRepository

def get_erp_person_repository():
    """Importa ErpPersonRepository apenas quando necessário."""
    from .erp_cache.erp_person_repository import ErpPersonRepository
    return ErpPersonRepository

# --- Itens Exportados Atualizados ---
__all__ = [
    "init_sqlalchemy",
    "get_db_session",
    "dispose_sqlalchemy_engine",
    "Base", # Essencial para Alembic e modelos
    "get_user_repository",
    "get_observation_repository",
    "get_product_repository",
    "get_erp_person_repository",
]
