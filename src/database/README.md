
**3. `src/database/README.md`**

# src/database

Este diretório contém toda a lógica relacionada à interação com o banco de dados **PostgreSQL**, utilizando **SQLAlchemy Core**.

## Arquivos

*   **`__init__.py`**: Inicializa o *engine* do SQLAlchemy (`Engine`) e o gerenciador de schema (`SchemaManager`) quando a aplicação inicia, usando a URI do banco definida na configuração. Fornece funções `get_sqlalchemy_engine()`, `dispose_sqlalchemy_engine()` e fábricas para obter instâncias dos repositórios (`get_user_repository`, `get_observation_repository`).
*   **`base_repository.py`**: Define a classe `BaseRepository` que fornece funcionalidades comuns para todos os repositórios. Utiliza o `Engine` do SQLAlchemy para obter conexões e executar queries SQL brutas (usando `text()`). Gerencia a execução, mas **não** commita transações (isso é feito nos métodos dos repositórios filhos ou serviços).
*   **`observation_repository.py`**: Define `ObservationRepository`, responsável pelas operações CRUD relacionadas às observações de produto (`product_observations`). Usa transações explícitas (`connection.begin()`) para operações de escrita.
*   **`product_repository.py`**: Placeholder para operações relacionadas a dados de *produtos* armazenados localmente (se houver). Adaptado para usar SQLAlchemy Engine.
*   **`schema_manager.py`**: Define `SchemaManager`, responsável por criar as tabelas (`CREATE TABLE IF NOT EXISTS`) e aplicar migrações simples (`ALTER TABLE ADD COLUMN IF NOT EXISTS`) usando sintaxe PostgreSQL e o `Engine` SQLAlchemy. Garante dados iniciais essenciais (usuário administrador). **Para futuras migrações, considere usar Alembic.**
*   **`user_repository.py`**: Define `UserRepository`, responsável pelas operações CRUD para as tabelas `users` e `user_permissions`. Usa transações explícitas (`connection.begin()`) para operações de escrita.
*   **`README.md`**: Este arquivo.

## Funcionamento

1.  **Inicialização:** Na inicialização da aplicação (`src.app.create_app`), a função `init_sqlalchemy_engine()` deste pacote é chamada. Ela lê a `SQLALCHEMY_DATABASE_URI` da configuração e cria a instância global do `Engine` SQLAlchemy, que gerencia um pool de conexões.
2.  **Schema:** O `SchemaManager`, recebendo o `Engine`, obtém uma conexão e executa `initialize_schema()`, que cria as tabelas e aplica migrações dentro de uma transação.
3.  **Repositórios:** As classes de repositório (`UserRepository`, `ObservationRepository`) herdam de `BaseRepository` e recebem o `Engine` em seu construtor.
4.  **Operações:** Quando um serviço precisa interagir com o banco, ele obtém a instância do repositório apropriado.
    *   Para **leituras** (`SELECT`), o repositório geralmente chama `_execute` da `BaseRepository`, que obtém uma conexão do pool, executa a query e a libera.
    *   Para **escritas** (`INSERT`, `UPDATE`, `DELETE`), o método do repositório obtém uma conexão do `Engine` (`with self.engine.connect() as connection:`), inicia uma transação explícita (`with connection.begin():`), executa uma ou mais operações usando `connection.execute(text(...))`, e a transação é commitada (ou revertida em caso de erro) automaticamente ao final do bloco `with connection.begin():`.
5.  **Desligamento:** Na finalização da aplicação (hook `atexit`), a função `dispose_sqlalchemy_engine()` é chamada para fechar todas as conexões no pool do engine.

## Modelos de Dados

Os repositórios geralmente recebem e retornam objetos definidos no pacote `src.domain` (ex: `User`, `Observation`). Eles são responsáveis por mapear entre esses objetos de domínio e as linhas/colunas do banco de dados.