# src/api

Este diretório contém a camada da API da aplicação, responsável por expor os endpoints HTTP e lidar com as requisições e respostas.

## Arquivos e Subdiretórios

*   **`__init__.py`**: Inicializa o pacote `api` e contém a função `register_blueprints` para registrar todos os blueprints da API na aplicação Flask principal.
*   **`decorators.py`**: Define decoradores customizados usados nos endpoints para controle de acesso (autenticação e autorização), como `@login_required`, `@admin_required`, `@accounts_receivable_access_required`, etc.
*   **`errors.py`**: Define exceções customizadas (`ApiError`, `ValidationError`, `NotFoundError`, etc.) que podem ser lançadas pelas camadas de serviço ou API, e também registra os manipuladores de erro (`@app.errorhandler`) no Flask para transformar essas exceções (e exceções HTTP padrão) em respostas JSON padronizadas.
*   **`routes/`**: Subdiretório contendo os blueprints Flask, onde cada arquivo corresponde a um grupo lógico de endpoints.
    *   `accounts_receivable.py`: Endpoints de Contas a Receber (`/search`, `/boleto`).
    *   `auth.py`: Endpoints de autenticação (`/login`, `/logout`, `/verify`).
    *   `customer_panel.py`: Endpoints do painel do cliente (`/data`, `/statistics`).
    *   `fabrics.py`: Endpoint para consulta de tecidos (`/balances`).
    *   `fiscal.py`: Endpoints para o módulo Fiscal (`/invoices/search`, `/danfe/{key}`).
    *   `observations.py`: Endpoints para gerenciamento de observações (`/product/...`, `/<id>/resolve`, `/pending_references`).
    *   `products.py`: Endpoints para produtos acabados (`/balance_matrix`).
    *   `users.py`: Endpoints para gerenciamento de usuários (CRUD).
*   **`README.md`**: Este arquivo.

## Responsabilidades

*   Definir os endpoints da API usando Flask Blueprints.
*   Receber requisições HTTP, validar e extrair dados (payload JSON, query parameters, path parameters).
*   Utilizar os decoradores de `decorators.py` para garantir a autenticação e autorização necessárias para cada endpoint.
*   Chamar os métodos apropriados na camada de serviço (`src/services`) para executar a lógica de negócio.
*   Receber os resultados (ou exceções) da camada de serviço.
*   Formatar os resultados em respostas JSON padronizadas ou respostas binárias (ex: PDF do boleto).
*   Utilizar os manipuladores de erro de `errors.py` para garantir que todos os erros (esperados ou inesperados) resultem em respostas JSON consistentes com o status HTTP correto.
*   Interagir com o contexto da aplicação Flask (`current_app`, `request`, `session`).

## Fluxo de Requisição Típico

1.  Requisição HTTP chega ao Flask.
2.  Flask roteia para o endpoint correspondente no Blueprint apropriado (ex: `users.py`).
3.  Decoradores (`@login_required`, `@admin_required`, etc.) são executados para verificar autenticação/autorização. Se a verificação falhar, uma exceção (`AuthenticationError`, `ForbiddenError`) é lançada e o manipulador de erro em `errors.py` retorna a resposta 401/403. Se passar, o usuário é anexado a `request.current_user`.
4.  A função do endpoint é executada.
5.  A função extrai dados da `request`.
6.  A função chama o método correspondente no serviço apropriado (ex: `AuthService`, `UserService`).
7.  O serviço executa a lógica, possivelmente chamando o repositório ou a integração ERP.
8.  O serviço retorna dados ou lança uma exceção (`ValidationError`, `NotFoundError`, `ServiceError`, `DatabaseError`, `ErpIntegrationError`).
9.  Se o serviço retornar dados, a função do endpoint formata esses dados em JSON e retorna a resposta com status 2xx.
10. Se o serviço lançar uma exceção customizada, o manipulador de erro correspondente em `errors.py` captura a exceção e retorna a resposta JSON apropriada com o status HTTP correto (4xx ou 5xx).
11. Se ocorrer uma exceção inesperada, o manipulador genérico em `errors.py` captura, loga o erro completo e retorna uma resposta JSON genérica 500.