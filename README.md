# Saldo API

API Flask para consulta de saldos de produtos e tecidos, custos, dados de clientes e contas a receber, integrando-se a um ERP TOTVS e utilizando PostgreSQL como banco de dados com SQLAlchemy ORM e Alembic para migrações.

## Funcionalidades Principais

*   **Consulta de Saldo de Produtos:** Retorna o saldo de produtos acabados em formato de matriz (cor x tamanho), com diferentes modos de cálculo (base, vendas, produção).
*   **Consulta de Saldo de Tecidos:** Retorna uma lista de tecidos (matérias-primas) com saldo, custo e detalhes (largura, gramatura, encolhimento).
*   **Gerenciamento de Observações:** Permite adicionar, visualizar e resolver observações associadas a produtos (armazenadas no PostgreSQL).
*   **Painel do Cliente:** Busca dados cadastrais (PF/PJ) e estatísticas financeiras de clientes diretamente do ERP.
*   **Contas a Receber:** Permite buscar documentos de contas a receber com filtros avançados e gerar boletos em PDF via ERP.
*   **Módulo Fiscal:** Permite buscar notas fiscais (NF-e) com filtros e gerar DANFE em PDF via ERP.
*   **Gerenciamento de Usuários:** CRUD de usuários e suas permissões (armazenadas no PostgreSQL, acesso restrito a administradores).
*   **Autenticação e Autorização:** Sistema de login baseado em token JWT com controle de acesso por permissões.
*   **Migrações de Banco de Dados:** Gerenciamento do schema do banco de dados PostgreSQL usando Alembic.

## Estrutura do Projeto

O projeto segue uma arquitetura em camadas para melhor organização e manutenibilidade:

```
saldo-api/
├── .env # Variáveis de ambiente (Credenciais DB, API, Chaves)
├── requirements.txt # Dependências Python
├── run.py # Ponto de entrada para execução
├── alembic.ini # Configuração do Alembic
├── alembic/ # Diretório de migrações do Alembic
│ ├── env.py # Script de ambiente do Alembic
│ ├── script.py.mako # Template de migração
│ └── versions/ # Arquivos de scripts de migração
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
    *   **PostgreSQL:** Um servidor PostgreSQL instalado e acessível.
    *   **Cliente PostgreSQL (libpq):** Bibliotecas cliente do PostgreSQL instaladas e acessíveis.
    *   **Git:** Sistema de controle de versão.

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

5.  **Configure o Banco de Dados PostgreSQL:** (Instruções permanecem as mesmas)
    *   Crie um banco de dados (ex: `connector_db`).
    *   Crie um usuário (ex: `saldo_api_user`) com senha segura.
    *   Conceda privilégios ao usuário no banco.
    *   Configure o `pg_hba.conf` para permitir conexões.

6.  **Configure as Variáveis de Ambiente (`.env`):** (Instruções permanecem as mesmas)
    *   Copie `.env.example` para `.env` (se existir) ou crie um novo.
    *   Preencha `SECRET_KEY`, `DB_TYPE=POSTGRES`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, credenciais da API TOTVS, e configurações da app Flask.

7.  **Aplique as Migrações do Banco de Dados:**
    *   Com as variáveis de ambiente configuradas e o banco acessível, aplique as migrações do Alembic para criar/atualizar o schema:
    ```bash
    alembic upgrade head
    ```
    *   Na primeira execução, isso criará todas as tabelas (`users`, `user_permissions`, `product_observations`, `alembic_version`). A função `initialize_schema` em `src/app.py` também garantirá a criação do usuário `admin` padrão se ele não existir.

8.  **Execute a Aplicação:**
    ```bash
    python run.py
    ```
    A API Flask iniciará e estará disponível em `http://<APP_HOST>:<APP_PORT>`.

## Fluxo de Trabalho de Migração (Alembic)

Sempre que você modificar os modelos ORM em `src/domain/` (adicionar/remover/alterar tabelas ou colunas):

1.  **Gere uma Nova Migração Automática:**
    ```bash
    alembic revision --autogenerate -m "Descreva a mudança aqui"
    ```

2.  **Revise o Script Gerado:** Verifique o arquivo Python criado em `alembic/versions/`. Ajuste se necessário (o autogenerate pode precisar de retoques em casos complexos).

3.  **Aplique a Migração ao Banco:**
    ```bash
    alembic upgrade head
    ```

4.  **Commite** o novo script de migração junto com as alterações nos modelos.

Para reverter a última migração (use com cuidado):
```bash
alembic downgrade -1
```
Para ver o histórico de migrações e o estado atual:
```bash
alembic history
alembic current
```

## Padrões de Desenvolvimento

*   **Nomenclatura:** `snake_case` para variáveis/funções, `PascalCase` para classes, `UPPER_SNAKE_CASE` para constantes.
*   **Estrutura:** Arquitetura em camadas (API, Services, ERP Integration, Database, Domain).
*   **Banco de Dados:** PostgreSQL.
*   **ORM/DB Layer:** **SQLAlchemy ORM** para interação com o banco de dados local.
*   **Migrações:** Alembic para gerenciamento do schema do banco de dados.
*   **Tipagem:** Uso extensivo de type hints.
*   **Modelos:** Uso de **classes ORM (herdando de `Base`)** para representar tabelas do banco local e **`dataclasses`** para representar estruturas de dados do ERP ou DTOs específicos.
*   **Logs:** Logs detalhados usando o módulo `logging` e `ConcurrentRotatingFileHandler`.
*   **Error Handling:** Exceções customizadas e tratamento robusto de erros.
*   **Documentação:** Docstrings, READMEs nos diretórios chave.
*   **Variáveis de Ambiente:** Configurações gerenciadas via `.env`.

## Desenvolvimento Futuro

*   Implementar caching para respostas da API ERP.
*   Adicionar testes unitários e de integração.
*   Melhorar a configuração de CORS para produção.
*   Expandir funcionalidades (Detalhes NF, Link PIX, etc.).
*   Armazenar dados do ERP no PostgreSQL para relatórios/análises futuras.