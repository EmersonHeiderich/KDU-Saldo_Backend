# src/services

Este diretório contém a camada de lógica de negócio da aplicação. Os serviços orquestram as operações, coordenando chamadas para a camada de integração com o ERP (`src/erp_integration`) e a camada de acesso ao banco de dados (`src/database`), e aplicando regras de negócio.

## Arquivos

*   **`accounts_receivable_service.py`**: Lógica para buscar, filtrar, enriquecer (com nome do cliente) e formatar documentos de contas a receber, além de gerar boletos. Utiliza `ErpAccountsReceivableService` e `ErpPersonService`.
*   **`auth_service.py`**: Lógica relacionada à autenticação de usuários da aplicação (login, geração/verificação de token JWT, obtenção do usuário atual). Utiliza `UserRepository`.
*   **`customer_service.py`**: Lógica para buscar e formatar dados de clientes (PF/PJ) e suas estatísticas. Utiliza `ErpPersonService`.
*   **`fabric_service.py`**: Lógica para obter a lista de tecidos (matérias-primas), combinando dados de saldo, custo e detalhes (largura, gramatura, etc.). Utiliza `ErpBalanceService`, `ErpCostService`, `ErpProductService` e `utils`.
*   **`observation_service.py`**: Lógica de negócio para gerenciar observações de produto (adicionar, buscar, resolver, contar). Utiliza `ObservationRepository`.
*   **`product_service.py`**: Lógica para obter informações de produtos acabados, principalmente a matriz de saldo (cor x tamanho). Utiliza `ErpBalanceService` e `utils`.
*   **`README.md`**: Este arquivo.

## Responsabilidades

*   Implementar os casos de uso da aplicação.
*   Validar dados de entrada (embora alguma validação possa ocorrer na camada da API também).
*   Coordenar interações entre diferentes fontes de dados (ERP e banco de dados local).
*   Aplicar regras de negócio (ex: lógica condicional para valores calculados no contas a receber).
*   Formatar dados para serem retornados pela camada da API.
*   Gerenciar transações de negócio (se aplicável, embora as transações de banco de dados sejam gerenciadas nos repositórios).
*   Lançar exceções específicas de serviço (ex: `ValidationError`, `NotFoundError`, `ServiceError`) para serem tratadas pela camada da API.

## Interações

*   **Camada da API (`src/api`)**: Chama os métodos dos serviços para executar ações solicitadas pelos endpoints.
*   **Camada de Integração ERP (`src/erp_integration`)**: Os serviços utilizam os serviços de integração para buscar ou enviar dados para o ERP TOTVS.
*   **Camada de Banco de Dados (`src/database`)**: Os serviços utilizam os repositórios para interagir com o banco de dados local (SQLite).
*   **Domínio (`src/domain`)**: Os serviços manipulam os objetos de domínio (modelos de dados).