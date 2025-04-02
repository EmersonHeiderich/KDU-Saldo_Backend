# Saldo API

API Flask para consulta de saldos de produtos e tecidos, custos, dados de clientes e contas a receber, integrando-se a um ERP TOTVS e utilizando PostgreSQL como banco de dados com SQLAlchemy ORM.

## Funcionalidades Principais

*   **Consulta de Saldo de Produtos:** Retorna o saldo de produtos acabados em formato de matriz (cor x tamanho), com diferentes modos de cálculo (base, vendas, produção).
*   **Consulta de Saldo de Tecidos:** Retorna uma lista de tecidos (matérias-primas) com saldo, custo e detalhes (largura, gramatura, encolhimento).
*   **Gerenciamento de Observações:** Permite adicionar, visualizar e resolver observações associadas a produtos (armazenadas no PostgreSQL).
*   **Painel do Cliente:** Busca dados cadastrais (PF/PJ) e estatísticas financeiras de clientes diretamente do ERP.
*   **Contas a Receber:** Permite buscar documentos de contas a receber com filtros avançados e gerar boletos em PDF via ERP.
*   **Módulo Fiscal:** Permite buscar notas fiscais (NF-e) com filtros e gerar DANFE em PDF via ERP.
*   **Gerenciamento de Usuários:** CRUD de usuários e suas permissões (armazenados no PostgreSQL, acesso restrito a administradores).
*   **Autenticação e Autorização:** Sistema de login baseado em token JWT com controle de acesso por permissões.

## Estrutura do Projeto

O projeto segue uma arquitetura em camadas para melhor organização e manutenibilidade:

```
saldo-api/
├── .env # Variáveis de ambiente (Credenciais DB, API, Chaves)
├── requirements.txt # Dependências Python
├── run.py # Ponto de entrada para execução
├── README.md # Este arquivo
│
└── src/
├── app.py # Fábrica da aplicação Flask (create_app)
├── config/ # Configurações (lê .env, define objeto Config)
├── domain/ # Modelos de dados (ORM para DB local, Dataclasses para ERP/DTOs)
├── database/ # Camada de acesso ao banco de dados (PostgreSQL com SQLAlchemy ORM)
├── services/ # Camada de lógica de negócio
├── erp_integration/ # Camada de integração com a API ERP TOTVS
├── api/ # Camada da API REST (Blueprints, rotas, decorators, errors)
└── utils/ # Utilitários (logger, builders, etc.)
```


Consulte os `README.md` dentro de cada diretório (`src/config`, `src/database`, etc.) para mais detalhes sobre sua responsabilidade.

## Setup e Instalação

1.  **Clone o Repositório:**
    ```bash
    git clone <url-do-repositorio>
    cd saldo-api
    ```

2.  **Pré-requisitos:**
    *   **Python:** 3.10 ou superior.
    *   **PostgreSQL:** Um servidor PostgreSQL instalado e acessível (localmente, Docker, ou na nuvem).
    *   **Cliente PostgreSQL (libpq):** Certifique-se de que as bibliotecas cliente do PostgreSQL (especificamente `libpq`) estejam instaladas e acessíveis no ambiente onde a API será executada (necessário para o driver `psycopg`). No Windows, isso geralmente envolve instalar o cliente PostgreSQL e adicionar seu diretório `bin` ao PATH do sistema.

3.  **Crie e Ative um Ambiente Virtual:**
    ```bash
    python -m venv venv
    # Linux/macOS:
    source venv/bin/activate
    # Windows:
    .\venv\Scripts\activate
    ```

