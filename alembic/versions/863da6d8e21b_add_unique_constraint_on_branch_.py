# alembic/versions/863da6d8e21b_add_unique_constraint_on_branch_.py
"""Add unique constraint on branch, sequence, date for nota_fiscal

Revision ID: 863da6d8e21b
Revises: 72333f760af5 # ID da migração anterior (a que alterou ncm)
Create Date: 2025-04-03 14:36:59.832089 # Data de criação original

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# Removido import não utilizado
# from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '863da6d8e21b'
down_revision: Union[str, None] = '72333f760af5' # Aponta para a migração que alterou ncm
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Comando CORRIGIDO para ADICIONAR a constraint UNIQUE ###
    # Adicionar a constraint unique composta na tabela nota_fiscal
    op.create_unique_constraint(
        'uq_nota_fiscal_branch_sequence_date', # Nome sugerido para a constraint
        'nota_fiscal',                         # Nome da tabela
        ['branch_code', 'invoice_sequence', 'invoice_date'] # Colunas na constraint
    )
    # ### Fim do Comando CORRIGIDO ###


def downgrade() -> None:
    # ### Comando CORRIGIDO para REMOVER a constraint UNIQUE ###
    # Remover a constraint unique ao reverter
    op.drop_constraint(
        'uq_nota_fiscal_branch_sequence_date', # Nome da constraint a ser removida
        'nota_fiscal',                         # Nome da tabela
        type_='unique'                         # Tipo da constraint
    )
    # ### Fim do Comando CORRIGIDO ###