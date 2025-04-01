# src/database/__init__.py
# Initializes and manages database components using SQLAlchemy.

import threading
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine # Import Engine type hint
from sqlalchemy.exc import SQLAlchemyError

# Importações de Repositórios e Schema Manager permanecem
from .schema_manager import SchemaManager
from .user_repository import UserRepository
from .observation_repository import ObservationRepository
from src.utils.logger import logger
from src.api.errors import DatabaseError # Import custom error

# --- SQLAlchemy Engine Global ---
_sqla_engine: Optional[Engine] = None
_engine_lock = threading.Lock()

# --- Função de Inicialização do Engine ---
def init_sqlalchemy_engine(database_uri: str, pool_size: int = 10, max_overflow: int = 20) -> Engine:
    """
    Initializes the SQLAlchemy engine and database schema.
    Should be called once during application startup.

    Args:
        database_uri: The full database connection URI (e.g., "postgresql+psycopg://...").
        pool_size: The number of connections to keep open in the pool.
        max_overflow: The number of connections that can be opened beyond pool_size.

    Returns:
        The initialized SQLAlchemy Engine instance.

    Raises:
        DatabaseError: If initialization or schema setup fails.
    """
    global _sqla_engine
    with _engine_lock:
        if _sqla_engine:
            logger.warning("SQLAlchemy engine already initialized.")
            return _sqla_engine

        if not database_uri:
             logger.critical("Database URI is not configured. Cannot initialize SQLAlchemy engine.")
             raise DatabaseError("Database URI is missing in configuration.")

        logger.info(f"Initializing SQLAlchemy engine for URI: {'********'.join(database_uri.split('@'))}") # Log URI without password part
        try:
            # Create the SQLAlchemy engine
            # pool_recycle: Optional, time in seconds to recycle connections (e.g., 3600 for 1 hour)
            # echo=True: Useful for debugging SQL, set based on Flask debug mode maybe
            engine = create_engine(
                database_uri,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_recycle=3600, # Recycle connections after 1 hour
                # echo=current_app.config.get('APP_DEBUG', False) # Requires access to app context or pass debug flag
                echo=False # Start with echo=False
            )

            # --- Test Connection (Optional but recommended) ---
            try:
                with engine.connect() as connection:
                    logger.info("Database connection successful.")
                    # Optionally run a simple query: connection.execute(text("SELECT 1"))
            except SQLAlchemyError as conn_err:
                 logger.critical(f"Database connection failed: {conn_err}", exc_info=True)
                 raise DatabaseError(f"Failed to connect to the database: {conn_err}") from conn_err

            # --- Initialize Schema ---
            # SchemaManager now needs the engine to get connections
            # We'll adapt SchemaManager in a later step to accept the engine
            # For now, assume it can work with the engine (it needs adaptation)
            try:
                 # !!! NOTE: SchemaManager needs adaptation to use the Engine !!!
                 logger.info("Initializing database schema...")
                 schema_manager = SchemaManager(engine) # Pass engine instead of pool
                 schema_manager.initialize_schema() # Creates tables, runs migrations
                 logger.info("Database schema initialization complete.")
            except Exception as schema_err:
                 logger.critical(f"Database schema initialization failed: {schema_err}", exc_info=True)
                 # Don't leave a partially initialized engine if schema fails
                 engine.dispose() # Close the engine pool if schema fails
                 raise DatabaseError(f"Schema initialization failed: {schema_err}") from schema_err


            # Store the initialized engine
            _sqla_engine = engine
            logger.info("SQLAlchemy engine initialization complete.")
            return _sqla_engine

        except SQLAlchemyError as e:
             logger.critical(f"SQLAlchemy engine creation failed: {e}", exc_info=True)
             raise DatabaseError(f"SQLAlchemy engine creation failed: {e}") from e
        except Exception as e:
            logger.critical(f"Unexpected error during SQLAlchemy initialization: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error during database initialization: {e}") from e

# --- Função para Obter o Engine ---
def get_sqlalchemy_engine() -> Engine:
    """
    Returns the singleton SQLAlchemy engine instance.

    Returns:
        The Engine instance.

    Raises:
        RuntimeError: If the engine has not been initialized.
    """
    if not _sqla_engine:
        # This should ideally not happen if init_sqlalchemy_engine is called correctly at startup
        logger.error("SQLAlchemy engine accessed before initialization.")
        raise RuntimeError("Database engine has not been initialized. Call init_sqlalchemy_engine() first.")
    return _sqla_engine

# --- Função de Desligamento do Engine (Opcional, mas bom ter) ---
def dispose_sqlalchemy_engine():
    """Closes all connections in the engine's pool. Call during application shutdown."""
    global _sqla_engine
    with _engine_lock:
        if _sqla_engine:
            logger.info("Disposing SQLAlchemy engine connection pool...")
            try:
                _sqla_engine.dispose()
                _sqla_engine = None # Clear the instance
                logger.info("SQLAlchemy engine connection pool disposed.")
            except Exception as e:
                logger.error(f"Error disposing SQLAlchemy engine pool: {e}", exc_info=True)
        else:
            logger.debug("SQLAlchemy engine shutdown called, but engine already disposed or not initialized.")


# --- Fábricas de Repositórios Atualizadas ---
def get_user_repository() -> UserRepository:
    """Gets an instance of UserRepository using the global SQLAlchemy engine."""
    engine = get_sqlalchemy_engine()
    # !!! NOTE: UserRepository constructor needs adaptation to accept Engine !!!
    return UserRepository(engine) # Pass engine

def get_observation_repository() -> ObservationRepository:
    """Gets an instance of ObservationRepository using the global SQLAlchemy engine."""
    engine = get_sqlalchemy_engine()
    # !!! NOTE: ObservationRepository constructor needs adaptation to accept Engine !!!
    return ObservationRepository(engine) # Pass engine

# --- Itens Exportados Atualizados ---
__all__ = [
    # Novas funções
    "init_sqlalchemy_engine",
    "get_sqlalchemy_engine",
    "dispose_sqlalchemy_engine",
    # Tipos/Classes (Engine opcional, Repos e Schema Manager mantidos)
    "Engine",
    "UserRepository",
    "ObservationRepository",
    "SchemaManager",
    # Funções de fábrica mantidas
    "get_user_repository",
    "get_observation_repository",
]

# Remover a importação do pool antigo se ainda existir
# from .connection_pool import ConnectionPool # REMOVER