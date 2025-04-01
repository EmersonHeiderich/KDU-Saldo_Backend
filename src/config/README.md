# src/config

Este diretório contém a configuração da aplicação.

## Arquivos

*   **`settings.py`**:
    *   Carrega variáveis de ambiente do arquivo `.env` na raiz do projeto usando `python-dotenv`.
    *   Define a classe `Config` (um `dataclass`) que agrupa todas as configurações da aplicação (Flask, API ERP, Banco de Dados).
    *   Lê as variáveis de conexão do PostgreSQL (`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`).
    *   Constrói a `SQLALCHEMY_DATABASE_URI` usada pelo SQLAlchemy para conectar ao banco.
    *   Fornece valores padrão para configurações caso não sejam definidas no ambiente.
    *   Exporta uma instância singleton `config` da classe `Config`, que pode ser importada em outros módulos.
    *   Realiza validações básicas (ex: nível de log).
*   **`README.md`**: Este arquivo.

## Uso

Importe a instância `config` de `src.config` para acessar as configurações em qualquer lugar da aplicação:

```python
from src.config import config

api_url = config.API_BASE_URL
debug_mode = config.APP_DEBUG
db_uri = config.SQLALCHEMY_DATABASE_URI # URI para SQLAlchemy