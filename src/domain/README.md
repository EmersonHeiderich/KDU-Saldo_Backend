# src/domain

Este diretório contém os modelos de dados da aplicação, também conhecidos como entidades de domínio ou Data Transfer Objects (DTOs). Eles representam as estruturas de dados manipuladas pela aplicação.

## Arquivos

*   **`balance.py`**: Define `Balance`, `ProductItem`, `ProductResponse` para dados de saldo do ERP.
*   **`cost.py`**: Define `Cost`, `ProductCost`, `CostResponse` para dados de custo do ERP.
*   **`fabric_details.py`**: Define `FabricDetailValue`, `FabricDetailsItem` para detalhes específicos de tecidos (largura, gramatura, etc.) do ERP.
*   **`observation.py`**: Define `Observation` para os dados de observações de produto armazenados localmente.
*   **`person.py`**: Define `Address`, `Phone`, `Email`, `IndividualDataModel`, `LegalEntityDataModel`, `PersonStatisticsResponseModel` para dados de pessoa (PF/PJ) do ERP.
*   **`user.py`**: Define `User` e `UserPermissions` para os usuários da aplicação e suas permissões.
*   **`README.md`**: Este arquivo.

## Padrões

*   **Dataclasses:** Os modelos são implementados como `dataclasses` para concisão e clareza.
*   **Imutabilidade:** Modelos que representam dados vindos de fontes externas (ERP) são geralmente `frozen=True` (imutáveis) para evitar modificações acidentais. Modelos que representam dados gerenciados pela aplicação (como `User`, `Observation`) podem ser mutáveis.
*   **Type Hinting:** Tipos são definidos para todos os atributos.
*   **`from_dict` / `from_api_response`:** Métodos de classe para criar instâncias a partir de dicionários (vindos do banco de dados ou respostas de API). Incluem tratamento básico de erros e logs para dados inválidos.
*   **`to_dict`:** Métodos para converter as instâncias em dicionários, útil para serialização JSON ou armazenamento.
*   **Validação:** A validação nos métodos `from_dict` é básica. Validações mais complexas podem ser adicionadas ou gerenciadas em camadas superiores (serviços).