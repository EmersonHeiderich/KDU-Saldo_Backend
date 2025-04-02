# src/database/base.py
# Define a base declarativa para os modelos SQLAlchemy ORM.

from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData

# Convenção de nomenclatura para constraints (opcional, mas recomendado)
# Garante nomes consistentes para chaves primárias, estrangeiras, índices, etc.
# Evita problemas com nomes muito longos ou colisões em alguns SGBDs.
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

# Cria uma instância de MetaData com a convenção de nomenclatura
# O schema pode ser definido aqui se você usar schemas no PostgreSQL (ex: metadata=MetaData(schema="meu_schema"))
metadata = MetaData(naming_convention=convention)

# Cria a Base declarativa usando a metadata configurada
Base = declarative_base(metadata=metadata)

# Você pode adicionar aqui classes base customizadas com colunas comuns (id, created_at, etc.)
# se desejar, mas por enquanto manteremos simples.
# Exemplo:
# class BaseTimestampedModel(Base):
#     __abstract__ = True # Não cria tabela para esta classe
#     created_at: Mapped[datetime] = mapped_column(default=func.now())
#     updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())