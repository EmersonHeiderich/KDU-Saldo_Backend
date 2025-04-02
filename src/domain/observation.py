# src/domain/observation.py
# Define o modelo ORM para Product Observations usando SQLAlchemy.

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, func # Import func if using database default timestamps
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import TIMESTAMP # Importar tipo específico do PG

# Importar Base
from src.database.base import Base
from src.utils.logger import logger

class Observation(Base):
    """
    Representa uma observação de produto como modelo ORM.
    """
    __tablename__ = 'product_observations'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Usar Text para códigos/textos potencialmente longos
    reference_code: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    observation_text: Mapped[str] = mapped_column("observation", Text, nullable=False) # Mapeia para coluna 'observation' existente
    # Coluna "user" precisa de aspas se for palavra reservada, mas SQLAlchemy pode lidar com isso.
    # Se o nome do atributo no Python for diferente, use mapped_column("user", ...)
    user: Mapped[str] = mapped_column(Text, nullable=False)
    # Usar TIMESTAMP(timezone=True) para PostgreSQL, com default via Python/SQLAlchemy
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    resolved_user: Mapped[Optional[str]] = mapped_column(Text)
    resolved_timestamp: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    def to_dict(self) -> Dict[str, Any]:
        """Converte o objeto Observation para um dicionário."""
        return {
            'id': self.id,
            'reference_code': self.reference_code,
            # Retorna o nome do atributo python 'observation_text'
            'observation_text': self.observation_text,
            'user': self.user,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'resolved': self.resolved,
            'resolved_user': self.resolved_user,
            'resolved_timestamp': self.resolved_timestamp.isoformat() if self.resolved_timestamp else None,
        }

    # @classmethod from_dict não é necessário para ORM, o SQLAlchemy cuida disso.

    def __repr__(self):
        return f"<Observation(id={self.id}, ref='{self.reference_code}', resolved={self.resolved})>"