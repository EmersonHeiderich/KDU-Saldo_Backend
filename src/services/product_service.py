# src/services/product_service.py
# Contains business logic related to fetching and processing product (finished goods) data.

from typing import List, Dict, Any, Optional
from src.domain.balance import ProductItem # Domain model for product balance item
from src.erp_integration.erp_balance_service import ErpBalanceService # ERP service for balances
from src.utils.matrix_builder import build_product_matrix # Utility for matrix structure
from src.utils.logger import logger
from src.api.errors import ServiceError, NotFoundError, ValidationError

class ProductService:
    """
    Service layer for handling finished product related operations, primarily balance information.
    """
    def __init__(self, erp_balance_service: ErpBalanceService):
        """
        Initializes the ProductService.

        Args:
            erp_balance_service: Instance of ErpBalanceService.
        """
        self.erp_balance_service = erp_balance_service
        logger.info("ProductService initialized.")

    def get_product_balance_matrix_with_items(self, reference_code: str, calculation_mode: str = 'base') -> Dict[str, Any]:
        """
        Retrieves product balance data for a reference code from the ERP,
        formats it into a matrix structure (color x size), and includes the raw items.

        Args:
            reference_code: The product reference code to query.
            calculation_mode: The balance calculation mode ('base', 'sales', 'production').

        Returns:
            A dictionary containing:
            {
                "reference_code": str,
                "calculation_mode": str,
                "matrix": Dict[str, Any], # The matrix structure from build_product_matrix
                "product_items": List[Dict[str, Any]] # Raw ProductItem data as dicts
            }

        Raises:
            ValidationError: If input parameters are invalid.
            NotFoundError: If no products are found for the reference code.
            ServiceError: If an error occurs during ERP communication or data processing.
        """
        if not reference_code:
            raise ValidationError("Product reference code cannot be empty.")
        if calculation_mode not in ['base', 'sales', 'production']:
            raise ValidationError(f"Invalid calculation mode: '{calculation_mode}'. Valid modes are 'base', 'sales', 'production'.")

        logger.info(f"Fetching balance matrix and items for reference '{reference_code}', mode '{calculation_mode}'.")

        try:
            logger.debug(f"Calling ERP balance service for reference code: {reference_code}")
            # Fetch balance items only for the specified reference code
            product_items: List[ProductItem] = self.erp_balance_service.get_balances(
                reference_code_list=[reference_code],
                is_fabric=False # Explicitly fetching finished products
            )

            if not product_items:
                logger.warning(f"No product items found in ERP for reference code: {reference_code}")
                raise NotFoundError(f"No products found for reference code '{reference_code}'.")

            logger.debug(f"Found {len(product_items)} product items for reference '{reference_code}'. Building matrix...")
            # Build the matrix structure using the utility function
            matrix_data = build_product_matrix(product_items, calculation_mode)
            logger.info(f"Successfully built balance matrix for reference '{reference_code}'.")

            # Convert product items to dictionaries for JSON response
            product_items_dict = [item.to_dict() for item in product_items]

            # Structure the final response payload including raw items
            response_data = {
                "reference_code": reference_code,
                "calculation_mode": calculation_mode,
                "matrix": matrix_data,
                "product_items": product_items_dict # Include the raw items
            }
            return response_data

        except (NotFoundError, ValidationError) as e:
             raise e # Re-raise specific errors
        except Exception as e:
            logger.error(f"Error getting product balance matrix for '{reference_code}': {e}", exc_info=True)
            # Wrap generic or ERP errors
            raise ServiceError(f"Failed to retrieve product balance matrix: {e}") from e