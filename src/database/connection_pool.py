# src/database/connection_pool.py
# Implements a thread-safe connection pool for SQLite.

import sqlite3
import threading
import queue
import time
import os
from typing import Optional
from src.utils.logger import logger

class ConnectionPool:
    """
    A thread-safe pool for managing SQLite database connections.

    Ensures that connections are reused and limits the total number
    of active connections. Associates connections with threads to
    handle SQLite's thread safety requirements better.
    """
    _instance = None
    _lock = threading.Lock()

    # Making it a Singleton might simplify management in Flask app context
    def __new__(cls, *args, **kwargs):
         # This Singleton approach might be overly complex if init_db handles it.
         # Consider removing if init_db manages the single instance properly.
         if not cls._instance:
              with cls._lock:
                   if not cls._instance:
                        cls._instance = super(ConnectionPool, cls).__new__(cls)
         return cls._instance

    def __init__(self, db_path: str, max_connections: int = 5, timeout: int = 10):
        """
        Initializes the connection pool. Should ideally be called only once.

        Args:
            db_path: Absolute or relative path to the SQLite database file.
            max_connections: Maximum number of simultaneous connections allowed.
            timeout: Time in seconds to wait for a connection if the pool is full.
        """
        # Prevent re-initialization in Singleton pattern
        if hasattr(self, '_initialized') and self._initialized:
             return
        with self._lock:
            if hasattr(self, '_initialized') and self._initialized:
                 return

            self.db_path = os.path.abspath(db_path) # Store absolute path
            self.max_connections = max_connections
            self.timeout = timeout
            # Use LifoQueue for potentially better performance (last used = likely hottest cache)
            self.pool = queue.LifoQueue(maxsize=max_connections)
            # Using context managers (threading.local) for thread-specific data
            self._local = threading.local()
            self._active_connections = 0 # Total connections created (in pool + in use)
            self._creation_lock = threading.Lock() # Lock specifically for creating connections

            logger.info(f"Initializing ConnectionPool for '{self.db_path}' (Max: {max_connections}, Timeout: {self.timeout}s)")
            # Pre-populate the pool? Optional, can add startup cost.
            # for _ in range(min(max_connections // 2, 2)): # Example: pre-populate a few
            #     try:
            #         conn = self._create_connection()
            #         self.pool.put_nowait(conn)
            #         self._active_connections += 1
            #     except Exception:
            #         # Log error but continue initialization
            #         logger.error("Failed to pre-populate connection pool.")
            #         break

            self._initialized = True # Mark as initialized

    def _create_connection(self) -> sqlite3.Connection:
        """Creates a new SQLite connection."""
        try:
            # Ensure the directory exists
            db_dir = os.path.dirname(self.db_path)
            os.makedirs(db_dir, exist_ok=True)

            # check_same_thread=False is generally okay with proper pooling and
            # thread-local management, but be mindful if using complex transactions
            # across different threads implicitly.
            conn = sqlite3.connect(self.db_path, timeout=self.timeout, check_same_thread=False,
                                   isolation_level=None) # Use autocommit mode, manage transactions explicitly
            conn.row_factory = sqlite3.Row # Return rows that act like dictionaries
            # Enable WAL mode for better concurrency (optional, but recommended)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;") # Balance safety and speed
            except sqlite3.Error as prag_err:
                 logger.warning(f"Could not set PRAGMA options (WAL/Synchronous): {prag_err}")

            logger.debug(f"SQLite connection created for '{self.db_path}' (id={id(conn)})")
            return conn
        except sqlite3.Error as e:
            logger.error(f"Failed to create SQLite connection to '{self.db_path}': {e}", exc_info=True)
            raise DatabaseError(f"Failed to connect to database: {e}") from e # Use custom error

    def get_connection(self) -> sqlite3.Connection:
        """
        Gets a connection for the current thread. Reuses if one exists,
        otherwise retrieves from pool or creates a new one.

        Returns:
            A sqlite3.Connection object.

        Raises:
            DatabaseError: If unable to get a connection within the timeout.
        """
        # Check if the current thread already has a connection
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            # Optional: Ping connection to check if still alive? Might add overhead.
            # try:
            #     self._local.conn.execute("SELECT 1").fetchone()
            #     logger.debug(f"Reusing existing connection for thread {threading.get_ident()} (id={id(self._local.conn)})")
            #     return self._local.conn
            # except sqlite3.Error:
            #     logger.warning(f"Existing connection for thread {threading.get_ident()} seems dead. Closing and getting new one.")
            #     self._close_connection_internal(self._local.conn) # Close the dead connection
            #     delattr(self._local, 'conn')
            #     # Fall through to get a new connection
            logger.debug(f"Reusing existing connection for thread {threading.get_ident()} (id={id(self._local.conn)})")
            return self._local.conn


        conn: Optional[sqlite3.Connection] = None
        start_time = time.monotonic()
        try:
            # Try getting from pool without blocking initially
            conn = self.pool.get_nowait()
            logger.debug(f"Connection obtained from pool for thread {threading.get_ident()} (id={id(conn)})")
        except queue.Empty:
            # Pool is empty, try creating if limit not reached
            with self._creation_lock: # Ensure only one thread tries to create at a time when limit is near
                if self._active_connections < self.max_connections:
                    try:
                        conn = self._create_connection()
                        self._active_connections += 1
                        logger.debug(f"Created new connection for thread {threading.get_ident()} (id={id(conn)}). Active: {self._active_connections}")
                    except Exception:
                         # Creation failed, fall through to waiting on the pool
                         logger.error("Connection creation failed, will wait for pool.")
                         pass # Ensure we still try waiting below

            if conn is None:
                 # Limit reached or creation failed, wait for a connection from the pool
                 wait_timeout = self.timeout - (time.monotonic() - start_time)
                 if wait_timeout <= 0:
                      logger.error(f"Timeout exceeded immediately while waiting for connection (active: {self._active_connections}).")
                      raise DatabaseError("Timeout acquiring database connection.")

                 logger.debug(f"Pool empty/limit reached, waiting up to {wait_timeout:.2f}s for connection (active: {self._active_connections})...")
                 try:
                      conn = self.pool.get(block=True, timeout=wait_timeout)
                      logger.debug(f"Connection obtained from pool after waiting for thread {threading.get_ident()} (id={id(conn)})")
                 except queue.Empty:
                      logger.error(f"Timeout ({self.timeout}s) exceeded while waiting for database connection (active: {self._active_connections}).")
                      raise DatabaseError("Timeout acquiring database connection.")

        # Store the connection in thread-local storage
        self._local.conn = conn
        return conn

    def release_connection(self, conn: Optional[sqlite3.Connection] = None):
        """
        Releases the connection associated with the current thread back to the pool.
        If an explicit connection `conn` is provided, it tries to release that one,
        but primarily designed to release the thread's current connection.
        """
        # Get the connection associated with the current thread
        thread_conn = getattr(self._local, 'conn', None)

        # If an explicit conn is passed and it's DIFFERENT from the thread's conn, log a warning
        if conn is not None and conn is not thread_conn:
             logger.warning(f"release_connection called with explicit conn (id={id(conn)}) different from thread's conn (id={id(thread_conn)}). Releasing thread's connection.")
             # Prioritize releasing the thread's connection to avoid leaks

        if thread_conn is None:
             # logger.debug(f"No connection associated with thread {threading.get_ident()} to release.")
             return # Nothing to release for this thread

        # Clear the connection from thread-local storage *before* putting back in pool
        delattr(self._local, 'conn')

        try:
            # Optional: Rollback any pending transaction before releasing?
            # try:
            #     thread_conn.rollback() # Ensure clean state
            # except sqlite3.Error as rb_err:
            #     # Ignore if rollback fails (e.g., connection closed)
            #     logger.debug(f"Rollback failed during release (conn id={id(thread_conn)}): {rb_err}")

            logger.debug(f"Releasing connection (id={id(thread_conn)}) for thread {threading.get_ident()} to pool.")
            self.pool.put_nowait(thread_conn) # Use nowait as pool size should accommodate
        except queue.Full:
            # Pool is somehow full (shouldn't happen if max_connections is managed correctly)
            logger.warning(f"Pool full when releasing connection (id={id(thread_conn)}). Closing connection instead.")
            self._close_connection_internal(thread_conn) # Close the connection
        except Exception as e:
             logger.error(f"Error releasing connection (id={id(thread_conn)}): {e}", exc_info=True)
             # Close the connection if putting back failed, to prevent leaks
             self._close_connection_internal(thread_conn)


    def _close_connection_internal(self, conn: sqlite3.Connection):
         """Internal helper to close a connection and decrement active count."""
         if conn:
              try:
                   conn.close()
                   logger.debug(f"Connection closed (id={id(conn)})")
                   with self._creation_lock: # Protect active_connections count
                        self._active_connections -= 1
                        # Clamp to zero just in case
                        self._active_connections = max(0, self._active_connections)
                   logger.debug(f"Active connections count: {self._active_connections}")
              except Exception as e:
                   logger.error(f"Error closing connection (id={id(conn)}): {e}", exc_info=True)
                   # Even if closing fails, decrement count as it's unusable
                   with self._creation_lock:
                        self._active_connections -= 1
                        self._active_connections = max(0, self._active_connections)


    def close_all(self):
        """Closes all connections currently in the pool and marks pool as inactive."""
        logger.info(f"Closing all connections in pool for '{self.db_path}'...")
        # Clear thread-local storage for the current thread immediately
        if hasattr(self._local, 'conn'):
            delattr(self._local, 'conn')

        closed_count = 0
        # Drain the queue and close connections
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                self._close_connection_internal(conn)
                closed_count += 1
            except queue.Empty:
                break # Pool is empty
            except Exception as e:
                 logger.error(f"Error closing connection from pool: {e}", exc_info=True)

        logger.info(f"Closed {closed_count} connections from the pool. Active connections remaining (should be in use by threads): {self._active_connections}")
        # Note: Connections currently in use by other threads are not closed here.
        # They will be closed when released back to a full (or non-existent) pool,
        # or potentially leak if release_connection is never called by that thread.
        # Proper teardown in the web framework (like Flask's teardown_appcontext)
        # is crucial for releasing connections held by request threads.

        # Reset pool state
        # self.pool = queue.LifoQueue(maxsize=self.max_connections) # Recreate if needed? Or just mark inactive?
        # self._active_connections = 0 # Risky if other threads still hold connections
        self._initialized = False # Mark as requiring re-initialization
        ConnectionPool._instance = None # Clear singleton instance if using that pattern
        logger.info("Connection pool closed.")

    # --- Add methods to expose repositories ---
    # This tightly couples the pool to specific repositories, an alternative
    # is the factory functions in database/__init__.py
    def get_user_repository(self) -> 'UserRepository':
        from .user_repository import UserRepository # Local import
        return UserRepository(self)

    def get_observation_repository(self) -> 'ObservationRepository':
        from .observation_repository import ObservationRepository # Local import
        return ObservationRepository(self)

# Import custom error at the end to avoid circular dependency if DatabaseError uses logger
from src.api.errors import DatabaseError