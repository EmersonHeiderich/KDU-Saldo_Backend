# alembic/versions/29ece17d793b_increase_size_of_freight_type_columns_.py
"""Increase size of freight_type columns in nota_fiscal

Revision ID: 29ece17d793b
Revises: 75de064288e5 # ID da migração anterior que criou as tabelas fiscais
Create Date: 2025-04-03 13:34:08.282181 # Data de criação original

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# sqlalchemy.dialects não é estritamente necessário para VARCHAR, mas não prejudica
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '29ece17d793b'
down_revision: Union[str, None] = '75de064288e5' # Aponta para a migração anterior
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Comandos CORRIGIDOS para ALTERAR as colunas ###
    # Alterar apenas o tipo/tamanho das colunas necessárias na tabela nota_fiscal
    op.alter_column('nota_fiscal', 'freight_type',
           existing_type=sa.VARCHAR(length=10), # Informa o tipo existente no DB
           type_=sa.VARCHAR(length=50),      # Define o novo tipo/tamanho
           existing_nullable=True)           # Mantém a nulidade existente

    op.alter_column('nota_fiscal', 'freight_type_redispatch',
           existing_type=sa.VARCHAR(length=20), # Informa o tipo existente no DB
           type_=sa.VARCHAR(length=50),      # Define o novo tipo/tamanho
           existing_nullable=True)           # Mantém a nulidade existente
    # ### Fim dos Comandos CORRIGIDOS ###


def downgrade() -> None:
    # ### Comandos CORRIGIDOS para REVERTER a alteração ###
    # Reverter para os tipos/tamanhos originais
    op.alter_column('nota_fiscal', 'freight_type_redispatch',
           existing_type=sa.VARCHAR(length=50), # Informa o tipo atual (VARCHAR 50)
           type_=sa.VARCHAR(length=20),      # Define o tipo antigo (VARCHAR 20)
           existing_nullable=True)

    op.alter_column('nota_fiscal', 'freight_type',
           existing_type=sa.VARCHAR(length=50), # Informa o tipo atual (VARCHAR 50)
           type_=sa.VARCHAR(length=10),      # Define o tipo antigo (VARCHAR 10)
           existing_nullable=True)
    # ### Fim dos Comandos CORRIGIDOS ###