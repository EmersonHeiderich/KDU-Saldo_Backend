# src/utils

Este diretório contém módulos utilitários que fornecem funcionalidades de suporte usadas em várias partes da aplicação, mas que não se encaixam diretamente na lógica de negócio principal, acesso a dados ou integração ERP.

## Arquivos

*   **`logger.py`**: Configura o logger da aplicação (usando o módulo `logging` do Python). Define o formato, nível e handlers (console e arquivo rotativo) para os logs. Exporta a instância `logger` configurada para ser usada em toda a aplicação.
*   **`matrix_builder.py`**: Contém a função `build_product_matrix` que transforma uma lista de dados de saldo de produto (obtida do ERP) em uma estrutura de matriz (cor x tamanho) para exibição no frontend. Inclui lógica para ordenação inteligente de tamanhos e cálculo de totais.
*   **`fabric_list_builder.py`**: Contém as funções `build_fabric_list` e `filter_fabric_list`. A primeira combina dados de saldo, custo e detalhes de tecidos em uma lista formatada. A segunda filtra essa lista com base em um texto de busca.
*   **`system_monitor.py`**: Fornece funções (`log_system_resources`, `start_resource_monitor`, `stop_resource_monitor`) para registrar periodicamente o uso de recursos do sistema (memória, CPU, threads) pela aplicação. Útil para monitoramento e diagnóstico de performance.
*   **`README.md`**: Este arquivo.

## Uso

Importe as funções ou a instância `logger` diretamente destes módulos onde for necessário.

```python
# Exemplo de uso do logger
from src.utils.logger import logger
logger.info("Esta é uma mensagem informativa.")
logger.error("Ocorreu um erro.", exc_info=True)

# Exemplo de uso do matrix_builder (em um serviço, por exemplo)
from src.utils.matrix_builder import build_product_matrix
from src.domain.balance import ProductItem # Assuming product_items is List[ProductItem]
matrix_data = build_product_matrix(product_items, 'sales')

# Exemplo de uso do system_monitor (na inicialização da app, por exemplo)
from src.utils.system_monitor import start_resource_monitor
start_resource_monitor() # Inicia o monitoramento em background