4.  **Instale as Dependências:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configure o Banco de Dados PostgreSQL:**
    *   Conecte-se ao seu servidor PostgreSQL.
    *   Crie um banco de dados (ex: `connector_db`).
    *   Crie um usuário (ex: `saldo_api_user`) com uma senha segura. **Evite usar o usuário `postgres` em produção.**
    *   Conceda privilégios ao usuário no banco de dados criado:
        ```sql
        CREATE DATABASE connector_db;
        CREATE USER saldo_api_user WITH PASSWORD 'sua_senha_segura';
        GRANT ALL PRIVILEGES ON DATABASE connector_db TO saldo_api_user;
        -- Conecte-se ao novo banco (\c connector_db) se necessário e execute:
        -- GRANT ALL ON SCHEMA public TO saldo_api_user;
        ```
    *   **Configure o `pg_hba.conf`** no servidor PostgreSQL para permitir conexões do host onde a API Flask rodará, usando o usuário e banco de dados criados, e um método de autenticação seguro (ex: `scram-sha-256` ou `md5`). Recarregue a configuração do PostgreSQL após a edição (`SELECT pg_reload_conf();` ou `systemctl reload postgresql`).

6.  **Configure as Variáveis de Ambiente:**
    *   Copie `.env.example` (se existir) para `.env` ou crie um novo arquivo `.env`.
    *   Preencha as variáveis no arquivo `.env`:
        *   `SECRET_KEY`: **OBRIGATÓRIO.** Chave secreta segura e única para JWT.
        *   `DB_TYPE=POSTGRES`
        *   `POSTGRES_HOST`: Endereço do servidor PostgreSQL.
        *   `POSTGRES_PORT`: Porta do servidor PostgreSQL (padrão `5432`).
        *   `POSTGRES_USER`: Usuário do banco de dados criado.
        *   `POSTGRES_PASSWORD`: Senha do usuário do banco.
        *   `POSTGRES_DB`: Nome do banco de dados criado.
        *   `API_BASE_URL`, `API_USERNAME`, `API_PASSWORD`, `CLIENT_ID`, `CLIENT_SECRET`, `COMPANY_CODE`: Credenciais e configurações da API TOTVS.
        *   `APP_HOST`, `APP_PORT`, `APP_DEBUG`, `LOG_LEVEL`: Configurações da aplicação Flask.
        *   `DEFAULT_ADMIN_PASSWORD` (Opcional): Define a senha inicial para o usuário `admin` criado automaticamente. Se omitido, deriva da `SECRET_KEY`.

7.  **Execute a Aplicação:**
    ```bash
    python run.py
    ```
    A API Flask iniciará. Na primeira execução, o `SchemaManager` criará as tabelas baseadas nos modelos ORM (`User`, `Observation`, `UserPermissions`) no banco PostgreSQL e o usuário `admin` padrão. Verifique os logs para confirmar a criação bem-sucedida.
    A API estará disponível em `http://<APP_HOST>:<APP_PORT>`.

## Padrões de Desenvolvimento

*   **Nomenclatura:** `snake_case` para variáveis/funções, `PascalCase` para classes, `UPPER_SNAKE_CASE` para constantes.
*   **Estrutura:** Arquitetura em camadas (API, Services, ERP Integration, Database, Domain).
*   **Banco de Dados:** PostgreSQL.
*   **ORM/DB Layer:** **SQLAlchemy ORM** para interação com o banco de dados local.
*   **Tipagem:** Uso extensivo de type hints.
*   **Modelos:** Uso de **classes ORM (herdando de `Base`)** para representar tabelas do banco local e **`dataclasses`** para representar estruturas de dados do ERP ou DTOs específicos.
*   **Logs:** Logs detalhados usando o módulo `logging` e `ConcurrentRotatingFileHandler`.
*   **Error Handling:** Exceções customizadas e tratamento robusto de erros.
*   **Documentação:** Docstrings, READMEs nos diretórios chave.
*   **Variáveis de Ambiente:** Configurações gerenciadas via `.env`.

## Desenvolvimento Futuro

*   Implementar caching para respostas da API ERP.
*   Adicionar testes unitários e de integração.
*   **Implementar Alembic** para gerenciar migrações de schema do banco de dados ORM.
*   Melhorar a configuração de CORS para produção.
*   Expandir funcionalidades (Detalhes NF, Link PIX, etc.).
*   Armazenar dados do ERP no PostgreSQL para relatórios/análises futuras.