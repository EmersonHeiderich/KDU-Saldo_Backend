# src/config

Este diretório contém a configuração da aplicação.

## Arquivos

*   **`settings.py`**:
    *   Carrega variáveis de ambiente do arquivo `.env` na raiz do projeto usando `python-dotenv`.
    *   Define a classe `Config` (um `dataclass`) que agrupa todas as configurações da aplicação.
    *   Fornece valores padrão para as configurações caso não sejam definidas no ambiente.
    *   Exporta uma instância singleton `config` da classe `Config`, que pode ser importada em outros módulos.
    *   Realiza validações básicas (ex: nível de log) e garante que o diretório do banco de dados exista.
*   **`README.md`**: Este arquivo.

## Uso

Importe a instância `config` de `src.config` para acessar as configurações em qualquer lugar da aplicação:

```python
from src.config import config

api_url = config.API_BASE_URL
debug_mode = config.APP_DEBUG
```