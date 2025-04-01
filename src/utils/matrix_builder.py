# src/utils/matrix_builder.py
# Utility functions for building the product balance matrix structure.

import re
from typing import List, Dict, Any, Tuple, Set, Optional, TYPE_CHECKING
from src.utils.logger import logger

# Use type checking block for type hints if needed at module level (optional but good practice)
if TYPE_CHECKING:
    from src.domain.balance import ProductItem


def build_product_matrix(products: List['ProductItem'], calculation_mode: str = 'base') -> Dict[str, Any]:
    """
    Builds a matrix of product balances organized by color and size.

    Args:
        products: A list of ProductItem objects for a single reference code.
        calculation_mode: The balance calculation mode ('base', 'sales', 'production').

    Returns:
        A dictionary containing the matrix structure:
        {
            "colors": [{"code": str, "name": str}, ...],
            "sizes": [str, ...],
            "values": { color_code: { size_name: {"value": int, "status": str, "product_code": int|None} } },
            "totals": {"base_balance": int, "sales_orders": int, "in_production": int}
        }

    Raises:
        ValueError: If calculation_mode is invalid or products list is malformed.
    """
    # Import here instead of top-level
    from src.domain.balance import ProductItem

    if not products:
        logger.warning("build_product_matrix called with empty product list.")
        return {"colors": [], "sizes": [], "values": {}, "totals": {"base_balance": 0, "sales_orders": 0, "in_production": 0}}

    if calculation_mode not in ['base', 'sales', 'production']:
        raise ValueError(f"Invalid calculation_mode: {calculation_mode}")

    logger.debug(f"Building matrix for {len(products)} product items, mode '{calculation_mode}'.")

    # --- Extract unique dimensions ---
    color_set: Set[Tuple[str, str]] = set()
    size_set: Set[str] = set()
    product_map: Dict[Tuple[str, str], ProductItem] = {} # Key: (color_code, size_name)

    for p in products:
        if not p or not p.color_code or not p.size_name:
             logger.warning(f"Skipping invalid ProductItem in matrix build: {p}")
             continue
        # Ensure ProductItem type before accessing attributes
        if not isinstance(p, ProductItem):
             logger.warning(f"Skipping item with unexpected type {type(p)} in matrix build.")
             continue
        color_set.add((p.color_code, p.color_name or p.color_code)) # Use code if name missing
        size_set.add(p.size_name)
        product_map[(p.color_code, p.size_name)] = p

    # --- Sort dimensions ---
    sorted_colors = sorted(list(color_set), key=lambda c: c[0]) # Sort by color code
    sorted_sizes = _smart_sort_sizes(list(size_set))

    # --- Initialize matrix structure ---
    matrix: Dict[str, Any] = {
        "colors": [{"code": code, "name": name} for code, name in sorted_colors],
        "sizes": sorted_sizes,
        "values": {}
    }

    # --- Populate matrix values ---
    for color_code, color_name in sorted_colors:
        matrix["values"][color_code] = {}
        for size_name in sorted_sizes:
            product = product_map.get((color_code, size_name))
            value = 0
            status = "critical" # Default if product not found
            product_code_for_cell: Optional[int] = None

            if product:
                try:
                     value = product.get_balance_for_mode(calculation_mode)
                     status = _determine_status(value)
                     product_code_for_cell = product.product_code
                except ValueError as e:
                     logger.error(f"Error calculating balance for {product.product_code}: {e}")
                     value = 0
                     status = "error"
                except Exception as e:
                     logger.error(f"Unexpected error processing product {product.product_code}: {e}", exc_info=True)
                     value = 0
                     status = "error"
            else:
                logger.debug(f"No product variant found for Color={color_code}, Size={size_name}.")


            matrix["values"][color_code][size_name] = {
                "value": value,
                "status": status,
                "product_code": product_code_for_cell
            }

    # --- Calculate Totals ---
    totals = _calculate_totals(products)
    matrix["totals"] = totals

    logger.debug("Matrix build complete.")
    return matrix

def _calculate_totals(products: List['ProductItem']) -> Dict[str, int]:
    """Calculates aggregated totals across all provided product items."""
    # Import here as well if using the type hint strictly
    from src.domain.balance import ProductItem

    total_base_balance = 0
    total_sales_orders = 0
    total_in_production = 0

    for product in products:
        # Check type consistency
        if not isinstance(product, ProductItem):
             logger.warning(f"Skipping item with unexpected type {type(product)} in totals calculation.")
             continue

        if product.balances:
            # Use the calculation methods from the ProductItem model
            total_base_balance += product.calculate_base_balance()

            # Access the primary balance entry for raw values
            primary_balance = product._get_primary_balance() # Use internal helper
            if primary_balance:
                 total_sales_orders += primary_balance.sales_order
                 total_in_production += (primary_balance.production_order_progress +
                                         primary_balance.production_order_wait_lib)
        else:
            logger.warning(f"Product {product.product_code} included in totals calculation but has no balance data.")


    return {
        "base_balance": total_base_balance,
        "sales_orders": total_sales_orders,
        "in_production": total_in_production
    }

def _smart_sort_sizes(sizes: List[str]) -> List[str]:
    """
    Sorts sizes intelligently, handling numeric parts and common non-numeric sizes.
    Example Order: PP, P, M, G, GG, XG, 36, 38, 40, 42, UNICO.
    """
    def sort_key(size: str) -> Tuple[int, int, str]:
        size_upper = size.upper()

        # 1. Priority for common non-numeric sizes
        order_map = {"RN": 0, "BB": 1, "PP": 10, "P": 20, "M": 30, "G": 40, "GG": 50, "XG": 60, "EG": 70, "EGG": 80, "UN": 999, "UNICO": 999}
        if size_upper in order_map:
            return (1, order_map[size_upper], size_upper) # Group 1, order within group, original string

        # 2. Priority for purely numeric sizes
        if size_upper.isdigit():
            try:
                return (2, int(size_upper), size_upper) # Group 2, numeric value, original string
            except ValueError:
                 pass # Should not happen if isdigit() is true

        # 3. Priority for sizes with leading numbers (e.g., "1 ANO", "2 ANOS")
        match_lead_num = re.match(r'(\d+)\s*(.*)', size_upper)
        if match_lead_num:
             try:
                  num_part = int(match_lead_num.group(1))
                  return (3, num_part, size_upper) # Group 3, numeric part, original string
             except ValueError:
                  pass

        # 4. Default: Alphanumeric sort for anything else
        return (9999, 0, size_upper) # Last group, default order 0, original string


    try:
        return sorted(sizes, key=sort_key)
    except Exception as e:
        logger.error(f"Error during smart size sort: {e}. Falling back to simple sort.", exc_info=True)
        # Fallback to simple alphanumeric sort on error
        return sorted(sizes)


def _determine_status(value: int) -> str:
    """
    Determines a status string based on the balance value.
    Thresholds can be adjusted here.
    """
    if value <= 0:
        return "critical"
    elif value < 10: # Example threshold for 'low'
        return "low"
    else:
        return "sufficient"