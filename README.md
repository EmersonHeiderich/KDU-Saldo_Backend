
# Saldo API

API Flask para consulta de saldos de produtos e tecidos, custos, dados de clientes e contas a receber, integrando-se a um ERP TOTVS.

## Funcionalidades Principais

*   **Consulta de Saldo de Produtos:** Retorna o saldo de produtos acabados em formato de matriz (cor x tamanho), com diferentes modos de cálculo (base, vendas, produção).
*   **Consulta de Saldo de Tecidos:** Retorna uma lista de tecidos (matérias-primas) com saldo, custo e detalhes (largura, gramatura, encolhimento).
*   **Gerenciamento de Observações:** Permite adicionar, visualizar e resolver observações associadas a produtos.
*   **Painel do Cliente:** Busca dados cadastrais (PF/PJ) e estatísticas financeiras de clientes.
*   **Contas a Receber:** Permite buscar documentos de contas a receber com filtros avançados e gerar boletos em PDF.
*   **Gerenciamento de Usuários:** CRUD de usuários e suas permissões (acesso restrito a administradores).
*   **Autenticação e Autorização:** Sistema de login baseado em token JWT com controle de acesso por permissões.

## Estrutura do Projeto

O projeto segue uma arquitetura em camadas para melhor organização e manutenibilidade:

```
saldo-api/
├── .env # Variáveis de ambiente
├── requirements.txt
├── run.py # Ponto de entrada para execução
├── README.md # Este arquivo
│
└── src/
├── app.py # Fábrica da aplicação Flask (create_app)
├── config/ # Configurações (settings.py)
├── domain/ # Modelos de dados (dataclasses)
│ ├── accounts_receivable.py #
│ └── ... (outros modelos)
├── database/ # Camada de acesso ao banco de dados (SQLite)
├── services/ # Camada de lógica de negócio
│ ├── accounts_receivable_service.py #
│ └── ... (outros serviços)
├── erp_integration/ # Camada de integração com o ERP TOTVS
│ ├── erp_accounts_receivable_service.py #
│ └── ... (outros serviços ERP)
├── api/ # Camada da API (Blueprints, rotas, decorators, errors)
│ ├── routes/
│ │ ├── accounts_receivable.py #
│ │ └── ... (outras rotas)
│ └── ... (decorators, errors, etc.)
└── utils/ # Utilitários (logger, builders)
├── pdf_utils.py #
└── ... (outros utils)
```

Consulte os `README.md` dentro de cada diretório para mais detalhes sobre sua responsabilidade.

## Setup e Instalação

1.  **Clone o Repositório:**
    ```bash
    git clone <url-do-repositorio>
    cd saldo-api
    ```

2.  **Crie um Ambiente Virtual:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    # ou
    venv\Scripts\activate    # Windows
    ```

3.  **Instale as Dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure as Variáveis de Ambiente:**
    *   Copie o arquivo `.env.example` (se existir) para `.env`.
    *   Preencha as variáveis no arquivo `.env` com os valores corretos para seu ambiente:
        *   `SECRET_KEY`: Chave secreta para assinar tokens JWT (gere uma chave segura).
        *   `DATABASE_PATH`: Caminho para o arquivo do banco de dados SQLite (ex: `database/app.db`).
        *   `API_BASE_URL`: URL base da API TOTVS.
        *   `API_USERNAME`: Usuário para autenticação na API TOTVS.
        *   `API_PASSWORD`: Senha para autenticação na API TOTVS.
        *   `CLIENT_ID`: Client ID para autenticação OAuth na API TOTVS.
        *   `CLIENT_SECRET`: Client Secret para autenticação OAuth na API TOTVS.
        *   `COMPANY_CODE`: Código da empresa padrão no TOTVS.
        *   `APP_HOST`: Host onde a API Flask será executada (padrão `0.0.0.0`).
        *   `APP_PORT`: Porta onde a API Flask será executada (padrão `5004`).
        *   `APP_DEBUG`: Habilita/desabilita modo debug (padrão `True`).
        *   `LOG_LEVEL`: Nível de log (padrão `DEBUG`).

5.  **Execute a Aplicação:**
    ```bash
    python run.py
    ```
    A API estará disponível em `http://<APP_HOST>:<APP_PORT>`.

## Padrões de Desenvolvimento

*   **Nomenclatura:**
    *   Variáveis e funções: `snake_case`.
    *   Classes: `PascalCase`.
    *   Constantes: `UPPER_SNAKE_CASE`.
*   **Estrutura:** Arquitetura em camadas (API, Services, ERP Integration, Database, Domain).
*   **Tipagem:** Uso extensivo de type hints.
*   **Modelos:** Uso de `dataclasses` para representar estruturas de dados.
*   **Logs:** Logs detalhados em níveis apropriados (DEBUG, INFO, WARNING, ERROR, CRITICAL).
*   **Error Handling:** Uso de exceções customizadas e tratamento robusto de erros.
*   **Documentação:** Docstrings em todas as funções e classes, READMEs em diretórios chave.
*   **Variáveis de Ambiente:** Configurações sensíveis e de ambiente gerenciadas via `.env`.

## Desenvolvimento Futuro

*   Implementar caching para respostas da API ERP que mudam com pouca frequência.
*   Adicionar testes unitários e de integração.
*   Refinar o sistema de migração do banco de dados (considerar Alembic/Flask-Migrate).
*   Melhorar a configuração de CORS para produção.
*   Implementar mais funcionalidades de consulta ao ERP.
*   Expandir funcionalidades do Módulo fiscal (ex: Detalhes da nota).
*   Expandir funcionalidades do Contas a Receber (ex: Link PIX).
