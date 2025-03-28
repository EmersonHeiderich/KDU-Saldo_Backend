# src/erp_integration

Este diretório contém a camada responsável por toda a comunicação com a API externa do ERP TOTVS. O objetivo é isolar a complexidade da integração com o ERP do resto da aplicação.

## Arquivos

*   **`erp_auth_service.py`**: Gerencia a autenticação com a API do ERP, obtendo e renovando os tokens de acesso (Bearer tokens) necessários para as demais chamadas. Implementado como um Singleton thread-safe.
*   **`erp_balance_service.py`**: Responsável por buscar dados de saldo de produtos (acabados ou matérias-primas) do endpoint `/product/v2/balances/search` do ERP.
*   **`erp_cost_service.py`**: Responsável por buscar dados de custo de produtos do endpoint `/product/v2/costs/search` do ERP.
*   **`erp_person_service.py`**: Responsável por buscar dados de pessoas (PF/PJ) e estatísticas dos endpoints `/person/v2/*` do ERP.
*   **`erp_product_service.py`**: Responsável por buscar dados genéricos de produtos do endpoint `/product/v2/products/search` do ERP, usado especificamente aqui para obter detalhes adicionais de tecidos (largura, gramatura, etc.).
*   **`README.md`**: Este arquivo.

## Responsabilidades

*   Encapsular os detalhes da comunicação com a API do ERP (URLs, payloads, headers).
*   Utilizar o `ErpAuthService` para obter tokens de autenticação válidos.
*   Realizar chamadas HTTP (GET/POST) para os endpoints específicos do ERP.
*   Implementar lógica de retentativas (`MAX_RETRIES`) em caso de falhas de rede ou erros específicos (como 401 para token expirado).
*   Tratar erros de comunicação com o ERP e lançar exceções específicas (`ErpIntegrationError`, `ErpNotFoundError`) para a camada de serviço (`src/services`).
*   Mapear as respostas JSON do ERP para os modelos de domínio definidos em `src/domain` (ex: `ProductItem`, `CostResponse`, `IndividualDataModel`).
*   Gerenciar a paginação das APIs do ERP, buscando todas as páginas necessárias para retornar um conjunto completo de dados.

## Interações

*   **Camada de Serviço (`src/services`)**: Os serviços de negócio utilizam os serviços desta camada para obter dados do ERP.
*   **Configuração (`src/config`)**: Utiliza as configurações definidas em `settings.py` (URLs, credenciais, códigos, etc.).
*   **Domínio (`src/domain`)**: Recebe dados brutos do ERP e os transforma nos objetos de domínio definidos.
*   **API Errors (`src/api/errors`)**: Lança exceções customizadas definidas neste pacote em caso de erros específicos do ERP.
*   **Utils (`src/utils`)**: Utiliza o `logger` para registrar informações e erros.