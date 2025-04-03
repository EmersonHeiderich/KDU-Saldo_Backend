# src/database/user_repository.py
# Gerencia operações de banco de dados relacionadas a Usuários e Permissões usando SQLAlchemy ORM.

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, delete, update
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .base_repository import BaseRepository
from src.domain.user import User, UserPermissions
from src.utils.logger import logger
from src.api.errors import DatabaseError, NotFoundError, ValidationError

class UserRepository(BaseRepository):
    """
    Repositório para gerenciar dados de Usuário e Permissões usando Sessões SQLAlchemy ORM.
    Os métodos agora esperam que um objeto Session seja passado.
    """

    def find_by_username(self, db: Session, username: str) -> Optional[User]:
        """
        Busca um usuário ativo pelo nome de usuário (case-insensitive) usando Sessão ORM.
        """
        logger.debug(f"ORM: Buscando usuário ativo pelo username '{username}'")
        try:
            stmt = (
                select(User)
                .options(joinedload(User.permissions))
                .where(func.lower(User.username) == func.lower(username))
                .where(User.is_active == True)
            )
            user = db.scalars(stmt).first()

            if user:
                logger.debug(f"ORM: Usuário encontrado pelo username '{username}': ID {user.id}")
            else:
                logger.debug(f"ORM: Usuário ativo não encontrado pelo username '{username}'.")
            return user
        except SQLAlchemyError as e:
            logger.error(f"ORM: Erro de banco de dados ao buscar usuário pelo username '{username}': {e}", exc_info=True)
            raise DatabaseError(f"Erro de banco de dados ao buscar usuário pelo username: {e}") from e
        except Exception as e:
            logger.error(f"ORM: Erro inesperado ao buscar usuário pelo username '{username}': {e}", exc_info=True)
            raise DatabaseError(f"Erro inesperado ao buscar usuário pelo username: {e}") from e

    def find_by_id(self, db: Session, user_id: int) -> Optional[User]:
        """Busca um usuário pelo ID usando Sessão ORM (independente do status ativo)."""
        logger.debug(f"ORM: Buscando usuário pelo ID {user_id}")
        try:
            user = db.get(User, user_id, options=[joinedload(User.permissions)])
            if user:
                 logger.debug(f"ORM: Usuário encontrado pelo ID {user_id}.")
                 if user.permissions is None:
                      logger.warning(f"ORM: Usuário ID {user_id} encontrado, mas relacionamento permissions é None. Inconsistência de dados?")
            else:
                 logger.debug(f"ORM: Usuário não encontrado pelo ID {user_id}.")
            return user
        except SQLAlchemyError as e:
            logger.error(f"ORM: Erro de banco de dados ao buscar usuário pelo ID {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Erro de banco de dados ao buscar usuário pelo ID: {e}") from e
        except Exception as e:
            logger.error(f"ORM: Erro inesperado ao buscar usuário pelo ID {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Erro inesperado ao buscar usuário pelo ID: {e}") from e

    def get_all(self, db: Session) -> List[User]:
        """Recupera todos os usuários do banco de dados usando Sessão ORM."""
        logger.debug("ORM: Recuperando todos os usuários")
        try:
            stmt = select(User).options(joinedload(User.permissions)).order_by(User.username)
            users = db.scalars(stmt).all()
            logger.debug(f"ORM: Recuperados {len(users)} usuários do banco de dados.")
            return list(users)
        except SQLAlchemyError as e:
             logger.error(f"ORM: Erro de banco de dados ao recuperar todos os usuários: {e}", exc_info=True)
             raise DatabaseError(f"Erro de banco de dados ao recuperar todos os usuários: {e}") from e
        except Exception as e:
             logger.error(f"ORM: Erro inesperado ao recuperar todos os usuários: {e}", exc_info=True)
             raise DatabaseError(f"Erro inesperado ao recuperar todos os usuários: {e}") from e

    def add(self, db: Session, user: User) -> User:
        """Adiciona um novo usuário e suas permissões usando Sessão ORM."""
        if not user.username or not user.password_hash or not user.name:
             raise ValueError("Campos obrigatórios faltando (username, password_hash, name) para Usuário.")
        if user.permissions is None:
             logger.warning(f"Objeto User para '{user.username}' está sem objeto UserPermissions associado. Criando padrão.")
             user.permissions = UserPermissions()

        logger.debug(f"ORM: Adicionando usuário '{user.username}' à sessão")
        try:
            if user.created_at is None:
                user.created_at = datetime.now(timezone.utc)

            db.add(user)
            db.flush()
            logger.info(f"ORM: Usuário '{user.username}' adicionado à sessão (ID: {user.id}, Perm ID: {getattr(user.permissions, 'id', None)}). Commit pendente.")
            return user
        except IntegrityError as e:
            db.rollback()
            logger.warning(f"ORM: Erro de integridade do banco de dados ao adicionar usuário '{user.username}': {e}")
            error_info = str(e.orig).lower() if e.orig else str(e).lower()
            if "users_username_key" in error_info or "unique constraint" in error_info and "username" in error_info:
                 raise ValueError(f"Username '{user.username}' já existe.")
            if "users_email_key" in error_info or "unique constraint" in error_info and "email" in error_info and user.email:
                 raise ValueError(f"Email '{user.email}' já existe.")
            raise DatabaseError(f"Falha ao adicionar usuário devido a restrição de integridade: {e}") from e
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"ORM: Erro de banco de dados ao adicionar usuário '{user.username}': {e}", exc_info=True)
            raise DatabaseError(f"Falha ao adicionar usuário: {e}") from e
        except Exception as e:
            db.rollback()
            logger.error(f"ORM: Erro inesperado ao adicionar usuário '{user.username}': {e}", exc_info=True)
            raise DatabaseError(f"Ocorreu um erro inesperado ao adicionar usuário: {e}") from e


    def update(self, db: Session, user_to_update: User) -> User:
        """Atualiza um usuário existente e suas permissões usando Sessão ORM."""
        if user_to_update.id is None:
            raise ValueError("Não é possível atualizar usuário sem um ID.")
        if not user_to_update.password_hash:
             raise ValueError("Hash de senha não pode estar vazio para atualização.")

        logger.debug(f"ORM: Atualizando usuário ID {user_to_update.id} na sessão")
        try:
            db.flush()
            logger.info(f"ORM: Usuário ID {user_to_update.id} marcado para atualização na sessão. Commit pendente.")
            return user_to_update
        except IntegrityError as e:
            db.rollback()
            logger.warning(f"ORM: Erro de integridade do banco de dados ao atualizar usuário ID {user_to_update.id}: {e}")
            error_info = str(e.orig).lower() if e.orig else str(e).lower()
            if "users_email_key" in error_info or "unique constraint" in error_info and "email" in error_info:
                 raise ValueError(f"Email '{user_to_update.email}' já está em uso por outro usuário.")
            raise DatabaseError(f"Falha ao atualizar usuário devido a restrição de integridade: {e}") from e
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"ORM: Erro de banco de dados ao atualizar usuário ID {user_to_update.id}: {e}", exc_info=True)
            raise DatabaseError(f"Falha ao atualizar usuário: {e}") from e
        except Exception as e:
            db.rollback()
            logger.error(f"ORM: Erro inesperado ao atualizar usuário ID {user_to_update.id}: {e}", exc_info=True)
            raise DatabaseError(f"Ocorreu um erro inesperado ao atualizar usuário: {e}") from e

    def delete(self, db: Session, user_id: int) -> bool:
        """Exclui um usuário pelo ID usando Sessão ORM."""
        logger.debug(f"ORM: Excluindo usuário ID {user_id}")
        try:
            user = db.get(User, user_id)
            if user:
                db.delete(user)
                db.flush()
                logger.info(f"ORM: Usuário ID {user_id} marcado para exclusão na sessão. Commit pendente.")
                return True
            else:
                logger.warning(f"ORM: Tentativa de excluir usuário ID {user_id}, mas usuário não foi encontrado.")
                return False
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"ORM: Erro de banco de dados ao excluir usuário ID {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Falha ao excluir usuário: {e}") from e
        except Exception as e:
            db.rollback()
            logger.error(f"ORM: Erro inesperado ao excluir usuário ID {user_id}: {e}", exc_info=True)
            raise DatabaseError(f"Ocorreu um erro inesperado ao excluir usuário: {e}") from e

    def update_last_login(self, db: Session, user_id: int) -> bool:
        """Atualiza o timestamp de último login para um usuário usando Sessão ORM."""
        logger.debug(f"ORM: Atualizando último login para usuário ID {user_id}")
        try:
            user = db.get(User, user_id)
            if user:
                user.last_login = datetime.now(timezone.utc)
                db.flush()
                logger.debug(f"ORM: Último login do Usuário ID {user_id} marcado para atualização. Commit pendente.")
                return True
            else:
                 logger.warning(f"ORM: Falha ao atualizar último login para usuário ID {user_id} (usuário não encontrado).")
                 return False
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"ORM: Falha ao atualizar último login para usuário ID {user_id}: {e}", exc_info=True)
            return False
        except Exception as e:
             db.rollback()
             logger.error(f"ORM: Erro inesperado ao atualizar último login para usuário ID {user_id}: {e}", exc_info=True)
             return False