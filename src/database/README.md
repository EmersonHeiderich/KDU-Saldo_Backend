# src/database

Este diretório contém toda a lógica relacionada à interação com o banco de dados **PostgreSQL**, utilizando **SQLAlchemy ORM** e **Alembic** para gerenciamento de schema.

## Arquivos

*   **`__init__.py`**: Inicializa os componentes do SQLAlchemy (`Engine`, `sessionmaker` para criar `SessionLocal`) quando a aplicação inicia, usando a URI do banco definida na configuração. Fornece a função `get_db_session` (um gerenciador de contexto) para obter e gerenciar sessões de banco de dados. **Não contém mais as funções de fábrica de repositórios nem a inicialização do SchemaManager aqui.**
*   **`base.py`**: Define a base declarativa (`Base`) do SQLAlchemy da qual todos os modelos ORM herdam. Também configura metadados e convenções de nomenclatura, que são usados pelo Alembic.
*   **`base_repository.py`**: Define a classe `BaseRepository` simplificada, que serve como ponto de inicialização comum para repositórios, armazenando a `Engine`.
*   **`observation_repository.py`**: Define `ObservationRepository`, responsável pelas operações CRUD relacionadas às observações de produto (`product_observations`) usando a API de Sessão do ORM.
*   **`product_repository.py`**: Placeholder para operações relacionadas a dados de *produtos* armazenados localmente.
*   **`schema_manager.py`**: Define `SchemaManager`, **agora com responsabilidade reduzida**. Sua função principal é garantir que as tabelas existam na **primeira inicialização** (usando `Base.metadata.create_all`) antes que o Alembic seja aplicado, e garantir dados iniciais essenciais (usuário administrador). **NÃO é mais responsável por criar índices, constraints ou aplicar alterações de schema (ALTER TABLE) - isso é feito pelo Alembic.**
*   **`user_repository.py`**: Define `UserRepository`, responsável pelas operações CRUD para as tabelas `users` e `user_permissions` usando a API de Sessão do ORM.
*   **`README.md`**: Este arquivo.

## Funcionamento com Alembic

1.  **Inicialização da App (`src/app.py`):**
    *   A função `init_sqlalchemy()` deste pacote é chamada. Ela cria a `Engine` global do SQLAlchemy e configura a fábrica de sessões `SessionLocal`.
    *   O `SchemaManager` é instanciado e `initialize_schema()` é chamado. Ele executa `Base.metadata.create_all(engine)` (que cria tabelas que *não* existem) e garante o usuário admin.
2.  **Gerenciamento de Schema (Alembic):**
    *   **Fora da execução normal da aplicação**, o desenvolvedor usa os comandos `alembic` para gerenciar o schema.
    *   `alembic revision --autogenerate`: Compara os modelos ORM (`Base.metadata`) com o banco de dados e gera um script de migração em `alembic/versions/`.
    *   `alembic upgrade head`: Aplica os scripts de migração pendentes ao banco de dados, efetivamente criando/alterando tabelas, colunas, índices, etc.
    *   Isso garante que as alterações no schema sejam versionadas e aplicadas de forma consistente em diferentes ambientes (desenvolvimento, teste, produção).
3.  **Repositórios e Operações:** (Funcionamento permanece o mesmo)
    *   Os serviços obtêm instâncias dos repositórios.
    *   Para operações no banco, os serviços usam `get_db_session()` para obter uma `Session`.
    *   A `Session` é passada para os métodos do repositório.
    *   Os repositórios usam a `Session` e a API ORM para interagir com o banco.
    *   O contexto `get_db_session()` gerencia commit/rollback/close.
4.  **Desligamento:** Na finalização da aplicação, `dispose_sqlalchemy_engine()` fecha o pool de conexões.

## Modelos de Dados

Os repositórios trabalham com os modelos ORM definidos em `src/domain` (ex: `User`, `Observation`), que herdam de `src/database/base.py::Base`. O Alembic usa esses mesmos modelos (`Base.metadata`) como a "verdade" sobre como o schema do banco de dados deve ser.