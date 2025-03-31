# src/domain/user.py
# Defines the data models for User and UserPermissions.

from datetime import datetime
import bcrypt
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from src.utils.logger import logger

@dataclass
class UserPermissions:
    """
    Represents the permissions associated with a user. Mutable.
    """
    id: Optional[int] = None
    user_id: Optional[int] = None # Link back to the user
    is_admin: bool = False
    can_access_products: bool = False
    can_access_fabrics: bool = False
    can_access_customer_panel: bool = False
    can_access_fiscal: bool = False
    can_access_accounts_receivable: bool = False # <<<--- ADDED

    def to_dict(self) -> Dict[str, Any]:
        """Converts the UserPermissions object to a dictionary."""
        # Use vars() for dataclasses, handles Optional fields correctly
        return vars(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional['UserPermissions']:
        """Creates UserPermissions from a dictionary (e.g., from DB)."""
        if not data:
            return None
        if not isinstance(data, dict):
             logger.warning(f"Invalid data type for UserPermissions.from_dict: {type(data)}")
             return None

        return cls(
            id=data.get('id'),
            user_id=data.get('user_id'),
            is_admin=bool(data.get('is_admin', False)),
            can_access_products=bool(data.get('can_access_products', False)),
            can_access_fabrics=bool(data.get('can_access_fabrics', False)),
            can_access_customer_panel=bool(data.get('can_access_customer_panel', False)),
            can_access_fiscal=bool(data.get('can_access_fiscal', False)),
            can_access_accounts_receivable=bool(data.get('can_access_accounts_receivable', False)) # <<<--- ADDED

        )

@dataclass
class User:
    """
    Represents an application user. Mutable.
    """
    id: Optional[int] = None
    username: Optional[str] = None
    password_hash: Optional[str] = None # Store hash, not password
    name: Optional[str] = None
    email: Optional[str] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    is_active: bool = True
    permissions: Optional[UserPermissions] = None # Nested permissions object

    def set_password(self, password: str):
        """Hashes the given password and sets the password_hash."""
        if not password:
            self.password_hash = None
            return
        try:
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            self.password_hash = hashed.decode('utf-8')
        except Exception as e:
            logger.error(f"Error hashing password for user {self.username}: {e}")
            self.password_hash = None

    def verify_password(self, password: str) -> bool:
        """Verifies the given password against the stored hash."""
        if not self.password_hash or not password:
            logger.debug(f"Password verification failed for user {self.username}: Missing hash or provided password.")
            return False
        try:
            result = bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
            logger.debug(f"Password verification result for user {self.username}: {result}")
            return result
        except ValueError as e:
             logger.error(f"Error verifying password for user {self.username}: {e}. Possible corrupted hash.")
             return False
        except Exception as e:
            logger.error(f"Unexpected error verifying password for user {self.username}: {e}")
            return False

    def update_last_login(self):
        """Sets the last_login timestamp to the current time."""
        self.last_login = datetime.now()

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
            # Ensure datetime objects are converted safely
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            'last_login': self.last_login.isoformat() if isinstance(self.last_login, datetime) else None,
            'is_active': self.is_active,
            'permissions': self.permissions.to_dict() if self.permissions else None
        }
        if include_hash:
            data['password_hash'] = self.password_hash
        return data

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional['User']:
        """Creates a User object from a dictionary (e.g., from DB)."""
        if not data:
            return None
        if not isinstance(data, dict):
             logger.warning(f"Invalid data type for User.from_dict: {type(data)}")
             return None

        # Convert ISO timestamp strings back to datetime objects safely
        created_at_val = data.get('created_at')
        created_at = None
        if isinstance(created_at_val, str):
            try: created_at = datetime.fromisoformat(created_at_val.replace('Z', '+00:00')) # Handle Z suffix
            except (ValueError, TypeError): logger.warning(f"Invalid format for created_at: {created_at_val}.")
        elif isinstance(created_at_val, datetime):
            created_at = created_at_val # Already datetime
        if created_at is None: created_at = datetime.now() # Default if missing/invalid


        last_login_val = data.get('last_login')
        last_login = None
        if isinstance(last_login_val, str):
             try: last_login = datetime.fromisoformat(last_login_val.replace('Z', '+00:00'))
             except (ValueError, TypeError): logger.warning(f"Invalid format for last_login: {last_login_val}.")
        elif isinstance(last_login_val, datetime):
             last_login = last_login_val

        # Create UserPermissions from nested dict
        permissions = UserPermissions.from_dict(data.get('permissions'))

        try:
            user = cls(
                id=data.get('id'),
                username=data.get('username'),
                name=data.get('name'),
                email=data.get('email'),
                created_at=created_at,
                last_login=last_login,
                is_active=bool(data.get('is_active', True)), # Ensure boolean
                permissions=permissions,
                password_hash=data.get('password_hash')
            )
            # Link user_id in permissions if it wasn't set and user has id
            if user.id and user.permissions and user.permissions.user_id is None:
                 user.permissions.user_id = user.id

            return user
        except Exception as e:
            logger.error(f"Error creating User from dict: {e}. Data: {data}")
            return None

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', is_active={self.is_active})>"