# src/services/fabric_service.py
# Contains business logic related to fetching and processing fabric (raw material) data.

import time
from typing import List, Dict, Any, Optional
from cachetools import TTLCache, cached

from src.domain.balance import ProductItem as BalanceItem # Use alias for clarity
from src.domain.cost import ProductCost
from src.domain.fabric_details import FabricDetailsItem
from src.erp_integration.erp_balance_service import ErpBalanceService
from src.erp_integration.erp_cost_service import ErpCostService
from src.erp_integration.erp_product_service import ErpProductService # For fabric details
from src.utils.fabric_list_builder import build_fabric_list, filter_fabric_list # Import builders
from src.utils.logger import logger
from src.api.errors import ServiceError, NotFoundError

# Cache configuration: 10 minutes TTL, max 10 entries (likely just 2: filtered/unfiltered)
# Note: This cache is instance-specific. If multiple instances run, caches are separate.
fabric_data_cache = TTLCache(maxsize=10, ttl=600) # 600 seconds = 10 minutes

# Helper function for cache key generation (handles None filter)
def _get_cache_key(search_filter: Optional[str]) -> str:
    return f"filter:{search_filter or '_NONE_'}"

class FabricService:
    """
    Service layer for handling fabric (raw material) related operations.
    Fetches data from ERP, combines it, and provides formatted lists with caching.
    """
    def __init__(self,
                 erp_balance_service: ErpBalanceService,
                 erp_cost_service: ErpCostService,
                 erp_product_service: ErpProductService):
        self.erp_balance_service = erp_balance_service
        self.erp_cost_service = erp_cost_service
        self.erp_product_service = erp_product_service # Inject product service for details
        logger.info("FabricService initialized.")

    def clear_fabric_cache(self):
        """Clears the fabric data cache."""
        logger.info("Clearing fabric data cache.")
        fabric_data_cache.clear()

    def get_fabrics(self, search_filter: Optional[str] = None, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieves a list of fabrics (raw materials) with balance, cost, and details,
        using a cache and optionally filtered by a search term.

        Args:
            search_filter: Text to filter fabrics by description (case-insensitive).
                           Filtering now happens AFTER fetching and caching.
            force_refresh: If True, bypasses the cache and fetches fresh data.

        Returns:
            A list of dictionaries, each representing a fabric with its data.

        Raises:
            ServiceError: If an error occurs during data retrieval or processing.
            NotFoundError: If no fabrics are found at all from the ERP.
        """
        cache_key = _get_cache_key(search_filter) # Use filter in cache key
        log_prefix = f"fabrics (Filter: '{search_filter or 'None'}', Force: {force_refresh})"
        logger.info(f"Fetching {log_prefix}...")

        if not force_refresh and cache_key in fabric_data_cache:
            logger.info(f"Cache hit for key '{cache_key}'. Returning cached fabric data.")
            # Return a copy to prevent modifying the cached list if filtering happens later
            return list(fabric_data_cache[cache_key])

        logger.info(f"Cache miss or force_refresh=True for key '{cache_key}'. Fetching fresh data from ERP.")
        try:
            # --- Fetch data (Core logic moved to a separate method for caching) ---
            full_fabric_list_unfiltered = self._fetch_and_build_fabrics()

            # --- Store in Cache BEFORE client-side filtering ---
            # We cache the full list based on the ERP filter (which is 'None' here)
            # Let's simplify: Cache only the unfiltered list (key '_NONE_')
            unfiltered_cache_key = _get_cache_key(None)
            fabric_data_cache[unfiltered_cache_key] = full_fabric_list_unfiltered
            logger.info(f"Stored {len(full_fabric_list_unfiltered)} fabrics in cache with key '{unfiltered_cache_key}'.")

            # --- Apply Client-Side Filter ---
            if search_filter:
                logger.debug(f"Applying client-side filter: '{search_filter}'")
                filtered_list = filter_fabric_list(full_fabric_list_unfiltered, search_filter)
                logger.info(f"Fabric list filtered client-side from {len(full_fabric_list_unfiltered)} to {len(filtered_list)} items.")
                return filtered_list
            else:
                # Return the full unfiltered list if no client-side filter
                return full_fabric_list_unfiltered


        except NotFoundError:
            logger.warning(f"No fabrics found in ERP for {log_prefix}.")
            raise # Re-raise NotFoundError
        except Exception as e:
            logger.error(f"Error retrieving {log_prefix}: {e}", exc_info=True)
            # Wrap generic errors in ServiceError
            raise ServiceError(f"Failed to retrieve fabric list: {e}") from e

    def _fetch_and_build_fabrics(self) -> List[Dict[str, Any]]:
        """Internal method to perform the actual ERP fetching and list building."""
        logger.debug("Fetching fabric balances from ERP...")
        # Fetch balances without ERP-side filtering based on text
        fabric_balances: List[BalanceItem] = self.erp_balance_service.get_balances(is_fabric=True)
        logger.debug(f"Fetched {len(fabric_balances)} balance items for fabrics.")

        if not fabric_balances:
            raise NotFoundError("No fabrics found in the ERP system.")

        logger.debug("Fetching fabric costs from ERP...")
        # Fetch costs without ERP-side filtering based on text
        fabric_costs: List[ProductCost] = self.erp_cost_service.get_costs(is_fabric=True)
        logger.debug(f"Fetched {len(fabric_costs)} cost items for fabrics.")

        logger.debug("Fetching fabric details (width, grammage, etc.) from ERP...")
        fabric_details_map: Dict[int, FabricDetailsItem] = self.erp_product_service.get_fabric_details()
        logger.debug(f"Fetched details for {len(fabric_details_map)} fabrics.")

        logger.debug("Building fabric list...")
        full_fabric_list = build_fabric_list(fabric_balances, fabric_costs, fabric_details_map)
        logger.debug(f"Built fabric list with {len(full_fabric_list)} items.")

        return full_fabric_list