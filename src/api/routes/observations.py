# src/api/routes/observations.py
# Defines API endpoints for managing product observations.

from flask import Blueprint, request, jsonify, current_app
from src.services.observation_service import ObservationService # Import the specific service
# Remove the top-level import: from src.database import get_observation_repository
from src.api.decorators import login_required, products_access_required # Use product access perm
from src.api.errors import ApiError, NotFoundError, ValidationError, ForbiddenError # Import custom errors
from src.utils.logger import logger

observations_bp = Blueprint('observations', __name__)

# Helper to get ObservationService instance
def _get_observation_service() -> ObservationService:
     # Check app context cache first?
     service = current_app.config.get('observation_service')
     if not service:
          logger.warning("ObservationService not found in app config, creating new instance.")
          # Import get_observation_repository *inside* the function
          from src.database import get_observation_repository
          # Assumes get_observation_repository() works correctly
          repo = get_observation_repository()
          service = ObservationService(repo)
          # Optionally cache it: current_app.config['observation_service'] = service
     return service

# Note: Routes are prefixed with /api/observations in register_blueprints

# --- Routes for specific product reference ---

@observations_bp.route('/product/<string:reference_code>', methods=['POST'])
@login_required
@products_access_required # Permission to view/manage product implies permission to add obs
def add_product_observation(reference_code: str):
    """
    Adds a new observation for a specific product reference code.
    ---
    tags: [Observations]
    security:
      - bearerAuth: []
    parameters:
      - in: path
        name: reference_code
        schema:
          type: string
        required: true
        description: The product reference code.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              observation_text:
                type: string
                description: "The text content of the observation."
                example: "Check stock level discrepancy."
            required: [observation_text]
    responses:
      201:
        description: Observation created successfully.
        content:
          application/json:
            schema:
              # Define schema for the created Observation object
              type: object
              properties:
                id: {type: integer}
                reference_code: {type: string}
                observation_text: {type: string}
                user: {type: string}
                timestamp: {type: string, format: date-time}
                resolved: {type: boolean}
                # ... other fields ...
      400:
        description: Bad request (Invalid JSON, missing fields)
      401:
        description: Unauthorized
      403:
        description: Forbidden (User lacks permission)
      500:
        description: Internal server error
    """
    logger.info(f"Add observation request for reference: {reference_code}")
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    observation_text = data.get('observation_text')

    if not observation_text:
        return jsonify({"error": "Field 'observation_text' is required"}), 400

    try:
        current_user = request.current_user # Set by @login_required
        observation_service = _get_observation_service()
        new_observation = observation_service.add_observation(reference_code, observation_text, current_user)
        return jsonify(new_observation.to_dict()), 201

    except ValidationError as e:
        logger.warning(f"Validation error adding observation for '{reference_code}': {e}")
        return jsonify({"error": str(e)}), 400
    except ApiError as e:
         logger.error(f"API error adding observation for '{reference_code}': {e.message}", exc_info=False)
         return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error adding observation for '{reference_code}': {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500


@observations_bp.route('/product/<string:reference_code>', methods=['GET'])
@login_required
@products_access_required
def get_product_observations(reference_code: str):
    """
    Retrieves observations for a specific product reference code.
    Can optionally filter to show only unresolved observations.
    ---
    tags: [Observations]
    security:
      - bearerAuth: []
    parameters:
      - in: path
        name: reference_code
        schema:
          type: string
        required: true
        description: The product reference code.
      - in: query
        name: include_resolved
        schema:
          type: boolean
          default: true
        required: false
        description: "Set to false to retrieve only unresolved observations."
    responses:
      200:
        description: List of observations.
        content:
          application/json:
            schema:
              type: array
              items:
                # Define Observation schema here
                type: object
                properties:
                  id: {type: integer}
                  # ... other fields ...
      400:
        description: Bad request (Invalid reference_code)
      401:
        description: Unauthorized
      403:
        description: Forbidden (User lacks permission)
      500:
        description: Internal server error
    """
    logger.info(f"Get observations request for reference: {reference_code}")
    include_resolved_str = request.args.get('include_resolved', 'true').lower()
    include_resolved = include_resolved_str == 'true'

    try:
        observation_service = _get_observation_service()
        observations = observation_service.get_observations_for_product(reference_code, include_resolved)
        # Convert observation objects to dictionaries for JSON response
        observations_data = [obs.to_dict() for obs in observations]
        return jsonify(observations_data), 200

    except ValidationError as e:
         logger.warning(f"Validation error getting observations for '{reference_code}': {e}")
         return jsonify({"error": str(e)}), 400
    except ApiError as e:
         logger.error(f"API error getting observations for '{reference_code}': {e.message}", exc_info=False)
         return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error getting observations for '{reference_code}': {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500


@observations_bp.route('/product/<string:reference_code>/unresolved_count', methods=['GET'])
@login_required
@products_access_required
def get_product_unresolved_observations_count(reference_code: str):
    """
    Retrieves the count of unresolved observations for a specific product reference code.
    ---
    tags: [Observations]
    security:
      - bearerAuth: []
    parameters:
      - in: path
        name: reference_code
        schema:
          type: string
        required: true
        description: The product reference code.
    responses:
      200:
        description: Count of unresolved observations.
        content:
          application/json:
            schema:
              type: object
              properties:
                reference_code:
                  type: string
                unresolved_count:
                  type: integer
      400:
        description: Bad request (Invalid reference_code)
      401:
        description: Unauthorized
      403:
        description: Forbidden (User lacks permission)
      500:
        description: Internal server error
    """
    logger.info(f"Get unresolved count request for reference: {reference_code}")
    try:
        observation_service = _get_observation_service()
        count = observation_service.get_unresolved_count(reference_code)
        return jsonify({"reference_code": reference_code, "unresolved_count": count}), 200

    except ValidationError as e:
         logger.warning(f"Validation error getting unresolved count for '{reference_code}': {e}")
         return jsonify({"error": str(e)}), 400
    except ApiError as e:
         logger.error(f"API error getting unresolved count for '{reference_code}': {e.message}", exc_info=False)
         return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error getting unresolved count for '{reference_code}': {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500


# --- Routes for managing individual observations by ID ---

@observations_bp.route('/<int:observation_id>/resolve', methods=['PUT'])
@login_required
@products_access_required # Or potentially a different permission?
def resolve_product_observation(observation_id: int):
    """
    Marks a specific observation as resolved.
    ---
    tags: [Observations]
    security:
      - bearerAuth: []
    parameters:
      - in: path
        name: observation_id
        schema:
          type: integer
        required: true
        description: The ID of the observation to resolve.
    responses:
      200:
        description: Observation marked as resolved successfully.
        content:
          application/json:
            schema:
              type: object
              properties:
                message: {type: string}
      400:
        description: Bad request (Invalid ID) or observation already resolved.
      401:
        description: Unauthorized
      403:
        description: Forbidden (User lacks permission)
      404:
        description: Observation not found.
      500:
        description: Internal server error
    """
    logger.info(f"Resolve observation request for ID: {observation_id}")
    try:
        current_user = request.current_user
        observation_service = _get_observation_service()
        success = observation_service.resolve_observation(observation_id, current_user)

        if success:
            return jsonify({"message": f"Observation {observation_id} marked as resolved."}), 200
        else:
             # This happens if the service determines it was already resolved (or another non-error failure)
             # Returning 400 might be suitable here to indicate the state wasn't changed as requested.
             logger.warning(f"Failed to mark observation {observation_id} as resolved (possibly already resolved).")
             return jsonify({"error": f"Observation {observation_id} could not be resolved (it might already be resolved)."}), 400

    except NotFoundError as e:
        logger.warning(f"Cannot resolve observation ID {observation_id}: Not found.")
        return jsonify({"error": str(e)}), 404
    except ValidationError as e: # Should not happen for ID, but maybe user validation?
         logger.warning(f"Validation error resolving observation {observation_id}: {e}")
         return jsonify({"error": str(e)}), 400
    except ApiError as e:
         logger.error(f"API error resolving observation {observation_id}: {e.message}", exc_info=False)
         return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error resolving observation {observation_id}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500

# --- Route for overview ---

@observations_bp.route('/pending_references', methods=['GET'])
@login_required
@products_access_required
def get_pending_references():
    """
    Retrieves a list of product reference codes that have pending (unresolved) observations.
    Includes details of the latest pending observation for each reference.
    ---
    tags: [Observations]
    security:
      - bearerAuth: []
    responses:
      200:
        description: List of references with pending observations.
        content:
          application/json:
            schema:
              type: array
              items:
                 type: object
                 properties:
                   reference_code: {type: string}
                   user: {type: string, description: "User who added the latest pending observation"}
                   timestamp: {type: string, format: date-time, description: "Timestamp of the latest pending observation"}
      401:
        description: Unauthorized
      403:
        description: Forbidden (User lacks permission)
      500:
        description: Internal server error
    """
    logger.info("Get pending references request received.")
    try:
        observation_service = _get_observation_service()
        references = observation_service.get_references_with_pending_observations()
        return jsonify(references), 200
    except ApiError as e:
         logger.error(f"API error getting pending references: {e.message}", exc_info=False)
         return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error getting pending references: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500