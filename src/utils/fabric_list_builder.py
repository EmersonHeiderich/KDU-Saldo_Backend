from typing import List, Dict, Any, Optional, TYPE_CHECKING
from src.utils.logger import logger

if TYPE_CHECKING:
    from src.domain.balance import ProductItem as BalanceItem
    from src.domain.cost import ProductCost
    from src.domain.fabric_details import FabricDetailsItem

def build_fabric_list(
    balances: List['BalanceItem'],
    costs: List['ProductCost'],
    details: Dict[int, 'FabricDetailsItem']
) -> List[Dict[str, Any]]:
    """
    Constrói uma lista de tecidos combinando dados de saldo, custo e detalhes.
    """
    from src.domain.balance import ProductItem as BalanceItem
    from src.domain.cost import ProductCost
    from src.domain.fabric_details import FabricDetailsItem

    logger.debug(f"Construindo lista de tecidos com {len(balances)} itens de saldo, {len(costs)} itens de custo, {len(details)} itens de detalhes.")

    cost_map: Dict[int, ProductCost] = {cost.product_code: cost for cost in costs if isinstance(cost, ProductCost)}
    fabric_list: List[Dict[str, Any]] = []
    processed_codes = set()

    for balance_item in balances:
        if not isinstance(balance_item, BalanceItem) or balance_item.product_code in processed_codes:
            continue

        product_code = balance_item.product_code
        processed_codes.add(product_code)

        # Calcular saldo
        fabric_balance = 0
        if balance_item.balances:
            try:
                fabric_balance = balance_item.calculate_base_balance()
            except Exception as e:
                logger.error(f"Erro ao calcular saldo do tecido {product_code}: {e}")
        else:
            logger.warning(f"Tecido {product_code} não possui entradas de saldo.")

        # Obter custo
        cost_value: Optional[float] = None
        cost_item = cost_map.get(product_code)
        if cost_item:
            try:
                cost_value = cost_item.get_primary_cost_value()
            except Exception as e:
                logger.error(f"Erro ao obter custo do tecido {product_code}: {e}")
        else:
            logger.debug(f"Nenhum dado de custo encontrado para o tecido {product_code}.")

        # Obter detalhes
        details_item = details.get(product_code)
        width, grammage, shrinkage = None, None, None
        if isinstance(details_item, FabricDetailsItem):
            width = details_item.width
            grammage = details_item.grammage
            shrinkage = details_item.shrinkage
        elif details_item is not None:
            logger.warning(f"Detalhes encontrados para tecido {product_code}, mas o tipo está incorreto: {type(details_item)}")

        fabric_dict = {
            "code": product_code,
            "description": balance_item.product_name or "N/A",
            "balance": fabric_balance,
            "cost": cost_value,
            "width": width,
            "grammage": grammage,
            "shrinkage": shrinkage
        }
        fabric_list.append(fabric_dict)

    balance_codes = {b.product_code for b in balances if isinstance(b, BalanceItem)}
    cost_only_codes = set(cost_map.keys()) - balance_codes
    details_only_codes = set(details.keys()) - balance_codes

    if cost_only_codes:
        logger.warning(f"Custos encontrados para {len(cost_only_codes)} códigos de produto não presentes nos saldos: {list(cost_only_codes)[:10]}...")
    if details_only_codes:
        logger.warning(f"Detalhes encontrados para {len(details_only_codes)} códigos de produto não presentes nos saldos: {list(details_only_codes)[:10]}...")

    logger.info(f"Lista de tecidos construída com {len(fabric_list)} itens únicos.")
    return fabric_list

def filter_fabric_list(
    fabric_list: List[Dict[str, Any]],
    search_text: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Filtra a lista de tecidos com base no texto de pesquisa no campo 'description'.
    """
    if not search_text:
        logger.debug("Nenhum filtro de pesquisa fornecido para a lista de tecidos.")
        return fabric_list

    search_lower = search_text.lower()
    logger.debug(f"Filtrando lista de tecidos ({len(fabric_list)} itens) com o texto: '{search_text}'")

    filtered_list = [
        item for item in fabric_list
        if isinstance(item.get("description"), str) and search_lower in item["description"].lower()
    ]

    logger.info(f"Lista de tecidos filtrada para {len(filtered_list)} itens.")
    return filtered_list
