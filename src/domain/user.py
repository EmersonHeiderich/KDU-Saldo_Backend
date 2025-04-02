# src/domain/user.py
# Define os modelos ORM para User e UserPermissions usando SQLAlchemy.

from datetime import datetime, timezone
import bcrypt
# !!! IMPORTAR TYPE_CHECKING !!!
from typing import Optional, Dict, Any, TYPE_CHECKING # Adicionado TYPE_CHECKING
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, func, Text
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import TIMESTAMP

# Importar Base DEPOIS de TYPE_CHECKING para garantir ordem correta
from src.database.base import Base
from src.utils.logger import logger

# --- Bloco TYPE_CHECKING para imports circulares ---
if TYPE_CHECKING:
    # Mover UserPermissions para cá se usado apenas para type hint no relacionamento
    # Isso quebra o ciclo de importação em tempo de execução
    from .user import UserPermissions
# ----------------------------------------------------

# --- Classe UserPermissions ---
# A definição desta classe precisa vir ANTES de ser usada no relacionamento de User,
# ou usamos strings em ambos os lados do relacionamento. Vamos mantê-la aqui.
class UserPermissions(Base):
    """
    Representa as permissões ORM associadas a um usuário.
    """
    __tablename__ = 'user_permissions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_access_products: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_access_fabrics: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_access_customer_panel: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_access_fiscal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_access_accounts_receivable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- Relacionamento de volta para User ---
    # Usar string "User" aqui para evitar importação direta em tempo de execução
    user: Mapped["User"] = relationship(back_populates="permissions")

    def to_dict(self) -> Dict[str, Any]:
        """Converte o objeto UserPermissions para um dicionário."""
        return {
            'id': self.id, 'user_id': self.user_id, 'is_admin': self.is_admin,
            'can_access_products': self.can_access_products, 'can_access_fabrics': self.can_access_fabrics,
            'can_access_customer_panel': self.can_access_customer_panel, 'can_access_fiscal': self.can_access_fiscal,
            'can_access_accounts_receivable': self.can_access_accounts_receivable,
        }
    def __repr__(self):
        """Representação textual do objeto UserPermissions."""
        return f"<UserPermissions(id={self.id}, user_id={self.user_id}, is_admin={self.is_admin})>"


# --- Classe User ---
class User(Base):
    """
    Representa um usuário da aplicação como modelo ORM.
    """
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(Text, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- Relacionamento um-para-um com UserPermissions ---
    # Usar string "UserPermissions" para o tipo no relacionamento
    permissions: Mapped["UserPermissions"] = relationship(
        "UserPermissions", # <<<--- Usar string aqui para quebrar o ciclo de importação
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False, # Importante para um-para-um
        lazy="joined" # Carrega permissões junto com o usuário
    )

    # --- Métodos de Lógica ---
    def set_password(self, password: str):
        """Hashes the given password and sets the password_hash."""
        if not password:
            self.password_hash = ""
            logger.warning(f"Tentativa de definir senha vazia para usuário {self.username}")
            return
        try:
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            self.password_hash = hashed.decode('utf-8')
        except Exception as e:
            logger.error(f"Error hashing password for user {self.username}: {e}")
            self.password_hash = "" # Reset em caso de erro

    def verify_password(self, password: str) -> bool:
        """Verifica a senha fornecida contra o hash armazenado."""
        if not self.password_hash or not password:
            logger.debug(f"Password verification failed for user {self.username}: Missing hash or provided password.")
            return False
        try:
            hash_bytes = self.password_hash.encode('utf-8')
            result = bcrypt.checkpw(password.encode('utf-8'), hash_bytes)
            # Descomente a linha abaixo para debug APENAS em ambiente de desenvolvimento seguro
            # logger.debug(f"Password verification result for user {self.username}: {result}")
            return result
        except ValueError as e:
             # Isso pode acontecer se o hash armazenado não for válido para bcrypt
             logger.error(f"Error verifying password for user {self.username}: {e}. Possible corrupted hash value: '{self.password_hash[:10]}...'")
             return False
        except Exception as e:
            logger.error(f"Unexpected error verifying password for user {self.username}: {e}")
            return False

    def update_last_login(self):
        """Define o timestamp last_login para a hora UTC atual."""
        self.last_login = datetime.now(timezone.utc)

    def to_dict(self, include_hash: bool = False) -> Dict[str, Any]:
        """
        Converte o objeto User para um dicionário.
        Args:
            include_hash: Se True, inclui o password_hash na saída. Padrão: False.
        Returns:
            Representação do usuário em dicionário.
        """
        # Acessa o objeto permissions carregado pelo relacionamento e chama seu to_dict()
        perm_dict = self.permissions.to_dict() if self.permissions else None

        data = {
            'id': self.id, 'username': self.username, 'name': self.name, 'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active,
            'permissions': perm_dict
        }
        if include_hash:
            data['password_hash'] = self.password_hash
        return data

    def __repr__(self):
        """Representação textual do objeto User."""
        # Usar getattr para segurança, caso permissions não esteja carregado
        perm_id = getattr(self.permissions, 'id', None)
        return f"<User(id={self.id}, username='{self.username}', perm_id={perm_id})>"
