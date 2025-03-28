# src/utils/fabric_list_builder.py
# Utility functions for building and filtering the fabric list structure.

# Remove top-level domain imports causing cycle
# from src.domain.balance import ProductItem as BalanceItem
# from src.domain.cost import ProductCost
# from src.domain.fabric_details import FabricDetailsItem
from typing import List, Dict, Any, Optional, TYPE_CHECKING # Add TYPE_CHECKING
from src.utils.logger import logger

# Use TYPE_CHECKING block for type hints
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
    Builds a list of fabrics combining data from balance, cost, and details sources.

    Args:
        balances: A list of ProductItem objects containing balance info for fabrics.
        costs: A list of ProductCost objects containing cost info for fabrics.
        details: A dictionary mapping product_code to FabricDetailsItem objects.

    Returns:
        A list of dictionaries, each representing a fabric ready for API response.
    """
    # Import domain models inside the function
    from src.domain.balance import ProductItem as BalanceItem
    from src.domain.cost import ProductCost
    from src.domain.fabric_details import FabricDetailsItem

    logger.debug(f"Building fabric list from {len(balances)} balance items, {len(costs)} cost items, {len(details)} detail items.")

    # --- Data Preparation ---
    # Create dictionaries for faster lookups by product_code
    cost_map: Dict[int, ProductCost] = {cost.product_code: cost for cost in costs if isinstance(cost, ProductCost)}
    # Details map is already provided in the correct format.

    fabric_list: List[Dict[str, Any]] = []
    processed_codes = set() # Keep track of codes already processed

    # Iterate through balances as the primary source
    for balance_item in balances:
        # Ensure it's the correct type and not already processed
        if not isinstance(balance_item, BalanceItem) or balance_item.product_code in processed_codes:
            continue

        product_code = balance_item.product_code
        processed_codes.add(product_code)

        # --- Calculate Balance ---
        fabric_balance = 0
        if balance_item.balances:
             try:
                  # Using base balance calculation: stock + input - output
                  fabric_balance = balance_item.calculate_base_balance()
             except Exception as e:
                  logger.error(f"Error calculating balance for fabric {product_code}: {e}")
                  # Keep balance as 0
        else:
             logger.warning(f"Fabric {product_code} has no balance entries in balance data.")


        # --- Get Cost ---
        cost_value: Optional[float] = None
        cost_item = cost_map.get(product_code)
        if cost_item:
            try:
                cost_value = cost_item.get_primary_cost_value() # Uses helper method from domain model
            except Exception as e:
                logger.error(f"Error getting cost for fabric {product_code}: {e}")
        else:
             logger.debug(f"No cost data found for fabric {product_code}.")


        # --- Get Details ---
        details_item = details.get(product_code)
        width: Optional[float] = None
        grammage: Optional[float] = None
        shrinkage: Optional[float] = None
        if isinstance(details_item, FabricDetailsItem): # Check type before accessing attributes
            width = details_item.width
            grammage = details_item.grammage
            shrinkage = details_item.shrinkage
        elif details_item is not None: # Log if present but wrong type
             logger.warning(f"Found details for fabric {product_code}, but type is incorrect: {type(details_item)}")


        # --- Assemble Fabric Dictionary ---
        fabric_dict = {
            "code": product_code,
            "description": balance_item.product_name or "N/A", # Use balance item name
            "balance": fabric_balance,
            "cost": cost_value, # Will be None if not found
            "width": width,
            "grammage": grammage,
            "shrinkage": shrinkage
        }
        fabric_list.append(fabric_dict)

    # Log if there were costs/details for products not found in balances?
    balance_codes = {b.product_code for b in balances if isinstance(b, BalanceItem)}
    cost_only_codes = set(cost_map.keys()) - balance_codes
    details_only_codes = set(details.keys()) - balance_codes
    if cost_only_codes:
         logger.warning(f"Found costs for {len(cost_only_codes)} product codes not present in balances: {list(cost_only_codes)[:10]}...")
    if details_only_codes:
         logger.warning(f"Found details for {len(details_only_codes)} product codes not present in balances: {list(details_only_codes)[:10]}...")


    logger.info(f"Built fabric list with {len(fabric_list)} unique items.")
    return fabric_list

def filter_fabric_list(
    fabric_list: List[Dict[str, Any]],
    search_text: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Filters the provided list of fabric dictionaries based on a search text
    applied to the 'description' field (case-insensitive).

    Args:
        fabric_list: The list of fabric dictionaries to filter.
        search_text: The text to search for within the description. If None or empty,
                     the original list is returned.

    Returns:
        A new list containing only the fabrics that match the filter.
    """
    if not search_text:
        logger.debug("No search filter provided for fabric list.")
        return fabric_list # Return original list if no filter

    search_lower = search_text.lower()
    logger.debug(f"Filtering fabric list ({len(fabric_list)} items) with text: '{search_text}'")

    filtered_list = [
        item for item in fabric_list
        # Ensure 'description' exists and is a string before lower()
        if isinstance(item.get("description"), str) and search_lower in item["description"].lower()
    ]

    logger.info(f"Fabric list filtered down to {len(filtered_list)} items.")
    return filtered_list