# src/database/__init__.py
# Initializes SQLAlchemy components: Engine, SessionLocal, Base metadata.
# Uses local imports for logger/errors to prevent circular dependencies during Alembic runs.

import threading
from typing import Optional, Generator
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

# Importar Base diretamente - ESSENCIAL para Alembic
from .base import Base
# NÃO importar logger, errors, ConfigurationError, SchemaManager aqui no topo

# --- SQLAlchemy Engine and Session Factory Globals ---
_sqla_engine: Optional[Engine] = None
_SessionLocalFactory: Optional[sessionmaker[Session]] = None
_engine_lock = threading.Lock()

# --- Função de Inicialização do Engine e Session Factory ---
def init_sqlalchemy(database_uri: str, pool_size: int = 10, max_overflow: int = 20) -> Engine:
    """
    Initializes the SQLAlchemy engine, session factory, and database schema.
    Should be called once during application startup.
    Uses local imports for logger/errors.
    """
    # --- Importações locais ---
    from src.utils.logger import logger # Importa logger aqui
    from src.api.errors import DatabaseError, ConfigurationError # Importa errors aqui
    # -------------------------

    global _sqla_engine, _SessionLocalFactory
    with _engine_lock:
        if _sqla_engine and _SessionLocalFactory:
            logger.warning("SQLAlchemy engine and session factory already initialized.")
            return _sqla_engine

        if not database_uri:
            # Logger pode não estar disponível ainda se a config falhar aqui,
            # mas ConfigurationError será levantado.
            # logger.critical("Database URI is not configured. Cannot initialize SQLAlchemy.")
            raise ConfigurationError("Database URI is missing in configuration.")

        logger.info(f"Initializing SQLAlchemy engine and session factory...")
        try:
            # 1. Create the Engine
            engine = create_engine(
                database_uri,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_recycle=3600,
                echo=False
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

            # 4. Initialize Schema (uses the engine)
            # --- Importar SchemaManager localmente ---
            from .schema_manager import SchemaManager
            # ---------------------------------------
            try:
                logger.info("Initializing database schema...")
                schema_manager = SchemaManager(engine)
                schema_manager.initialize_schema()
                logger.info("Database schema initialization complete.")
            except Exception as schema_err:
                logger.critical(f"Database schema initialization failed: {schema_err}", exc_info=True)
                engine.dispose()
                raise DatabaseError(f"Schema initialization failed: {schema_err}") from schema_err

            # Store the initialized engine
            _sqla_engine = engine
            logger.info("SQLAlchemy initialization complete.")
            return _sqla_engine

        except (DatabaseError, ConfigurationError) as e: # Capturar config error tb
             # Logger pode não estar disponível se falhar cedo
             print(f"ERROR: Database/Configuration error during SQLAlchemy initialization: {e}")
             raise
        except SQLAlchemyError as e:
             # Logger pode não estar disponível
             print(f"ERROR: SQLAlchemy error during initialization: {e}")
             logger.critical(f"SQLAlchemy engine/session factory initialization failed: {e}", exc_info=True)
             raise DatabaseError(f"SQLAlchemy initialization failed: {e}") from e
        except Exception as e:
             # Logger pode não estar disponível
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
    from src.utils.logger import logger # Importa logger aqui
    from src.api.errors import DatabaseError # Importa errors aqui
    # -------------------------

    if not _SessionLocalFactory:
        # Logger pode não estar disponível aqui se a inicialização falhou muito cedo
        # logger.critical("SessionLocal factory not initialized. Call init_sqlalchemy() first.")
        print("CRITICAL ERROR: Database session factory has not been initialized.")
        raise RuntimeError("Database session factory has not been initialized.")

    db: Optional[Session] = None
    try:
        db = _SessionLocalFactory()
        yield db
        db.commit()
        logger.debug("Database session committed successfully.")
    except SQLAlchemyError as sql_ex:
        logger.error(f"Database error occurred in session: {sql_ex}", exc_info=True)
        if db:
            db.rollback()
            logger.warning("Database session rolled back due to SQLAlchemyError.")
        raise DatabaseError(f"Database operation failed: {sql_ex}") from sql_ex
    except Exception as e:
        logger.error(f"Error occurred in database session: {e}", exc_info=True)
        if db:
            db.rollback()
            logger.warning("Database session rolled back due to exception.")
        raise
    finally:
        if db:
            db.close()
            logger.debug("Database session closed.")

# --- Função de Desligamento do Engine ---
def dispose_sqlalchemy_engine():
    """Closes all connections in the engine's pool. Call during application shutdown."""
    # --- Importações locais ---
    from src.utils.logger import logger # Importa logger aqui
    # -------------------------

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

# --- Itens Exportados Atualizados ---
# Somente funções e Base são exportados
__all__ = [
    "init_sqlalchemy",
    "get_db_session",
    "dispose_sqlalchemy_engine",
    "Base", # Essencial
]