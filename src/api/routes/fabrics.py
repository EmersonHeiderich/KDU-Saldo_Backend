# src/api/routes/fabrics.py
# Routes related to fabric information.

from flask import Blueprint, request, jsonify, current_app
from src.services.fabric_service import FabricService
from src.services.auth_service import AuthService
from src.api.decorators import login_required, fabrics_access_required
from src.api.errors import ApiError, NotFoundError, ServiceError
from src.utils.logger import logger

# --- Get Service Instances ---
# Helper functions to get services from app context
def _get_fabric_service() -> FabricService:
    service = current_app.config.get('fabric_service')
    if not service:
        logger.critical("FabricService not found in application config!")
        raise ServiceError("Fabric service is unavailable.", 503)
    return service

# --- Blueprint Definition ---
fabrics_bp = Blueprint('fabrics', __name__)

# --- Routes ---

@fabrics_bp.route('/balances', methods=['POST'])
@login_required
@fabrics_access_required
def get_fabric_balances():
    """
    Endpoint to get fabric balances, costs, and details.
    Accepts optional 'filter' and 'force_refresh' in JSON body.
    ---
    tags:
      - Fabrics
    security:
      - bearerAuth: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          properties:
            filter:
              type: string
              description: Optional text to filter fabrics by description/code (client-side).
              example: "JEANS"
            force_refresh:
              type: boolean
              description: If true, bypasses the cache and fetches fresh data.
              example: false
    responses:
      200:
        description: List of fabrics with balance, cost, and details.
        schema:
          type: object
          properties:
            fabrics:
              type: array
              items:
                type: object
                properties:
                  code:
                    type: integer
                  description:
                    type: string
                  balance:
                    type: integer
                  cost:
                    type: number
                    format: float
                    nullable: true
                  width:
                    type: number
                    format: float
                    nullable: true
                  grammage:
                    type: number
                    format: float
                    nullable: true
                  shrinkage:
                    type: number
                    format: float
                    nullable: true
            total_items:
               type: integer
      400:
        description: Invalid input.
      401:
        description: Authentication required.
      403:
        description: Permission denied.
      404:
        description: No fabrics found.
      500:
        description: Internal server error or error fetching data from ERP.
      503:
        description: Service unavailable.
    """
    logger.info("Fabric balances request received.")
    data = request.get_json() or {}
    search_filter = data.get('filter')
    force_refresh = data.get('force_refresh', False)

    try:
        fabric_service = _get_fabric_service()
        fabric_list = fabric_service.get_fabrics(
            search_filter=search_filter,
            force_refresh=force_refresh
        )

        logger.info(f"Returning {len(fabric_list)} fabrics.")
        # Structure the response as expected by the frontend service
        return jsonify({
            "fabrics": fabric_list,
            "total_items": len(fabric_list) # Total items *after* filtering
        }), 200

    except NotFoundError as e:
        logger.warning(f"Fabric fetch failed: {e}")
        return jsonify({"error": str(e)}), 404
    except (ServiceError, ApiError) as e:
        logger.error(f"Service error fetching fabrics: {e}", exc_info=True)
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error fetching fabrics: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred."}), 500


@fabrics_bp.route('/cache/clear', methods=['POST'])
@login_required
@fabrics_access_required # Or maybe admin_required? Check requirements.
def clear_fabric_cache():
    """
    Endpoint to manually clear the fabric data cache.
    ---
    tags:
      - Fabrics
    security:
      - bearerAuth: []
    responses:
      200:
        description: Cache cleared successfully.
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: Authentication required.
      403:
        description: Permission denied.
      500:
        description: Internal server error.
      503:
        description: Service unavailable.
    """
    logger.info(f"Request received to clear fabric cache by user '{request.current_user.username}'.")
    try:
        fabric_service = _get_fabric_service()
        fabric_service.clear_fabric_cache()
        return jsonify({"message": "Cache de tecidos limpo com sucesso."}), 200
    except (ServiceError, ApiError) as e:
        logger.error(f"Service error clearing fabric cache: {e}", exc_info=True)
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error clearing fabric cache: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred while clearing the cache."}), 500

# --- Service Instantiation (Done in app factory) ---
# You need to ensure FabricService is instantiated and added to app.config['fabric_service']
# in src/app.py, similar to how auth_service is done.