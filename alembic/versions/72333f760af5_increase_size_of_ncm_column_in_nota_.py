# alembic/versions/72333f760af5_increase_size_of_ncm_column_in_nota_.py
"""Increase size of ncm column in nota_fiscal_item

Revision ID: 72333f760af5
Revises: 29ece17d793b # ID da migração anterior (a que alterou freight_type)
Create Date: 2025-04-03 13:47:41.300907 # Data de criação original

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# Removido import não utilizado de postgresql, mas pode manter se preferir
# from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '72333f760af5'
down_revision: Union[str, None] = '29ece17d793b' # Aponta para a migração que alterou freight_type
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Comandos CORRIGIDOS para ALTERAR a coluna ncm ###
    op.alter_column('nota_fiscal_item', 'ncm',
           existing_type=sa.VARCHAR(length=8),  # Informa o tipo existente no DB
           type_=sa.VARCHAR(length=12),     # Define o novo tipo/tamanho
           existing_nullable=True)          # Mantém a nulidade existente
    # ### Fim dos Comandos CORRIGIDOS ###


def downgrade() -> None:
    # ### Comandos CORRIGIDOS para REVERTER a alteração ###
    op.alter_column('nota_fiscal_item', 'ncm',
           existing_type=sa.VARCHAR(length=12), # Informa o tipo atual (VARCHAR 12)
           type_=sa.VARCHAR(length=8),       # Define o tipo antigo (VARCHAR 8)
           existing_nullable=True)
    # ### Fim dos Comandos CORRIGIDOS ###