# src/domain/user.py
# Define os modelos ORM para User e UserPermissions usando SQLAlchemy.

from datetime import datetime, timezone
import bcrypt
from typing import Optional, Dict, Any, TYPE_CHECKING # Import TYPE_CHECKING
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, func, Text
)
from sqlalchemy.orm import relationship, Mapped, mapped_column # ORM imports
from sqlalchemy.dialects.postgresql import TIMESTAMP # Especificar timezone para PG

# Importar Base do novo arquivo
from src.database.base import Base
from src.utils.logger import logger

# Use TYPE_CHECKING para evitar importações circulares em tempo de execução
# se User precisasse importar algo que importa UserPermissions
if TYPE_CHECKING:
    pass # Não há necessidade imediata aqui, mas é bom padrão

# UserPermissions agora é um modelo ORM
class UserPermissions(Base):
    """
    Representa as permissões ORM associadas a um usuário.
    """
    __tablename__ = 'user_permissions'

    # Colunas da tabela mapeadas para atributos
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Chave estrangeira para a tabela 'users'
    # cascade="all, delete-orphan" significa que ao deletar um User,
    # a permissão associada também será deletada.
    # unique=True garante a relação um-para-um do lado do User.
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_access_products: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_access_fabrics: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_access_customer_panel: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_access_fiscal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_access_accounts_receivable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False) # <<<--- ADDED

    # Relacionamento de volta para User (opcional, mas útil)
    # 'user' será o atributo para acessar o objeto User a partir de UserPermissions
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

    # @classmethod from_dict não é estritamente necessário para ORM,
    # mas pode ser útil para criar instâncias a partir de dados de API externa, etc.
    # Para criação a partir de dados do DB, o SQLAlchemy faz automaticamente.

    def __repr__(self):
        return f"<UserPermissions(id={self.id}, user_id={self.user_id}, is_admin={self.is_admin})>"

# User agora é um modelo ORM
class User(Base):
    """
    Representa um usuário da aplicação como modelo ORM.
    """
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Usar Text para username/email pode ser mais flexível que String com tamanho fixo
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(Text, unique=True, index=True) # Opcional, mas único
    # Usar TIMESTAMP(timezone=True) para PostgreSQL
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relacionamento um-para-um com UserPermissions
    # 'permissions' será o atributo para acessar o objeto UserPermissions a partir de User
    # cascade="all, delete-orphan": Se um User for deletado, suas permissões são deletadas.
    # uselist=False: Indica que é um relacionamento um-para-um (ou muitos-para-um do lado 'um').
    permissions: Mapped["UserPermissions"] = relationship(
        "UserPermissions",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False, # Importante para um-para-um
        lazy="joined" # Carrega permissões junto com o usuário (bom para poucos dados)
                      # Alternativas: 'select' (query separada), 'subquery', 'raise'
    )

    # --- Métodos de Lógica (permanecem os mesmos) ---
    def set_password(self, password: str):
        """Hashes the given password and sets the password_hash."""
        if not password:
            self.password_hash = "" # Ou None? Precisa ser not null no DB. Usar string vazia? Ou lançar erro?
                                    # Vamos usar string vazia por enquanto, mas validar antes de salvar.
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
        """Verifies the given password against the stored hash."""
        if not self.password_hash or not password:
            logger.debug(f"Password verification failed for user {self.username}: Missing hash or provided password.")
            return False
        try:
            # Garantir que o hash seja codificado para bytes
            hash_bytes = self.password_hash.encode('utf-8')
            result = bcrypt.checkpw(password.encode('utf-8'), hash_bytes)
            logger.debug(f"Password verification result for user {self.username}: {result}")
            return result
        except ValueError as e:
             # Isso pode acontecer se o hash armazenado não for válido para bcrypt
             logger.error(f"Error verifying password for user {self.username}: {e}. Possible corrupted hash value: '{self.password_hash[:10]}...'")
             return False
        except Exception as e:
            logger.error(f"Unexpected error verifying password for user {self.username}: {e}")
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
            # Acessa o objeto permissions e chama seu to_dict()
            'permissions': self.permissions.to_dict() if self.permissions else None
        }
        if include_hash:
            data['password_hash'] = self.password_hash # O atributo já existe, apenas incluímos no dict
        return data

    # @classmethod from_dict não é estritamente necessário para ORM,
    # pois o SQLAlchemy cuida do mapeamento DB -> Objeto.
    # Pode ser útil para criar/atualizar a partir de dados de API.

    def __repr__(self):
        # Usar getattr para segurança, caso permissions não esteja carregado
        perm_id = getattr(self.permissions, 'id', None)
        return f"<User(id={self.id}, username='{self.username}', perm_id={perm_id})>"