# src/database/base_repository.py
# Provides a base class for repository implementations using SQLAlchemy Core.

import sqlite3 # Mantenha temporariamente para sqlite3.Error, mas será substituído
from sqlalchemy.engine import Engine, Connection, Result # Importações SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError, IntegrityError # Erros SQLAlchemy
from sqlalchemy import text # Para executar SQL bruto
from typing import Any, List, Optional, Dict, Tuple, Literal
from src.utils.logger import logger
from src.api.errors import DatabaseError # Import custom error

# Define FetchMode usando Literal para melhor verificação de tipo
FetchMode = Literal["all", "one", "none", "rowcount"]

class BaseRepository:
    """
    Base class for data repositories providing common database operations
    using SQLAlchemy Core Engine.
    """

    def __init__(self, engine: Engine): # Recebe Engine SQLAlchemy
        """
        Initializes the BaseRepository.

        Args:
            engine: The SQLAlchemy Engine instance to use for database access.
        """
        if not isinstance(engine, Engine):
             raise TypeError("engine must be an instance of sqlalchemy.engine.Engine")
        self.engine = engine
        logger.debug(f"{self.__class__.__name__} initialized with SQLAlchemy engine: {engine.url.database}")

    def _execute(self, query: str, params: Optional[Dict[str, Any]] = None, fetch_mode: FetchMode = "all") -> Any:
        """
        Executes a SQL query using the SQLAlchemy engine.
        NOTE: Assumes the caller manages transactions if multiple operations are needed.

        Args:
            query: The SQL query string (use :param_name placeholders).
            params: Optional dictionary of parameters for the query.
            fetch_mode: "all", "one", "none", or "rowcount".

        Returns:
            Query results based on fetch_mode:
            - "all": List of dictionaries.
            - "one": Single dictionary or None.
            - "none": Last inserted ID (if query uses RETURNING) or None.
            - "rowcount": Number of rows affected by UPDATE/DELETE.

        Raises:
            DatabaseError: For database-related errors during execution.
            ValueError: If fetch_mode is invalid.
        """
        if fetch_mode not in ("all", "one", "none", "rowcount"):
            raise ValueError(f"Invalid fetch_mode: {fetch_mode}")

        # Use o engine para obter uma conexão (gerenciada pelo 'with')
        try:
            with self.engine.connect() as connection:
                logger.debug(f"[{self.__class__.__name__}] Executing query: {query[:200]}... with params: {params} (Fetch: {fetch_mode})")

                # Execute a query usando text() para SQL bruto
                # Params devem ser um dicionário para placeholders nomeados (ex: :user_id)
                sql_text = text(query)
                result: Result = connection.execute(sql_text, parameters=params or {})

                # Tratamento do resultado baseado no fetch_mode
                output: Any = None
                if fetch_mode == "all":
                    # Result.mappings() retorna uma lista iterável de dicionários (RowMapping)
                    rows = result.mappings().all()
                    output = [dict(row) for row in rows] # Converte para dicts padrão
                    logger.debug(f"[{self.__class__.__name__}] Query returned {len(output)} rows.")
                elif fetch_mode == "one":
                    row = result.mappings().first() # Pega a primeira linha como dict ou None
                    output = dict(row) if row else None
                    logger.debug(f"[{self.__class__.__name__}] Query returned one row: {'Found' if output else 'Not Found'}.")
                elif fetch_mode == "rowcount":
                    # Result.rowcount contém o número de linhas afetadas para DML (UPDATE/DELETE)
                    # Nota: Para INSERT, pode ser -1 ou 1 dependendo do driver/setup.
                    # Para SELECT, geralmente é -1.
                    output = result.rowcount
                    logger.debug(f"[{self.__class__.__name__}] Query executed (rowcount). Rows affected: {output}")
                elif fetch_mode == "none":
                    # Útil para INSERTs. Se a query usar RETURNING id, o ID estará no resultado.
                    # .scalar_one_or_none() pega o primeiro valor da primeira linha, se houver.
                    # Isso assume que o INSERT foi escrito com "RETURNING id".
                    try:
                        output = result.scalar_one_or_none()
                        logger.debug(f"[{self.__class__.__name__}] Query executed (no fetch/scalar). Returned value (e.g., last ID): {output}")
                    except Exception as scalar_err:
                        # Pode falhar se RETURNING não foi usado ou retornou múltiplas colunas/linhas
                        logger.warning(f"[{self.__class__.__name__}] Could not get scalar result (maybe RETURNING not used?): {scalar_err}")
                        output = None

                # --- IMPORTANTE: Commits são gerenciados FORA desta função ---
                # Se esta execução for parte de uma transação maior, o commit
                # acontecerá quando o bloco 'connection.begin()' externo for concluído.
                # Se for uma operação única, o 'connection' do SQLAlchemy pode
                # operar em modo 'autocommit' dependendo da configuração do engine
                # ou do dialeto, mas é mais seguro gerenciar explicitamente com begin().
                # Para manter a API consistente, esta função NÃO faz commit.

                return output

        # Captura erros específicos do SQLAlchemy e erros gerais
        except IntegrityError as integrity_err: # Erro de violação de constraint (ex: UNIQUE)
             logger.error(f"[{self.__class__.__name__}] Database Integrity error executing query: {integrity_err}", exc_info=True)
             logger.error(f"Failed Query: {query}, Params: {params}")
             # Re-lançar como DatabaseError ou deixar o chamador tratar IntegrityError?
             # Lançar como DatabaseError pode mascarar a causa específica.
             # Vamos manter o IntegrityError por enquanto, repositórios podem capturá-lo.
             # raise DatabaseError(f"Database integrity constraint violated: {integrity_err}") from integrity_err
             raise integrity_err # Deixar o repositório específico tratar
        except SQLAlchemyError as db_err: # Outros erros SQLAlchemy (conexão, sintaxe SQL no DB, etc.)
            logger.error(f"[{self.__class__.__name__}] SQLAlchemy error executing query: {db_err}", exc_info=True)
            logger.error(f"Failed Query: {query}, Params: {params}")
            raise DatabaseError(f"Database error occurred: {db_err}") from db_err
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] General error executing query: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred during database operation: {e}") from e


    def _execute_transaction(self, operations: List[Tuple[str, Optional[Dict[str, Any]]]]) -> bool:
        """
        Executes multiple SQL operations within a single transaction using SQLAlchemy.

        Args:
            operations: A list of tuples, where each tuple contains:
                        (query_string with :param placeholders,
                         optional_parameters_dictionary).

        Returns:
            True if the transaction was successful.

        Raises:
            DatabaseError: If a connection cannot be acquired or a database error occurs during the transaction.
            IntegrityError: If a constraint violation occurs during the transaction.
        """
        # Use o engine para obter uma conexão
        try:
            with self.engine.connect() as connection:
                # Inicie uma transação (commit/rollback automático pelo 'with')
                with connection.begin():
                    logger.debug(f"[{self.__class__.__name__}] Starting transaction with {len(operations)} operations.")
                    for i, (query, params) in enumerate(operations):
                        logger.debug(f"[{self.__class__.__name__}] Transaction op {i+1}: {query[:200]}... with params: {params}")
                        sql_text = text(query)
                        connection.execute(sql_text, parameters=params or {})
                    logger.debug(f"[{self.__class__.__name__}] Transaction operations executed successfully (commit pending).")
            # Se chegou aqui sem erro, o 'connection.begin()' fez commit automaticamente.
            logger.debug(f"[{self.__class__.__name__}] Transaction committed successfully.")
            return True

        # Captura erros específicos e gerais
        except IntegrityError as integrity_err:
             # O rollback é feito automaticamente pelo 'connection.begin()'
             logger.error(f"[{self.__class__.__name__}] Database Integrity error during transaction: {integrity_err}", exc_info=True)
             raise integrity_err # Re-lança para o chamador
        except SQLAlchemyError as db_err:
            # O rollback é feito automaticamente
            logger.error(f"[{self.__class__.__name__}] SQLAlchemy error during transaction: {db_err}", exc_info=True)
            raise DatabaseError(f"Database transaction failed: {db_err}") from db_err
        except Exception as e:
            # O rollback é feito automaticamente
            logger.error(f"[{self.__class__.__name__}] General error during transaction: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred during database transaction: {e}") from e