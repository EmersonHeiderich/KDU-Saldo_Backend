# src/database/base_repository.py
# Provides a base class for repository implementations with common DB operations.

import sqlite3
from typing import Any, List, Optional, Dict, Tuple, Literal # Use Literal for FetchMode
from .connection_pool import ConnectionPool
from src.utils.logger import logger
from src.api.errors import DatabaseError # Import custom error

# Define FetchMode using Literal for better type checking
FetchMode = Literal["all", "one", "none", "rowcount"]

class BaseRepository:
    """
    Base class for data repositories providing common database operations.
    Manages connection acquisition and release from a connection pool.
    """

    def __init__(self, connection_pool: ConnectionPool):
        """
        Initializes the BaseRepository.

        Args:
            connection_pool: The ConnectionPool instance to use for database access.
        """
        if not isinstance(connection_pool, ConnectionPool):
             raise TypeError("connection_pool must be an instance of ConnectionPool")
        self.connection_pool = connection_pool
        logger.debug(f"{self.__class__.__name__} initialized with pool: {connection_pool.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """
        Acquires a database connection from the pool.

        Returns:
            A sqlite3.Connection object.

        Raises:
            DatabaseError: If a connection cannot be acquired.
        """
        try:
            logger.debug(f"[{self.__class__.__name__}] Acquiring connection from pool...")
            conn = self.connection_pool.get_connection()
            # Set row factory after acquiring
            conn.row_factory = sqlite3.Row
            logger.debug(f"[{self.__class__.__name__}] Connection acquired (id={id(conn)})")
            return conn
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Failed to acquire database connection: {e}", exc_info=True)
            raise DatabaseError("Failed to acquire database connection") from e

    def _release_connection(self, conn: Optional[sqlite3.Connection]):
        """
        Releases a database connection back to the pool.

        Args:
            conn: The sqlite3.Connection object to release. If None, does nothing.
        """
        if conn:
            try:
                logger.debug(f"[{self.__class__.__name__}] Releasing connection (id={id(conn)}) back to pool.")
                # Optionally reset row_factory before release if it was changed
                # conn.row_factory = None
                self.connection_pool.release_connection(conn)
            except Exception as e:
                logger.error(f"[{self.__class__.__name__}] Failed to release database connection (id={id(conn)}): {e}", exc_info=True)
                # Don't raise here, as the primary operation might have succeeded.

    def _execute(self, query: str, params: Optional[Tuple] = None, fetch_mode: FetchMode = "all", conn: Optional[sqlite3.Connection] = None, single_op: bool = False) -> Any:
        """
        Executes a SQL query using a provided or acquired connection.

        Args:
            query: The SQL query string.
            params: Optional tuple of parameters for the query.
            fetch_mode: "all", "one", "none", or "rowcount".
            conn: Optional existing connection to use. If None, acquires a new one.
            single_op: If True and conn is None, commit/rollback happens within this method.
                       If False or conn is provided, caller manages transaction.

        Returns:
            Query results based on fetch_mode:
            - "all": List of dictionaries.
            - "one": Single dictionary or None.
            - "none": Last inserted row ID (for INSERT) or None otherwise.
            - "rowcount": Number of rows affected by UPDATE/DELETE, or None on error.

        Raises:
            DatabaseError: For database-related errors during execution.
            ValueError: If fetch_mode is invalid.
        """
        acquired_conn = None
        if conn is None:
            acquired_conn = self._get_connection()
            target_conn = acquired_conn
        else:
            target_conn = conn

        # Ensure row_factory is set (might be reset by pool or other parts)
        if target_conn.row_factory is not sqlite3.Row:
            target_conn.row_factory = sqlite3.Row

        if fetch_mode not in ("all", "one", "none", "rowcount"):
            if acquired_conn: self._release_connection(acquired_conn)
            raise ValueError(f"Invalid fetch_mode: {fetch_mode}")

        cursor = None
        try:
            logger.debug(f"[{self.__class__.__name__}] Executing query: {query} with params: {params} (Fetch: {fetch_mode}, SingleOp: {single_op and acquired_conn is not None})")
            cursor = target_conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            result: Any = None
            rows_affected: Optional[int] = None # Store rowcount for logging/return

            # Capture rowcount immediately after execute for UPDATE/DELETE
            if query.strip().upper().startswith(("UPDATE", "DELETE")):
                 rows_affected = cursor.rowcount

            if fetch_mode == "all":
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
                logger.debug(f"[{self.__class__.__name__}] Query returned {len(result)} rows.")
            elif fetch_mode == "one":
                row = cursor.fetchone()
                result = dict(row) if row else None
                logger.debug(f"[{self.__class__.__name__}] Query returned one row: {'Found' if result else 'Not Found'}.")
            elif fetch_mode == "rowcount":
                 result = rows_affected
                 logger.debug(f"[{self.__class__.__name__}] Query executed (rowcount). Rows affected: {result}")
            else: # "none"
                result = cursor.lastrowid if query.strip().upper().startswith("INSERT") else None
                logger.debug(f"[{self.__class__.__name__}] Query executed (no fetch). Last row ID: {result}")

            # Commit if we acquired the connection AND it's flagged as a single operation.
            if acquired_conn and single_op:
                 logger.debug(f"[{self.__class__.__name__}] Committing changes for single operation.")
                 target_conn.commit()

            return result

        except sqlite3.Error as db_err:
            # Rollback if we acquired the connection AND it's flagged as a single operation.
            if acquired_conn and single_op:
                 logger.warning(f"[{self.__class__.__name__}] Rolling back single operation due to SQLite error.")
                 try: acquired_conn.rollback()
                 except Exception as rb_err: logger.error(f"[{self.__class__.__name__}] Error during single op rollback: {rb_err}", exc_info=True)

            logger.error(f"[{self.__class__.__name__}] SQLite error executing query: {db_err}", exc_info=True)
            logger.error(f"Failed Query: {query}, Params: {params}")
            raise DatabaseError(f"Database error occurred: {db_err}") from db_err
        except Exception as e:
             # Rollback if we acquired the connection AND it's flagged as a single operation.
            if acquired_conn and single_op:
                 logger.warning(f"[{self.__class__.__name__}] Rolling back single operation due to general error.")
                 try: acquired_conn.rollback()
                 except Exception as rb_err: logger.error(f"[{self.__class__.__name__}] Error during single op rollback: {rb_err}", exc_info=True)

            logger.error(f"[{self.__class__.__name__}] General error executing query: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred during database operation: {e}") from e
        finally:
             if cursor:
                 try: cursor.close()
                 except Exception as cur_err: logger.warning(f"[{self.__class__.__name__}] Error closing cursor: {cur_err}")
             # Release connection only if it was acquired within this method
             if acquired_conn:
                 self._release_connection(acquired_conn)


    def _execute_transaction(self, operations: List[Tuple[str, Optional[Tuple]]]) -> bool:
        """
        Executes multiple SQL operations within a single transaction.
        The caller ensures the operations make sense together.

        Args:
            operations: A list of tuples, where each tuple contains:
                        (query_string, optional_parameters_tuple).

        Returns:
            True if the transaction was successful.

        Raises:
            DatabaseError: If a connection cannot be acquired or a database error occurs during the transaction.
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            logger.debug(f"[{self.__class__.__name__}] Starting transaction with {len(operations)} operations.")
            conn.execute("BEGIN;") # Explicitly start transaction

            for i, (query, params) in enumerate(operations):
                logger.debug(f"[{self.__class__.__name__}] Transaction op {i+1}: {query} with params: {params}")
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

            conn.commit() # Commit transaction
            logger.debug(f"[{self.__class__.__name__}] Transaction committed successfully.")
            return True

        except sqlite3.Error as db_err:
            if conn:
                 logger.warning(f"[{self.__class__.__name__}] Rolling back transaction due to SQLite error.")
                 try: conn.rollback()
                 except Exception as rb_err: logger.error(f"[{self.__class__.__name__}] Error during transaction rollback: {rb_err}", exc_info=True)
            logger.error(f"[{self.__class__.__name__}] SQLite error during transaction: {db_err}", exc_info=True)
            raise DatabaseError(f"Database transaction failed: {db_err}") from db_err
        except Exception as e:
            if conn:
                 logger.warning(f"[{self.__class__.__name__}] Rolling back transaction due to general error.")
                 try: conn.rollback()
                 except Exception as rb_err: logger.error(f"[{self.__class__.__name__}] Error during transaction rollback: {rb_err}", exc_info=True)
            logger.error(f"[{self.__class__.__name__}] General error during transaction: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred during database transaction: {e}") from e
        finally:
            if conn:
                self._release_connection(conn) # Release connection back to pool

    def _get_last_insert_id(self, conn: sqlite3.Connection) -> Optional[int]:
        """
        Gets the rowid of the last row inserted in the *current* connection.
        Should be called within the same transaction/connection context as the INSERT.
        NOTE: Use cursor.lastrowid directly after execute within the same cursor context for reliability.

        Args:
            conn: The connection used for the INSERT statement.

        Returns:
            The last inserted row ID, or None if no insert occurred or not applicable.
        """
        cursor = None
        try:
             # This approach is less reliable than using cursor.lastrowid immediately after execute
             logger.warning("Using SELECT last_insert_rowid() is less reliable than cursor.lastrowid")
             cursor = conn.cursor()
             cursor.execute("SELECT last_insert_rowid()")
             result = cursor.fetchone()
             return result[0] if result else None
        except sqlite3.Error as e:
             logger.error(f"[{self.__class__.__name__}] Error getting last insert ID: {e}", exc_info=True)
             return None
        finally:
             if cursor:
                  try: cursor.close()
                  except Exception as cur_err: logger.warning(f"[{self.__class__.__name__}] Error closing cursor for last insert ID: {cur_err}")