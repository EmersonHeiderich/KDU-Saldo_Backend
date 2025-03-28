# src/api/routes/customer_panel.py (Continued)
# Defines API endpoints for accessing customer data and statistics.

from flask import Blueprint, request, jsonify, current_app
from src.services.customer_service import CustomerService # Import the specific service
from src.erp_integration.erp_person_service import ErpPersonService # Needed to instantiate service
from src.erp_integration import erp_auth_service # Need auth for ERP service
from src.api.decorators import login_required, customer_panel_access_required # Import decorators
from src.api.errors import ApiError, NotFoundError, ValidationError # Import custom errors
from src.utils.logger import logger

customer_panel_bp = Blueprint('customer_panel', __name__)

# Helper function to instantiate or get the CustomerService
# This could be improved with a proper dependency injection framework later
def _get_customer_service() -> CustomerService:
     erp_person_svc = ErpPersonService(erp_auth_service) # Use singleton ERP auth
     # Simple instantiation:
     return CustomerService(erp_person_svc)

@customer_panel_bp.route('/data', methods=['POST'])
@login_required
@customer_panel_access_required
def get_customer_data():
    """
    Fetches customer master data (Individual or Legal Entity) based on search criteria.
    ---
    tags: [Customer Panel]
    security:
      - bearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              search_term:
                type: string
                description: "Customer Code, CPF (11 digits), or CNPJ (14 digits)"
                example: "12345"
              search_type:
                type: string
                description: "'PF' or 'PJ'. Required only if search_term is a Customer Code."
                example: "PF"
            required: [search_term]
    responses:
      200:
        description: Customer data found
        content:
          application/json:
            schema:
              # Define schema based on CustomerService._format_customer_data output
              type: object
              properties:
                 customer_type: {type: string, enum: [PF, PJ]}
                 code: {type: integer}
                 name: {type: string, description: "Name (PF) or Legal Name (PJ)"}
                 # ... other common and specific fields ...
      400:
        description: Bad request (Invalid JSON, missing fields, invalid search term format)
      401:
        description: Unauthorized
      403:
        description: Forbidden (User lacks permission)
      404:
        description: Customer not found
      500:
        description: Internal server error or ERP integration error
    """
    logger.info("Customer data request received.")
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    search_term = data.get('search_term')
    search_type = data.get('search_type') # Optional

    if not search_term:
        return jsonify({"error": "Field 'search_term' is required"}), 400

    try:
        customer_service = _get_customer_service()
        customer_details = customer_service.get_customer_details(str(search_term).strip(), search_type)
        return jsonify(customer_details), 200

    except ValidationError as e:
        logger.warning(f"Validation error fetching customer data: {e}")
        return jsonify({"error": str(e)}), 400
    except NotFoundError as e:
        logger.warning(f"Customer not found for search term '{search_term}': {e}")
        return jsonify({"error": str(e)}), 404
    except ApiError as e: # Catch specific internal/ERP errors
         logger.error(f"API error fetching customer data for '{search_term}': {e.message}", exc_info=False) # Don't need full stack for known API errors
         return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error fetching customer data for '{search_term}': {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500


@customer_panel_bp.route('/statistics', methods=['GET'])
@login_required
@customer_panel_access_required
def get_customer_statistics():
    """
    Fetches financial statistics for a given customer code.
    ---
    tags: [Customer Panel]
    security:
      - bearerAuth: []
    parameters:
      - in: query
        name: customer_code
        schema:
          type: integer
        required: true
        description: The code of the customer.
    responses:
      200:
        description: Customer statistics found
        content:
          application/json:
            schema:
              # Define schema based on CustomerService._format_statistics output
              type: object
              properties:
                 average_delay_days: {type: integer, nullable: true}
                 # ... other statistics fields ...
      400:
        description: Bad request (Missing or invalid customer_code)
      401:
        description: Unauthorized
      403:
        description: Forbidden (User lacks permission)
      404:
        description: Statistics not found for the customer
      500:
        description: Internal server error or ERP integration error
    """
    logger.info("Customer statistics request received.")
    customer_code_str = request.args.get('customer_code')

    if not customer_code_str:
        return jsonify({"error": "Query parameter 'customer_code' is required"}), 400

    try:
        customer_code = int(customer_code_str)
    except (ValueError, TypeError):
        return jsonify({"error": "Query parameter 'customer_code' must be an integer"}), 400

    try:
        # Get current user details for permission checks/logic if needed
        current_user = request.current_user # Set by @login_required
        is_admin = current_user.permissions.is_admin if current_user and current_user.permissions else False

        customer_service = _get_customer_service()
        statistics = customer_service.get_customer_statistics(customer_code, is_admin)
        return jsonify(statistics), 200

    except NotFoundError as e:
        logger.warning(f"Statistics not found for customer code {customer_code}: {e}")
        return jsonify({"error": str(e)}), 404
    except ApiError as e: # Catch specific internal/ERP errors
         logger.error(f"API error fetching statistics for customer {customer_code}: {e.message}", exc_info=False)
         return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error fetching statistics for customer {customer_code}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500