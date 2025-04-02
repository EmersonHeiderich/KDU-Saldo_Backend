# src/database

Este diretório contém toda a lógica relacionada à interação com o banco de dados **PostgreSQL**, utilizando **SQLAlchemy ORM**.

## Arquivos

*   **`__init__.py`**: Inicializa os componentes do SQLAlchemy (`Engine`, `sessionmaker` para criar `SessionLocal`) e o `SchemaManager` quando a aplicação inicia, usando a URI do banco definida na configuração. Fornece a função `get_db_session` (um gerenciador de contexto) para obter e gerenciar sessões de banco de dados, e também as funções fábrica (`get_user_repository`, `get_observation_repository`) que instanciam os repositórios.
*   **`base.py`**: Define a base declarativa (`Base`) do SQLAlchemy da qual todos os modelos ORM herdam. Também configura metadados e convenções de nomenclatura.
*   **`base_repository.py`**: Define a classe `BaseRepository` simplificada, que agora serve principalmente como um ponto de inicialização comum para repositórios, armazenando a `Engine` (embora as operações principais usem a `Session`).
*   **`observation_repository.py`**: Define `ObservationRepository`, responsável pelas operações CRUD relacionadas às observações de produto (`product_observations`) usando a API de Sessão do ORM. Espera receber um objeto `Session` em seus métodos.
*   **`product_repository.py`**: Placeholder para operações relacionadas a dados de *produtos* armazenados localmente (se houver). Adaptado para a estrutura ORM.
*   **`schema_manager.py`**: Define `SchemaManager`, responsável por criar as tabelas baseadas nos modelos ORM (`Base.metadata.create_all(engine)`) e aplicar migrações manuais (ex: `ALTER TABLE ADD COLUMN`, criar índices complexos). Garante dados iniciais essenciais (usuário administrador). **Para futuras migrações, considere usar Alembic.**
*   **`user_repository.py`**: Define `UserRepository`, responsável pelas operações CRUD para as tabelas `users` e `user_permissions` usando a API de Sessão do ORM. Espera receber um objeto `Session` em seus métodos.
*   **`README.md`**: Este arquivo.

## Funcionamento

1.  **Inicialização:** Na inicialização da aplicação (`src.app.create_app`), a função `init_sqlalchemy()` deste pacote é chamada. Ela lê a `SQLALCHEMY_DATABASE_URI`, cria a `Engine` global do SQLAlchemy (que gerencia o pool de conexões) e configura a fábrica de sessões `SessionLocal`.
2.  **Schema:** O `SchemaManager`, recebendo a `Engine`, executa `initialize_schema()`. Isso chama `Base.metadata.create_all(engine)` para criar as tabelas definidas nos modelos ORM (`User`, `Observation`) que não existam. Em seguida, executa migrações manuais (adição de colunas, criação de índices) e garante a existência do usuário admin.
3.  **Repositórios:** As classes de repositório (`UserRepository`, `ObservationRepository`) herdam de `BaseRepository` e são instanciadas (geralmente via funções fábrica como `get_user_repository`) passando a `Engine`.
4.  **Operações:** Quando um serviço precisa interagir com o banco, ele:
    *   Obtém uma `Session` usando o gerenciador de contexto `get_db_session()`.
    *   Obtém a instância do repositório apropriado.
    *   Chama os métodos do repositório, **passando a `Session` obtida** como argumento.
    *   Os métodos do repositório usam a `Session` para interagir com o banco usando a API ORM (ex: `session.get()`, `session.query()`, `session.add()`, `session.delete()`, `session.execute(select(...))`). O ORM traduz essas operações em SQL.
5.  **Transações:** O gerenciador de contexto `get_db_session()` cuida automaticamente do ciclo de vida da transação: inicia a transação, faz `commit` se o bloco `with` for concluído sem erros, faz `rollback` se ocorrer alguma exceção, e fecha a sessão (`close()`) no final.
6.  **Relacionamentos:** O ORM gerencia os relacionamentos definidos nos modelos (como entre `User` e `UserPermissions`), permitindo carregar dados relacionados de forma eficiente (ex: usando `joinedload`).
7.  **Desligamento:** Na finalização da aplicação (hook `atexit`), a função `dispose_sqlalchemy_engine()` é chamada para fechar todas as conexões no pool da engine.

## Modelos de Dados

Os repositórios trabalham com os modelos ORM definidos em `src/domain` (ex: `User`, `Observation`), que herdam de `src/database/base.py::Base`. O SQLAlchemy ORM mapeia esses objetos diretamente para as linhas/colunas do banco de dados.