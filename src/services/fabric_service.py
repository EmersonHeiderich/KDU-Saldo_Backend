import time
from typing import List, Dict, Any, Optional
from cachetools import TTLCache, cached

from src.domain.balance import ProductItem as BalanceItem # Alias para clareza
from src.domain.cost import ProductCost
from src.domain.fabric_details import FabricDetailsItem
from src.erp_integration.erp_balance_service import ErpBalanceService
from src.erp_integration.erp_cost_service import ErpCostService
from src.erp_integration.erp_product_service import ErpProductService # Para detalhes do tecido
from src.utils.fabric_list_builder import build_fabric_list, filter_fabric_list # Importar construtores
from src.utils.logger import logger
from src.api.errors import ServiceError, NotFoundError

# Configuração do cache: TTL de 10 minutos, máximo de 10 entradas
# Observação: Este cache é específico para a instância. Se várias instâncias forem executadas, os caches são separados.
fabric_data_cache = TTLCache(maxsize=10, ttl=600) # 600 segundos = 10 minutos

# Função auxiliar para geração de chave de cache (lida com filtro None)
def _get_cache_key(search_filter: Optional[str]) -> str:
    return f"filter:{search_filter or '_NONE_'}"

class FabricService:
    """
    Camada de serviço para operações relacionadas a tecidos (matéria-prima).
    Busca dados no ERP, combina e fornece listas formatadas com cache.
    """
    def __init__(self,
                 erp_balance_service: ErpBalanceService,
                 erp_cost_service: ErpCostService,
                 erp_product_service: ErpProductService):
        self.erp_balance_service = erp_balance_service
        self.erp_cost_service = erp_cost_service
        self.erp_product_service = erp_product_service # Injeta serviço de produtos para detalhes
        logger.info("FabricService inicializado.")

    def clear_fabric_cache(self):
        """Limpa o cache de dados de tecidos."""
        logger.info("Limpando o cache de dados de tecidos.")
        fabric_data_cache.clear()

    def get_fabrics(self, search_filter: Optional[str] = None, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Recupera uma lista de tecidos (matérias-primas) com saldo, custo e detalhes,
        usando cache e opcionalmente filtrada por um termo de pesquisa.

        Args:
            search_filter: Texto para filtrar tecidos pela descrição (case-insensitive).
                           O filtro ocorre APÓS a busca e cacheamento.
            force_refresh: Se True, ignora o cache e busca dados frescos.

        Returns:
            Uma lista de dicionários, cada um representando um tecido com seus dados.

        Raises:
            ServiceError: Se ocorrer um erro na recuperação ou processamento dos dados.
            NotFoundError: Se nenhum tecido for encontrado no ERP.
        """
        cache_key = _get_cache_key(search_filter) # Usa o filtro na chave do cache
        log_prefix = f"tecidos (Filtro: '{search_filter or 'Nenhum'}', Forçar: {force_refresh})"
        logger.info(f"Buscando {log_prefix}...")

        if not force_refresh and cache_key in fabric_data_cache:
            logger.info(f"Cache encontrado para chave '{cache_key}'. Retornando dados em cache.")
            return list(fabric_data_cache[cache_key])

        logger.info(f"Cache ausente ou force_refresh=True para chave '{cache_key}'. Buscando dados do ERP.")
        try:
            full_fabric_list_unfiltered = self._fetch_and_build_fabrics()
            unfiltered_cache_key = _get_cache_key(None)
            fabric_data_cache[unfiltered_cache_key] = full_fabric_list_unfiltered
            logger.info(f"Armazenados {len(full_fabric_list_unfiltered)} tecidos no cache com chave '{unfiltered_cache_key}'.")

            if search_filter:
                logger.debug(f"Aplicando filtro no cliente: '{search_filter}'")
                filtered_list = filter_fabric_list(full_fabric_list_unfiltered, search_filter)
                logger.info(f"Lista de tecidos filtrada de {len(full_fabric_list_unfiltered)} para {len(filtered_list)} itens.")
                return filtered_list
            else:
                return full_fabric_list_unfiltered

        except NotFoundError:
            logger.warning(f"Nenhum tecido encontrado no ERP para {log_prefix}.")
            raise
        except Exception as e:
            logger.error(f"Erro ao recuperar {log_prefix}: {e}", exc_info=True)
            raise ServiceError(f"Falha ao recuperar a lista de tecidos: {e}") from e

    def _fetch_and_build_fabrics(self) -> List[Dict[str, Any]]:
        """Método interno para buscar dados do ERP e construir a lista de tecidos."""
        logger.debug("Buscando saldos de tecidos no ERP...")
        fabric_balances: List[BalanceItem] = self.erp_balance_service.get_balances(is_fabric=True)
        logger.debug(f"Obtidos {len(fabric_balances)} itens de saldo para tecidos.")

        if not fabric_balances:
            raise NotFoundError("Nenhum tecido encontrado no sistema ERP.")

        logger.debug("Buscando custos de tecidos no ERP...")
        fabric_costs: List[ProductCost] = self.erp_cost_service.get_costs(is_fabric=True)
        logger.debug(f"Obtidos {len(fabric_costs)} itens de custo para tecidos.")

        logger.debug("Buscando detalhes dos tecidos (largura, gramatura, etc.) no ERP...")
        fabric_details_map: Dict[int, FabricDetailsItem] = self.erp_product_service.get_fabric_details()
        logger.debug(f"Obtidos detalhes de {len(fabric_details_map)} tecidos.")

        logger.debug("Construindo lista de tecidos...")
        full_fabric_list = build_fabric_list(fabric_balances, fabric_costs, fabric_details_map)
        logger.debug(f"Lista de tecidos construída com {len(full_fabric_list)} itens.")

        return full_fabric_list
