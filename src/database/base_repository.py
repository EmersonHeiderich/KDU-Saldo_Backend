# src/database/base_repository.py
# Provides a simplified base class for ORM repositories.

from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session # Import Session stuff
from typing import Optional, Callable # Import Callable for SessionLocal type hint

from src.utils.logger import logger
from src.api.errors import DatabaseError

class BaseRepository:
    """
    Base class for data repositories using SQLAlchemy ORM Sessions.
    Stores the engine to potentially create sessions if needed,
    but individual methods should ideally receive a session.
    """

    def __init__(self, engine: Engine):
        """
        Initializes the BaseRepository.

        Args:
            engine: The SQLAlchemy Engine instance.
        """
        if not isinstance(engine, Engine):
             raise TypeError("engine must be an instance of sqlalchemy.engine.Engine")
        self.engine = engine
        # Criar a fábrica de sessões localmente se não for injetada globalmente?
        # Por simplicidade, vamos assumir que os repositórios filhos obterão
        # a sessão via get_db_session() ou injeção.
        logger.debug(f"{self.__class__.__name__} initialized with SQLAlchemy engine: {engine.url.database}")

    # Métodos _execute e _execute_transaction foram removidos.
    # Os repositórios filhos usarão a API da Sessão SQLAlchemy diretamente.
    # Ex: session.query(...), session.add(...), session.execute(select(...))

    # Poderíamos adicionar um helper para obter sessão aqui, mas é melhor
    # gerenciar a sessão externamente (ex: com get_db_session).
    # def _get_session(self) -> Session:
    #     if not self._session_factory: # Precisaria da fábrica aqui
    #         raise RuntimeError("Session factory not available in repository.")
    #     return self._session_factory()