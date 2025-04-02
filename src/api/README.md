# src/api

Este diretório contém a camada da API da aplicação, responsável por expor os endpoints HTTP e lidar com as requisições e respostas, utilizando Flask.

## Arquivos e Subdiretórios

*   **`__init__.py`**: Inicializa o pacote `api` e contém a função `register_blueprints` para registrar todos os blueprints da API na aplicação Flask principal.
*   **`decorators.py`**: Define decoradores customizados (`@login_required`, `@admin_required`, etc.) para controle de acesso (autenticação e autorização). O `@login_required` agora utiliza o `AuthService` (com sua própria sessão de banco de dados) para validar o token e carregar o usuário (`request.current_user`).
*   **`errors.py`**: Define exceções customizadas (`ApiError`, `ValidationError`, etc.) e registra os manipuladores de erro (`@app.errorhandler`) no Flask para respostas JSON padronizadas.
*   **`routes/`**: Subdiretório contendo os blueprints Flask:
    *   `accounts_receivable.py`: Endpoints de Contas a Receber.
    *   `auth.py`: Endpoints de autenticação (`/login`, `/logout`, `/verify`). O endpoint de login chama o `AuthService`.
    *   `customer_panel.py`: Endpoints do painel do cliente.
    *   `fabrics.py`: Endpoint para consulta de tecidos.
    *   `fiscal.py`: Endpoints para o módulo Fiscal.
    *   `observations.py`: Endpoints para gerenciamento de observações. Chamam o `ObservationService` e convertem os objetos ORM `Observation` retornados em JSON usando `.to_dict()`.
    *   `products.py`: Endpoints para produtos acabados.
    *   `users.py`: Endpoints para gerenciamento de usuários (CRUD). Chamam diretamente os métodos do `UserRepository` (obtendo a sessão via `get_db_session` dentro da rota) ou o `AuthService`. Convertem os objetos ORM `User` em JSON usando `.to_dict()`.
*   **`README.md`**: Este arquivo.

## Responsabilidades

*   Definir os endpoints da API usando Flask Blueprints.
*   Receber requisições HTTP, validar e extrair dados.
*   Utilizar os decoradores de `decorators.py` para autenticação/autorização.
*   Chamar os métodos apropriados na camada de serviço (`src/services`). **A camada da API não gerencia mais diretamente as sessões de banco de dados; isso é feito pelos serviços que precisam delas.**
*   Receber os resultados (dados brutos, objetos ORM, Dataclasses) ou exceções da camada de serviço.
*   Formatar os resultados em respostas JSON. Para objetos ORM, utiliza o método `.to_dict()` do objeto antes de serializar.
*   Utilizar os manipuladores de erro de `errors.py` para respostas de erro consistentes.
*   Interagir com o contexto da aplicação Flask (`current_app`, `request`, `session`).

## Fluxo de Requisição Típico (com ORM)

1.  Requisição HTTP chega ao Flask.
2.  Flask roteia para o endpoint correspondente.
3.  Decoradores (`@login_required`, etc.) são executados. `@login_required` chama `AuthService.get_current_user_from_request()`, que usa `get_db_session()` para buscar o usuário no banco via `UserRepository`. Se ok, `request.current_user` é populado com o objeto `User` ORM. Se falhar, erro 401/403 é retornado.
4.  A função do endpoint é executada.
5.  A função extrai dados da `request`.
6.  A função chama o método do serviço apropriado (ex: `ObservationService.add_observation`).
7.  O serviço executa a lógica:
    *   Se precisar do banco, ele usa `with get_db_session() as db:`.
    *   Obtém o repositório necessário (ex: `self.observation_repository`).
    *   Chama o método do repositório, **passando a sessão `db`**.
    *   O repositório interage com o banco usando a sessão ORM.
    *   Se precisar do ERP, chama o serviço de integração ERP correspondente.
8.  O serviço retorna dados (podem ser objetos ORM, Dataclasses, dicts) ou lança uma exceção. A sessão do banco é commitada/revertida/fechada pelo `get_db_session()`.
9.  Se o serviço retornar dados:
    *   Se forem objetos ORM, a função do endpoint chama `.to_dict()` neles.
    *   Os dados (agora dicionários/listas) são formatados em JSON e retornados com status 2xx.
10. Se o serviço lançar uma exceção, o manipulador de erro correspondente em `errors.py` captura e retorna a resposta JSON apropriada (4xx ou 5xx).
11. Se ocorrer uma exceção inesperada, o manipulador genérico em `errors.py` captura, loga e retorna 500.