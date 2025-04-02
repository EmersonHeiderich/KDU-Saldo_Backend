import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# --- Adicionar Raiz do Projeto ao sys.path ---
# Garante que o Alembic possa encontrar os módulos da sua aplicação
# Ajuste para adicionar o diretório PAI do diretório 'alembic', que é a raiz do projeto.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT) # Adiciona a raiz do projeto
# --------------------------------------------

# --- Importar configurações e Base dos modelos ---
try:
    # As importações agora devem funcionar, pois 'src' está dentro de PROJECT_ROOT
    from src.config import config as app_config
    from src.database.base import Base
    # Importar todos os modelos ORM para que o Alembic os reconheça
    import src.domain # Garante que __init__.py de domain importe os modelos
except ImportError as e:
    print(f"Erro ao importar módulos da aplicação: {e}")
    print("Certifique-se de que está executando o alembic a partir do diretório raiz do projeto")
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"sys.path: {sys.path}")
    sys.exit(1)
# ----------------------------------------------

# este é o objeto MetaData do Alembic para suporte a 'autogenerate'
# --- Definir target_metadata a partir do Base importado ---
target_metadata = Base.metadata
# -------------------------------------------------------

# outras configurações do arquivo .ini, se houver:
config = context.config

# --- Configurar a URL do banco dinamicamente ---
db_url = app_config.SQLALCHEMY_DATABASE_URI
if not db_url:
    print("Erro: SQLALCHEMY_DATABASE_URI não está configurado na aplicação.")
    sys.exit(1)
config.set_main_option('sqlalchemy.url', db_url)
# ---------------------------------------------

# Interpreta o arquivo de configuração para logging do Python.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Demais configurações e funções run_migrations_offline/online permanecem iguais...

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        # Usar a convenção de nomenclatura definida em Base
        naming_convention=target_metadata.naming_convention,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # Usar a convenção de nomenclatura definida em Base
            naming_convention=target_metadata.naming_convention,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()