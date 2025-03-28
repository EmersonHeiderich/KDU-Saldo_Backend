# src/database

Este diretório contém toda a lógica relacionada à interação com o banco de dados local (SQLite).

## Arquivos

*   **`__init__.py`**: Inicializa o pool de conexões (`ConnectionPool`) e o gerenciador de schema (`SchemaManager`) quando a aplicação inicia. Fornece funções `get_db_pool()`, `close_db()` e fábricas para obter instâncias dos repositórios (`get_user_repository`, `get_observation_repository`).
*   **`base_repository.py`**: Define a classe `BaseRepository` que fornece funcionalidades comuns para todos os repositórios, como aquisição/liberação de conexões do pool e execução de queries SQL (`_execute`, `_execute_transaction`).
*   **`connection_pool.py`**: Implementa a classe `ConnectionPool` thread-safe para gerenciar conexões SQLite, reutilizando-as e limitando o número máximo de conexões ativas. Utiliza `threading.local` para associar conexões a threads.
*   **`observation_repository.py`**: Define `ObservationRepository`, responsável pelas operações CRUD (Create, Read, Update, Delete) relacionadas às observações de produto (`product_observations`) no banco de dados.
*   **`product_repository.py`**: Placeholder para operações relacionadas a dados de *produtos* armazenados localmente (se houver). Atualmente, a lógica de observações está em `ObservationRepository`.
*   **`schema_manager.py`**: Define `SchemaManager`, responsável por criar as tabelas (`CREATE TABLE IF NOT EXISTS`), aplicar migrações (como adicionar novas colunas com `ALTER TABLE`), e garantir dados iniciais essenciais (como o usuário administrador padrão).
*   **`user_repository.py`**: Define `UserRepository`, responsável pelas operações CRUD para as tabelas `users` e `user_permissions`.
*   **`README.md`**: Este arquivo.

## Funcionamento

1.  **Inicialização:** Na inicialização da aplicação (`src.app.create_app`), a função `init_db()` deste pacote é chamada. Ela cria a instância do `ConnectionPool` e do `SchemaManager`.
2.  **Schema:** O `SchemaManager` utiliza o pool para obter uma conexão e executa `initialize_schema()`, que cria as tabelas (se não existirem), aplica migrações necessárias (ex: adiciona colunas) e verifica/cria o usuário admin.
3.  **Repositórios:** As classes de repositório (`UserRepository`, `ObservationRepository`) herdam de `BaseRepository`. Elas recebem a instância do `ConnectionPool` em seu construtor.
4.  **Operações:** Quando um serviço precisa interagir com o banco, ele obtém a instância do repositório apropriado (via `get_user_repository()`, etc.). O repositório utiliza os métodos `_execute` ou `_execute_transaction` da `BaseRepository`.
5.  **Conexões:** A `BaseRepository` usa o `ConnectionPool` para obter (`_get_connection`) e liberar (`_release_connection`) conexões SQLite para cada operação (ou transação), garantindo o gerenciamento correto das conexões.
6.  **Desligamento:** Na finalização da aplicação (hook `teardown_appcontext` do Flask), a função `close_db()` é chamada para fechar todas as conexões no pool.

## Modelos de Dados

Os repositórios geralmente recebem e retornam objetos definidos no pacote `src.domain` (ex: `User`, `Observation`). Eles são responsáveis por mapear entre esses objetos de domínio e as linhas/colunas do banco de dados.