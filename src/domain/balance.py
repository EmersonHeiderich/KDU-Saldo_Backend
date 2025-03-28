# src/domain/balance.py
# Defines data models related to product balances from the ERP.

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from src.utils.logger import logger # Use the application's configured logger

@dataclass(frozen=True)
class Balance:
    """
    Represents a single balance entry for a product variant. Immutable.

    Corresponds to an item within the 'balances' list in the ERP API response.
    """
    branch_code: int
    stock_code: int
    stock_description: str
    stock: int = 0
    sales_order: int = 0
    input_transaction: int = 0
    output_transaction: int = 0
    production_order_progress: int = 0
    production_order_wait_lib: int = 0
    stock_temp: Optional[int] = None
    production_planning: Optional[int] = None
    purchase_order: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Balance object to a dictionary."""
        return self.__dict__ # Dataclasses provide __dict__

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Balance':
        """Creates a Balance object from a dictionary (e.g., from API)."""
        if not isinstance(data, dict):
            logger.error(f"Invalid data type for Balance.from_dict: {type(data)}")
            raise ValueError("Invalid data format for Balance")
        return cls(
            branch_code=data.get('branchCode', 0),
            stock_code=data.get('stockCode', 0),
            stock_description=data.get('stockDescription', ''),
            stock=data.get('stock', 0),
            sales_order=data.get('salesOrder', 0),
            input_transaction=data.get('inputTransaction', 0),
            output_transaction=data.get('outputTransaction', 0),
            production_order_progress=data.get('productionOrderProgress', 0),
            production_order_wait_lib=data.get('productionOrderWaitLib', 0),
            stock_temp=data.get('stockTemp'),
            production_planning=data.get('productionPlanning'),
            purchase_order=data.get('purchaseOrder')
        )

@dataclass(frozen=True)
class ProductItem:
    """
    Represents a product variant (SKU) with its details and balances. Immutable.

    Corresponds to an item within the 'items' list in the ERP API balance response.
    """
    product_code: int
    product_name: str
    product_sku: str
    reference_code: str
    color_code: str
    color_name: str
    size_name: str
    balances: List[Balance] = field(default_factory=list)
    locations: Optional[List[Any]] = None # Type hint could be more specific if structure is known
    max_change_filter_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts the ProductItem object to a dictionary."""
        return {
            **self.__dict__, # Get base attributes
            'balances': [b.to_dict() for b in self.balances] # Convert nested balances
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProductItem':
        """Creates a ProductItem object from a dictionary (e.g., from API)."""
        if not isinstance(data, dict):
            logger.error(f"Invalid data type for ProductItem.from_dict: {type(data)}")
            raise ValueError("Invalid data format for ProductItem")

        balances_data = data.get('balances', [])
        if not isinstance(balances_data, list):
             logger.warning(f"Invalid 'balances' format in ProductItem data for product {data.get('productCode')}. Expected list, got {type(balances_data)}.")
             balances = []
        else:
             balances = [Balance.from_dict(b_data) for b_data in balances_data if isinstance(b_data, dict)]

        return cls(
            product_code=data.get('productCode', 0),
            product_name=data.get('productName', ''),
            product_sku=data.get('productSku', ''),
            reference_code=data.get('referenceCode', ''),
            color_code=data.get('colorCode', ''),
            color_name=data.get('colorName', ''),
            size_name=data.get('sizeName', ''),
            balances=balances,
            locations=data.get('locations'),
            max_change_filter_date=data.get('maxChangeFilterDate')
        )

    # --- Balance Calculation Methods ---
    # These methods assume the relevant balance data is in the *first* Balance object
    # in the balances list, which seems to be the pattern in the original code.
    # Consider adding checks or making this assumption explicit.

    def _get_primary_balance(self) -> Optional[Balance]:
        """Helper to get the primary balance object (first in the list)."""
        if self.balances:
            return self.balances[0]
        logger.warning(f"ProductItem {self.product_code} has no balance data.")
        return None

    def calculate_base_balance(self) -> int:
        """Calculates base balance: stock + input - output."""
        balance = self._get_primary_balance()
        if balance:
            return balance.stock + balance.input_transaction - balance.output_transaction
        return 0

    def calculate_sales_balance(self) -> int:
        """Calculates balance considering sales orders: base_balance - sales_order."""
        balance = self._get_primary_balance()
        if balance:
            return self.calculate_base_balance() - balance.sales_order
        return 0

    def calculate_production_balance(self) -> int:
        """Calculates balance considering sales and production: base_balance - sales + production."""
        balance = self._get_primary_balance()
        if balance:
            return (self.calculate_base_balance() - balance.sales_order +
                    balance.production_order_progress + balance.production_order_wait_lib)
        return 0

    def get_balance_for_mode(self, mode: str) -> int:
        """
        Returns the calculated balance based on the specified mode.

        Args:
            mode: Calculation mode ('base', 'sales', 'production').

        Returns:
            The calculated balance value.

        Raises:
            ValueError: If the mode is unrecognized.
        """
        if mode == 'base':
            return self.calculate_base_balance()
        elif mode == 'sales':
            return self.calculate_sales_balance()
        elif mode == 'production':
            return self.calculate_production_balance()
        else:
            logger.error(f"Unrecognized balance calculation mode: {mode}")
            raise ValueError(f"Unrecognized balance calculation mode: {mode}")


@dataclass(frozen=True)
class ProductResponse:
    """
    Represents the overall structure of the balance API response. Immutable.
    """
    count: int
    total_pages: int
    has_next: bool
    total_items: int
    items: List[ProductItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the ProductResponse object to a dictionary."""
        return {
             **self.__dict__,
            'items': [item.to_dict() for item in self.items]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProductResponse':
        """
        Creates a ProductResponse object from the raw API response dictionary.

        Args:
            data: The dictionary parsed from the API JSON response.

        Returns:
            A ProductResponse object.

        Raises:
            ValueError: If the input data is not a dictionary or has invalid format.
        """
        if not isinstance(data, dict):
            logger.error(f"Invalid data type for ProductResponse.from_dict: {type(data)}")
            raise ValueError("Invalid data format for ProductResponse")

        items_data = data.get('items', [])
        if not isinstance(items_data, list):
            logger.warning(f"Invalid 'items' format in ProductResponse data. Expected list, got {type(items_data)}.")
            items = []
        else:
            items = []
            for item_data in items_data:
                 if isinstance(item_data, dict):
                     try:
                         items.append(ProductItem.from_dict(item_data))
                     except ValueError as e:
                          logger.error(f"Skipping invalid item in ProductResponse: {e} - Data: {item_data}")
                 else:
                     logger.warning(f"Skipping non-dict item in ProductResponse items list: {item_data}")


        return cls(
            count=data.get('count', 0),
            total_pages=data.get('totalPages', 0),
            has_next=data.get('hasNext', False),
            total_items=data.get('totalItems', 0),
            items=items
        )