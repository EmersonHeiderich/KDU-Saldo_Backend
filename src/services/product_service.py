from typing import List, Dict, Any
from src.domain.balance import ProductItem
from src.erp_integration.erp_balance_service import ErpBalanceService
from src.utils.matrix_builder import build_product_matrix
from src.utils.logger import logger
from src.api.errors import ServiceError, NotFoundError, ValidationError

class ProductService:
    """
    Camada de serviço para operações relacionadas a produtos acabados, principalmente informações de saldo.
    """
    def __init__(self, erp_balance_service: ErpBalanceService):
        self.erp_balance_service = erp_balance_service
        logger.info("ProductService inicializado.")

    def get_product_balance_matrix_with_items(self, reference_code: str, calculation_mode: str = 'base') -> Dict[str, Any]:
        """
            Recupera dados de saldo de produto para um código de referência do ERP,
            formata-os em uma estrutura de matriz (cor x tamanho) e inclui os itens brutos.

            Argumentos:
            reference_code: O código de referência do produto a ser consultado.
            computation_mode: O modo de cálculo de saldo ('base', 'sales', 'production').

            Retorna:
            Um dicionário contendo:
            {
            "reference_code": str,
            "calculation_mode": str,
            "matrix": Dict[str, Any], # A estrutura de matriz de build_product_matrix
            "product_items": List[Dict[str, Any]] # Dados brutos de ProductItem como dicts
            }

            Gera:
            ValidationError: Se os parâmetros de entrada forem inválidos.
            NotFoundError: Se nenhum produto for encontrado para o código de referência.
            ServiceError: Se ocorrer um erro durante a comunicação do ERP ou o processamento de dados.
        """
        if not reference_code:
            raise ValidationError("O código de referência do produto não pode estar vazio.")
        if calculation_mode not in ['base', 'sales', 'production']:
            raise ValidationError(f"Modo de cálculo inválido: '{calculation_mode}'. Modos válidos: 'base', 'sales', 'production'.")

        logger.info(f"Buscando matriz de saldo e itens para referência '{reference_code}', modo '{calculation_mode}'.")

        try:
            logger.debug(f"Chamando serviço de saldo do ERP para código de referência: {reference_code}")
            product_items: List[ProductItem] = self.erp_balance_service.get_balances(
                reference_code_list=[reference_code],
                is_fabric=False
            )

            if not product_items:
                logger.warning(f"Nenhum item de produto encontrado no ERP para código de referência: {reference_code}")
                raise NotFoundError(f"Nenhum produto encontrado para o código de referência '{reference_code}'.")

            logger.debug(f"Encontrados {len(product_items)} itens de produto para referência '{reference_code}'. Construindo matriz...")
            matrix_data = build_product_matrix(product_items, calculation_mode)
            logger.info(f"Matriz de saldo construída com sucesso para referência '{reference_code}'.")

            product_items_dict = [item.to_dict() for item in product_items]

            response_data = {
                "reference_code": reference_code,
                "calculation_mode": calculation_mode,
                "matrix": matrix_data,
                "product_items": product_items_dict
            }
            return response_data

        except (NotFoundError, ValidationError) as e:
             raise e
        except Exception as e:
            logger.error(f"Erro ao obter matriz de saldo do produto para '{reference_code}': {e}", exc_info=True)
            raise ServiceError(f"Falha ao recuperar matriz de saldo do produto: {e}") from e
