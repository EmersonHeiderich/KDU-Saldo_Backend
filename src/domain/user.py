# src/domain/user.py
from datetime import datetime, timezone
import bcrypt
from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, func, Text
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import TIMESTAMP

from src.database.base import Base
from src.utils.logger import logger

if TYPE_CHECKING:
    pass

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

    user: Mapped["User"] = relationship(back_populates="permissions")

    def to_dict(self) -> Dict[str, Any]:
        """Converte o objeto UserPermissions para um dicionário."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'is_admin': self.is_admin,
            'can_access_products': self.can_access_products,
            'can_access_fabrics': self.can_access_fabrics,
            'can_access_customer_panel': self.can_access_customer_panel,
            'can_access_fiscal': self.can_access_fiscal,
            'can_access_accounts_receivable': self.can_access_accounts_receivable,
        }

    def __repr__(self):
        return f"<UserPermissions(id={self.id}, user_id={self.user_id}, is_admin={self.is_admin})>"

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

    permissions: Mapped["UserPermissions"] = relationship(
        "UserPermissions",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="joined"
    )

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
            logger.error(f"Erro ao fazer hash da senha para usuário {self.username}: {e}")
            self.password_hash = ""

    def verify_password(self, password: str) -> bool:
        """Verifies the given password against the stored hash."""
        if not self.password_hash or not password:
            logger.debug(f"Verificação de senha falhou para usuário {self.username}: Hash ou senha fornecida ausente.")
            return False
        try:
            hash_bytes = self.password_hash.encode('utf-8')
            result = bcrypt.checkpw(password.encode('utf-8'), hash_bytes)
            logger.debug(f"Resultado da verificação de senha para usuário {self.username}: {result}")
            return result
        except ValueError as e:
             logger.error(f"Erro ao verificar senha para usuário {self.username}: {e}. Possível valor de hash corrompido: '{self.password_hash[:10]}...'")
             return False
        except Exception as e:
            logger.error(f"Erro inesperado ao verificar senha para usuário {self.username}: {e}")
            return False

    def update_last_login(self):
        """Sets the last_login timestamp to the current time UTC."""
        self.last_login = datetime.now(timezone.utc)

    def to_dict(self, include_hash: bool = False) -> Dict[str, Any]:
        """
        Converts the User object to a dictionary.
        Args:
            include_hash: Whether to include the password_hash in the output. Defaults to False.
        Returns:
            Dictionary representation of the user.
        """
        data = {
            'id': self.id,
            'username': self.username,
            'name': self.name,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active,
            'permissions': self.permissions.to_dict() if self.permissions else None
        }
        if include_hash:
            data['password_hash'] = self.password_hash
        return data

    def __repr__(self):
        perm_id = getattr(self.permissions, 'id', None)
        return f"<User(id={self.id}, username='{self.username}', perm_id={perm_id})>"