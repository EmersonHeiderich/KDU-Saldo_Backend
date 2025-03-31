# src/api/routes/products.py
# Routes related to finished product information.

from flask import Blueprint, request, jsonify, current_app
from src.services.product_service import ProductService
from src.api.decorators import login_required, products_access_required
from src.api.errors import ApiError, NotFoundError, ValidationError, ServiceError
from src.utils.logger import logger

# --- Get Service Instances ---
def _get_product_service() -> ProductService:
    service = current_app.config.get('product_service')
    if not service:
        logger.critical("ProductService not found in application config!")
        raise ServiceError("Product service is unavailable.", 503)
    return service

# --- Blueprint Definition ---
products_bp = Blueprint('products', __name__)

# --- Routes ---

@products_bp.route('/balance_matrix', methods=['POST'])
@login_required
@products_access_required
def get_product_balance_matrix():
    """
    Gets the product balance matrix for a given reference code and calculation mode.
    Also returns the raw product items used to build the matrix.
    ---
    tags:
      - Products
    security:
      - bearerAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - reference_code
          properties:
            reference_code:
              type: string
              description: The product reference code.
              example: "1010"
            calculation_mode:
              type: string
              description: Balance calculation mode ('base', 'sales', 'production'). Defaults to 'base'.
              example: "sales"
              enum: ["base", "sales", "production"]
    responses:
      200:
        description: Product balance matrix and raw items.
        schema:
          # Define the expected response structure here (matching ProductService return)
          type: object
          properties:
             reference_code:
               type: string
             calculation_mode:
               type: string
             matrix:
               # Define matrix structure (simplified example)
               type: object
             product_items:
               # Define product items structure (simplified example)
               type: array
               items:
                 type: object
      400:
        description: Invalid input (e.g., missing reference code, invalid mode).
      401:
        description: Authentication required.
      403:
        description: Permission denied.
      404:
        description: Product reference not found.
      500:
        description: Internal server error or error fetching data from ERP.
      503:
        description: Service unavailable.
    """
    data = request.get_json()
    if not data or not data.get('reference_code'):
        return jsonify({"error": "Campo 'reference_code' é obrigatório."}), 400

    reference_code = str(data.get('reference_code')).strip().upper()
    calculation_mode = str(data.get('calculation_mode', 'base')).lower()

    logger.info(f"Balance matrix request: Ref={reference_code}, Mode={calculation_mode}")

    try:
        product_service = _get_product_service()
        # Call the updated service method
        result = product_service.get_product_balance_matrix_with_items(reference_code, calculation_mode)
        return jsonify(result), 200

    except (ValidationError, NotFoundError) as e:
        logger.warning(f"Product matrix request failed (Ref: {reference_code}): {e}")
        status = 400 if isinstance(e, ValidationError) else 404
        return jsonify({"error": str(e)}), status
    except (ServiceError, ApiError) as e:
        logger.error(f"Service error fetching product matrix (Ref: {reference_code}): {e}", exc_info=True)
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error fetching product matrix (Ref: {reference_code}): {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred."}), 500