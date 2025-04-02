# src/services

Este diretório contém a camada de lógica de negócio da aplicação. Os serviços orquestram as operações, coordenando chamadas para a camada de integração com o ERP (`src/erp_integration`) e a camada de acesso ao banco de dados (`src/database`), aplicando regras de negócio e gerenciando o ciclo de vida das sessões de banco de dados para operações que o exigem.

## Arquivos

*   **`accounts_receivable_service.py`**: Lógica para buscar, filtrar, enriquecer e formatar documentos de contas a receber, além de gerar boletos. Utiliza `ErpAccountsReceivableService` e `ErpPersonService`.
*   **`auth_service.py`**: Lógica para autenticação de usuários (login, geração/verificação de token JWT). Utiliza `UserRepository` e gerencia a sessão de banco de dados (`get_db_session`) para buscar usuários e atualizar o último login.
*   **`customer_service.py`**: Lógica para buscar e formatar dados de clientes (PF/PJ) e estatísticas. Utiliza `ErpPersonService`.
*   **`fabric_service.py`**: Lógica para obter a lista de tecidos, combinando dados de saldo, custo e detalhes. Utiliza `ErpBalanceService`, `ErpCostService`, `ErpProductService` e `utils`.
*   **`fiscal_service.py`**: Lógica para buscar notas fiscais e gerar DANFE. Utiliza `ErpFiscalService`.
*   **`observation_service.py`**: Lógica de negócio para gerenciar observações de produto (adicionar, buscar, resolver, contar). Utiliza `ObservationRepository` e gerencia a sessão de banco de dados (`get_db_session`) para todas as operações no banco.
*   **`product_service.py`**: Lógica para obter informações de produtos acabados (matriz de saldo). Utiliza `ErpBalanceService` e `utils`.
*   **`README.md`**: Este arquivo.

## Responsabilidades

*   Implementar os casos de uso da aplicação.
*   Validar dados de entrada.
*   Coordenar interações entre diferentes fontes de dados (ERP e banco de dados local).
*   Aplicar regras de negócio.
*   **Gerenciar Sessões de Banco de Dados:** Para operações que modificam ou leem dados do banco local (ex: login, gerenciamento de observações, CRUD de usuários), os serviços utilizam o gerenciador de contexto `get_db_session()` para obter uma `Session` SQLAlchemy e passá-la aos métodos do repositório correspondente. A sessão garante a atomicidade das operações (commit/rollback).
*   Formatar dados para serem retornados pela camada da API (convertendo objetos ORM em dicionários quando necessário).
*   Lançar exceções específicas (`ValidationError`, `NotFoundError`, `ServiceError`, `DatabaseError`) para serem tratadas pela camada da API.

## Interações

*   **Camada da API (`src/api`)**: Chama os métodos dos serviços.
*   **Camada de Integração ERP (`src/erp_integration`)**: Os serviços utilizam os serviços de integração para interagir com o ERP.
*   **Camada de Banco de Dados (`src/database`)**:
    *   Obtém instâncias dos repositórios (`UserRepository`, `ObservationRepository`) via funções fábrica (`get_user_repository`, etc.).
    *   Utiliza `get_db_session()` para obter e gerenciar sessões SQLAlchemy.
    *   Passa a `Session` ativa para os métodos dos repositórios que precisam interagir com o banco.
*   **Domínio (`src/domain`)**: Os serviços manipulam os objetos de domínio (modelos ORM e Dataclasses).