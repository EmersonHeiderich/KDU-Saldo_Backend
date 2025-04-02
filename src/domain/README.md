# src/domain

Este diretório contém os modelos de dados da aplicação. Eles representam as estruturas de dados manipuladas pela aplicação, incluindo tanto os modelos ORM para o banco de dados local quanto Dataclasses para representar dados vindos do ERP ou usados como DTOs (Data Transfer Objects).

## Arquivos

*   **Modelos ORM (SQLAlchemy):**
    *   `user.py`: Define os modelos ORM `User` e `UserPermissions` mapeados para as tabelas do banco de dados local. Herdam de `src.database.base.Base`.
    *   `observation.py`: Define o modelo ORM `Observation` mapeado para a tabela `product_observations`. Herda de `src.database.base.Base`.
*   **Dataclasses (DTOs / Modelos ERP):**
    *   `accounts_receivable.py`: Define modelos Dataclass para dados de Contas a Receber do ERP (ex: `DocumentModel`, `BankSlipRequestModel`, `FormattedReceivableListItem`).
    *   `balance.py`: Define `Balance`, `ProductItem`, `ProductResponse` (Dataclasses) para dados de saldo do ERP.
    *   `cost.py`: Define `Cost`, `ProductCost`, `CostResponse` (Dataclasses) para dados de custo do ERP.
    *   `fabric_details.py`: Define `FabricDetailValue`, `FabricDetailsItem` (Dataclasses) para detalhes específicos de tecidos (largura, gramatura, etc.) do ERP.
    *   `fiscal.py`: Define modelos Dataclass para operações do módulo Fiscal (ex: `FormattedInvoiceListItem`, `InvoiceXmlOutDto`, `DanfeResponseModel`).
    *   `person.py`: Define `Address`, `Phone`, `Email`, `IndividualDataModel`, `LegalEntityDataModel`, `PersonStatisticsResponseModel` (Dataclasses) para dados de pessoa (PF/PJ) do ERP.
*   **Outros:**
    *   `__init__.py`: Exporta todos os modelos (ORM e Dataclasses) para fácil importação.
    *   `README.md`: Este arquivo.

## Padrões

*   **Modelos ORM:**
    *   Implementados como classes Python que herdam de `src.database.base.Base`.
    *   Usam `Mapped` e `mapped_column` do SQLAlchemy 2.0 para definir atributos e mapeamento de colunas.
    *   Definem relacionamentos usando `relationship`.
    *   Podem conter métodos de lógica de negócio relacionados ao próprio modelo (ex: `User.verify_password`).
    *   Incluem um método `to_dict()` para facilitar a serialização para JSON na camada da API.
*   **Dataclasses:**
    *   Usados para representar estruturas de dados que *não* são mapeadas diretamente para tabelas do banco local (principalmente dados do ERP ou DTOs específicos da API).
    *   Geralmente `frozen=True` (imutáveis) para dados vindos de fontes externas.
    *   Incluem métodos `from_dict` (ou similar) para criar instâncias a partir de respostas de API e `to_dict` para serialização.
*   **Type Hinting:** Tipos são definidos para todos os atributos.
*   **Validação:** A validação nos métodos `from_dict` de Dataclasses é básica. Validações mais complexas podem residir nos serviços. Modelos ORM dependem das constraints do banco e validações na camada de serviço antes da persistência.