# src/database/__init__.py
# Initializes and manages database components.

import threading
from typing import Optional
from .connection_pool import ConnectionPool
from .schema_manager import SchemaManager
from .user_repository import UserRepository
from .observation_repository import ObservationRepository
from src.utils.logger import logger

# Global pool instance (initialized by init_db)
_db_pool_instance: Optional[ConnectionPool] = None
_db_lock = threading.Lock()

def init_db(database_path: str, max_connections: int = 10, timeout: int = 30) -> ConnectionPool:
    """
    Initializes the database connection pool and schema.
    Should be called once during application startup.

    Args:
        database_path: Path to the SQLite database file.
        max_connections: Maximum number of connections in the pool.
        timeout: Timeout for acquiring a connection.

    Returns:
        The initialized ConnectionPool instance.

    Raises:
        Exception: If initialization fails.
    """
    global _db_pool_instance
    with _db_lock:
        if _db_pool_instance:
            logger.warning("Database pool already initialized.")
            return _db_pool_instance

        logger.info(f"Initializing database at: {database_path}")
        try:
            pool = ConnectionPool(database_path, max_connections, timeout)
            schema_manager = SchemaManager(pool)
            schema_manager.initialize_schema() # Creates tables, runs migrations

            # Store the initialized pool
            _db_pool_instance = pool
            logger.info("Database initialization complete.")
            return _db_pool_instance
        except Exception as e:
            logger.critical(f"Database initialization failed: {e}", exc_info=True)
            # Ensure pool is cleaned up if partially created before error
            if 'pool' in locals() and isinstance(pool, ConnectionPool):
                try:
                    pool.close_all()
                except Exception as close_e:
                    logger.error(f"Error closing pool during failed init: {close_e}")
            _db_pool_instance = None # Ensure instance is None on failure
            raise # Re-raise the exception to signal failure

def get_db_pool() -> ConnectionPool:
    """
    Returns the singleton database connection pool instance.

    Returns:
        The ConnectionPool instance.

    Raises:
        RuntimeError: If the database pool has not been initialized.
    """
    # No need for lock here if _db_pool_instance is set only once during init
    if not _db_pool_instance:
        # This should ideally not happen if init_db is called correctly at startup
        logger.error("Database pool accessed before initialization.")
        raise RuntimeError("Database pool has not been initialized. Call init_db() first.")
    return _db_pool_instance

def release_db_connection(exception=None):
    """Releases the current thread's connection back to the pool."""
    pool = _db_pool_instance # Get instance directly (safe after init)
    if pool:
        # Pass None explicitly so release_connection uses thread-local
        pool.release_connection(None)
        # logger.debug("Database connection released for this context.") # Can be noisy
    # else: # Should not happen if app started correctly
    #     logger.warning("Attempted to release DB connection, but pool is not initialized.")


def close_db_pool():
    """Closes all connections in the pool. Call during application shutdown ONLY."""
    global _db_pool_instance
    with _db_lock:
        if _db_pool_instance:
            logger.info("Closing database connection pool...")
            try:
                _db_pool_instance.close_all()
                _db_pool_instance = None # Clear the instance
                logger.info("Database connection pool closed.")
            except Exception as e:
                logger.error(f"Error closing database pool: {e}", exc_info=True)
        else:
            logger.debug("Database pool shutdown called, but pool already closed or not initialized.")

# --- Convenience methods to get repositories ---
def get_user_repository() -> UserRepository:
    """Gets an instance of UserRepository using the global pool."""
    pool = get_db_pool()
    return UserRepository(pool)

def get_observation_repository() -> ObservationRepository:
    """Gets an instance of ObservationRepository using the global pool."""
    pool = get_db_pool()
    return ObservationRepository(pool)


__all__ = [
    "init_db",
    "get_db_pool",
    "release_db_connection", # Expose release function
    "close_db_pool",         # Expose pool closing function (rename original close_db)
    "ConnectionPool",
    "UserRepository",
    "ObservationRepository",
    "SchemaManager",
    "get_user_repository",
    "get_observation_repository",
]