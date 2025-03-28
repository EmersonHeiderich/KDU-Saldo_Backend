# src/domain/cost.py
# Defines data models related to product costs from the ERP.

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from src.utils.logger import logger # Use the application's configured logger

@dataclass(frozen=True)
class Cost:
    """
    Represents a single cost entry for a product variant. Immutable.

    Corresponds to an item within the 'costs' list in the ERP API response.
    """
    branch_code: int
    cost_code: int
    cost_name: str
    cost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Cost object to a dictionary."""
        return self.__dict__

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Cost':
        """Creates a Cost object from a dictionary (e.g., from API)."""
        if not isinstance(data, dict):
            logger.error(f"Invalid data type for Cost.from_dict: {type(data)}")
            raise ValueError("Invalid data format for Cost")
        return cls(
            branch_code=data.get('branchCode', 0),
            cost_code=data.get('costCode', 0),
            cost_name=data.get('costName', ''),
            cost=data.get('cost', 0.0) # Ensure float conversion if necessary
        )

@dataclass(frozen=True)
class ProductCost:
    """
    Represents a product variant (SKU) with its details and costs. Immutable.

    Corresponds to an item within the 'items' list in the ERP API cost response.
    """
    product_code: int
    product_name: str
    product_sku: str
    reference_code: str
    color_code: str
    color_name: str
    size_name: str
    costs: List[Cost] = field(default_factory=list)
    max_change_filter_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts the ProductCost object to a dictionary."""
        return {
            **self.__dict__,
            'costs': [c.to_dict() for c in self.costs]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProductCost':
        """Creates a ProductCost object from a dictionary (e.g., from API)."""
        if not isinstance(data, dict):
            logger.error(f"Invalid data type for ProductCost.from_dict: {type(data)}")
            raise ValueError("Invalid data format for ProductCost")

        costs_data = data.get('costs', [])
        if not isinstance(costs_data, list):
            logger.warning(f"Invalid 'costs' format in ProductCost data for product {data.get('productCode')}. Expected list, got {type(costs_data)}.")
            costs = []
        else:
            costs = [Cost.from_dict(c_data) for c_data in costs_data if isinstance(c_data, dict)]

        return cls(
            product_code=data.get('productCode', 0),
            product_name=data.get('productName', ''),
            product_sku=data.get('productSku', ''),
            reference_code=data.get('referenceCode', ''),
            color_code=data.get('colorCode', ''),
            color_name=data.get('colorName', ''),
            size_name=data.get('sizeName', ''),
            costs=costs,
            max_change_filter_date=data.get('maxChangeFilterDate')
        )

    def get_primary_cost_value(self) -> float:
        """
        Returns the value of the primary cost (first in the list).

        Returns:
            Cost value (float) or 0.0 if no costs are available.
        """
        if self.costs:
            return self.costs[0].cost
        logger.warning(f"ProductCost {self.product_code} has no cost data.")
        return 0.0

@dataclass(frozen=True)
class CostResponse:
    """
    Represents the overall structure of the cost API response. Immutable.
    """
    count: int
    total_pages: int
    has_next: bool
    total_items: int
    items: List[ProductCost] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the CostResponse object to a dictionary."""
        return {
             **self.__dict__,
            'items': [item.to_dict() for item in self.items]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CostResponse':
        """
        Creates a CostResponse object from the raw API response dictionary.

        Args:
            data: The dictionary parsed from the API JSON response.

        Returns:
            A CostResponse object.

        Raises:
            ValueError: If the input data is not a dictionary or has invalid format.
        """
        if not isinstance(data, dict):
            logger.error(f"Invalid data type for CostResponse.from_dict: {type(data)}")
            raise ValueError("Invalid data format for CostResponse")

        items_data = data.get('items', [])
        if not isinstance(items_data, list):
             logger.warning(f"Invalid 'items' format in CostResponse data. Expected list, got {type(items_data)}.")
             items = []
        else:
            items = []
            for item_data in items_data:
                 if isinstance(item_data, dict):
                      try:
                          items.append(ProductCost.from_dict(item_data))
                      except ValueError as e:
                           logger.error(f"Skipping invalid item in CostResponse: {e} - Data: {item_data}")
                 else:
                      logger.warning(f"Skipping non-dict item in CostResponse items list: {item_data}")

        return cls(
            count=data.get('count', 0),
            total_pages=data.get('totalPages', 0),
            has_next=data.get('hasNext', False),
            total_items=data.get('totalItems', 0),
            items=items
        )
