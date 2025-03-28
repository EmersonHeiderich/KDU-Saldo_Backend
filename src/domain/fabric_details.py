# src/domain/fabric_details.py
# Defines data models related to fabric-specific details (width, grammage, etc.) from the ERP.
# Renamed from original product_model.py for clarity.

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from src.utils.logger import logger

@dataclass(frozen=True)
class FabricDetailValue:
    """
    Represents a single additional field value for a fabric. Immutable.

    Corresponds to an item in the 'additionalFields' list in the ERP Product API response.
    """
    code: int # Field code (e.g., 1=Width, 2=Grammage, 3=Shrinkage)
    name: str # Field name (provided by ERP)
    value: Any # Field value (can be string, number, etc.)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the FabricDetailValue object to a dictionary."""
        return self.__dict__

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional['FabricDetailValue']:
        """Creates a FabricDetailValue from a dictionary, returns None if invalid."""
        if not isinstance(data, dict):
            logger.warning(f"Invalid data type for FabricDetailValue.from_dict: {type(data)}")
            return None
        try:
            # Basic validation
            code = int(data.get('code'))
            name = str(data.get('name', ''))
            value = data.get('value') # Keep original type for flexibility
            return cls(code=code, name=name, value=value)
        except (TypeError, ValueError, KeyError) as e:
            logger.error(f"Error creating FabricDetailValue from dict: {e}. Data: {data}")
            return None


@dataclass(frozen=True)
class FabricDetailsItem:
    """
    Represents a fabric product with its specific details (width, grammage, shrinkage). Immutable.

    Derived from the ERP Product API response, focusing on relevant additional fields.
    """
    product_code: int
    width: Optional[float] = None      # Largura (Code 1)
    grammage: Optional[float] = None   # Gramatura (Code 2)
    shrinkage: Optional[float] = None  # Encolhimento (Code 3)
    # Add other relevant fields if needed from the base product data
    # product_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts the FabricDetailsItem object to a dictionary."""
        return self.__dict__

    @classmethod
    def from_product_api_item(cls, item_data: Dict[str, Any]) -> Optional['FabricDetailsItem']:
        """
        Creates a FabricDetailsItem from a single item dictionary from the ERP Product API response.

        Args:
            item_data: Dictionary representing one product item from the ERP API.

        Returns:
            A FabricDetailsItem object or None if essential data is missing or invalid.
        """
        if not isinstance(item_data, dict):
            logger.warning(f"Invalid item_data type for FabricDetailsItem: {type(item_data)}")
            return None

        product_code = item_data.get('productCode')
        if not product_code:
            logger.warning("Skipping item in FabricDetailsItem creation: missing productCode.")
            return None

        additional_fields_data = item_data.get('additionalFields', [])
        if not isinstance(additional_fields_data, list):
            logger.warning(f"Invalid 'additionalFields' format for product {product_code}. Expected list.")
            additional_fields_data = []

        width = None
        grammage = None
        shrinkage = None

        for field_data in additional_fields_data:
            field_obj = FabricDetailValue.from_dict(field_data)
            if field_obj and field_obj.value is not None: # Check if value exists
                try:
                    if field_obj.code == 1:  # Largura
                        width = float(field_obj.value)
                    elif field_obj.code == 2:  # Gramatura
                        grammage = float(field_obj.value)
                    elif field_obj.code == 3:  # Encolhimento
                        shrinkage = float(field_obj.value)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not convert fabric detail value for product {product_code}, field code {field_obj.code}. Value: '{field_obj.value}', Error: {e}")

        return cls(
            product_code=product_code,
            width=width,
            grammage=grammage,
            shrinkage=shrinkage
            # product_name=item_data.get('productName') # Optionally include name
        )

# Note: The overall Product Response structure for the /products/search endpoint
# is similar to Balance/Cost responses, but might have slightly different fields.
# If needed, a dedicated FabricDetailsResponse dataclass could be created,
# similar to ProductResponse or CostResponse. For now, the erp_product_service
# might just return a list of FabricDetailsItem.