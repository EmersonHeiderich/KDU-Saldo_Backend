# src/utils/matrix_builder.py
import re
from typing import List, Dict, Any, Tuple, Set, Optional, TYPE_CHECKING
from src.utils.logger import logger

if TYPE_CHECKING:
    from src.domain.balance import ProductItem

def build_product_matrix(products: List['ProductItem'], calculation_mode: str = 'base') -> Dict[str, Any]:
    from src.domain.balance import ProductItem

    if not products:
        logger.warning("build_product_matrix chamado com lista de produtos vazia.")
        return {"colors": [], "sizes": [], "values": {}, "totals": {"base_balance": 0, "sales_orders": 0, "in_production": 0}}

    if calculation_mode not in ['base', 'sales', 'production']:
        raise ValueError(f"Modo de cálculo inválido: {calculation_mode}")

    logger.debug(f"Construindo matriz para {len(products)} itens de produto, modo '{calculation_mode}'.")

    color_set: Set[Tuple[str, str]] = set()
    size_set: Set[str] = set()
    product_map: Dict[Tuple[str, str], ProductItem] = {}

    for p in products:
        if not p or not p.color_code or not p.size_name:
            logger.warning(f"Ignorando ProductItem inválido na construção da matriz: {p}")
            continue
        if not isinstance(p, ProductItem):
            logger.warning(f"Ignorando item com tipo inesperado {type(p)} na construção da matriz.")
            continue
        color_set.add((p.color_code, p.color_name or p.color_code))
        size_set.add(p.size_name)
        product_map[(p.color_code, p.size_name)] = p

    sorted_colors = sorted(list(color_set), key=lambda c: c[0])
    sorted_sizes = _smart_sort_sizes(list(size_set))

    matrix: Dict[str, Any] = {
        "colors": [{"code": code, "name": name} for code, name in sorted_colors],
        "sizes": sorted_sizes,
        "values": {}
    }

    for color_code, color_name in sorted_colors:
        matrix["values"][color_code] = {}
        for size_name in sorted_sizes:
            product = product_map.get((color_code, size_name))
            value = 0
            status = "critical"
            product_code_for_cell: Optional[int] = None

            if product:
                try:
                    value = product.get_balance_for_mode(calculation_mode)
                    status = _determine_status(value)
                    product_code_for_cell = product.product_code
                except ValueError as e:
                    logger.error(f"Erro ao calcular saldo para {product.product_code}: {e}")
                    status = "error"
                except Exception as e:
                    logger.error(f"Erro inesperado ao processar produto {product.product_code}: {e}", exc_info=True)
                    status = "error"
            else:
                logger.debug(f"Nenhuma variante de produto encontrada para Cor={color_code}, Tamanho={size_name}.")

            matrix["values"][color_code][size_name] = {
                "value": value,
                "status": status,
                "product_code": product_code_for_cell
            }

    matrix["totals"] = _calculate_totals(products)
    logger.debug("Construção da matriz concluída.")
    return matrix

def _calculate_totals(products: List['ProductItem']) -> Dict[str, int]:
    from src.domain.balance import ProductItem

    total_base_balance = 0
    total_sales_orders = 0
    total_in_production = 0

    for product in products:
        if not isinstance(product, ProductItem):
            logger.warning(f"Ignorando item com tipo inesperado {type(product)} no cálculo dos totais.")
            continue

        if product.balances:
            total_base_balance += product.calculate_base_balance()
            primary_balance = product._get_primary_balance()
            if primary_balance:
                total_sales_orders += primary_balance.sales_order
                total_in_production += (primary_balance.production_order_progress + primary_balance.production_order_wait_lib)
        else:
            logger.warning(f"Produto {product.product_code} incluído no cálculo dos totais, mas sem dados de saldo.")

    return {
        "base_balance": total_base_balance,
        "sales_orders": total_sales_orders,
        "in_production": total_in_production
    }

def _smart_sort_sizes(sizes: List[str]) -> List[str]:
    def sort_key(size: str) -> Tuple[int, int, str]:
        size_upper = size.upper()
        order_map = {"RN": 0, "BB": 1, "PP": 10, "P": 20, "M": 30, "G": 40, "GG": 50, "XG": 60, "EG": 70, "EGG": 80, "UN": 999, "UNICO": 999}
        if size_upper in order_map:
            return (1, order_map[size_upper], size_upper)
        if size_upper.isdigit():
            return (2, int(size_upper), size_upper)
        match_lead_num = re.match(r'(\d+)\s*(.*)', size_upper)
        if match_lead_num:
            return (3, int(match_lead_num.group(1)), size_upper)
        return (9999, 0, size_upper)

    try:
        return sorted(sizes, key=sort_key)
    except Exception as e:
        logger.error(f"Erro ao ordenar tamanhos: {e}. Usando ordenação alfanumérica padrão.", exc_info=True)
        return sorted(sizes)

def _determine_status(value: int) -> str:
    if value <= 0:
        return "critical"
    elif value < 10:
        return "low"
    else:
        return "sufficient"
