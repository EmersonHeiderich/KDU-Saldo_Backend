# src/api/routes/observations.py
# Defines API endpoints for managing product observations using ORM.

from flask import Blueprint, request, jsonify, current_app

# Import Service
from src.services.observation_service import ObservationService

# Import ORM Model (apenas para type hints se necessário, serviço retorna ORM)
# from src.domain.observation import Observation

from src.api.decorators import login_required, products_access_required
from src.api.errors import ApiError, NotFoundError, ValidationError, ForbiddenError, ServiceError, DatabaseError
from src.utils.logger import logger

observations_bp = Blueprint('observations', __name__)

# Helper para obter ObservationService
def _get_observation_service() -> ObservationService:
     service = current_app.config.get('observation_service')
     if not service:
          # Idealmente, a injeção deve ser garantida no create_app
          logger.critical("ObservationService not found in application config!")
          raise ServiceError("Observation service is unavailable.", 503) # Usar ServiceError
     return service

@observations_bp.route('/product/<string:reference_code>', methods=['POST'])
@login_required
@products_access_required
def add_product_observation(reference_code: str):
    """Adds a new observation for a specific product reference code."""
    logger.info(f"Add observation request for reference: {reference_code}")
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    observation_text = data.get('observation_text')

    if not observation_text:
        return jsonify({"error": "Field 'observation_text' is required"}), 400

    try:
        current_user = request.current_user
        observation_service = _get_observation_service()
        # Serviço agora gerencia a sessão internamente
        new_observation = observation_service.add_observation(reference_code, observation_text, current_user)
        # Converter objeto ORM para dict
        return jsonify(new_observation.to_dict()), 201

    except ValidationError as e:
        logger.warning(f"Validation error adding observation for '{reference_code}': {e}")
        return jsonify({"error": str(e)}), 400
    except (ServiceError, DatabaseError) as e: # Capturar erros do serviço/DB
         logger.error(f"Service/DB error adding observation for '{reference_code}': {e}", exc_info=True)
         # Retornar 500 ou status específico do ServiceError
         status_code = e.status_code if hasattr(e, 'status_code') else 500
         msg = e.message if hasattr(e, 'message') else str(e)
         return jsonify({"error": f"Failed to add observation: {msg}"}), status_code
    except Exception as e:
        logger.error(f"Unexpected error adding observation for '{reference_code}': {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500


@observations_bp.route('/product/<string:reference_code>', methods=['GET'])
@login_required
@products_access_required
def get_product_observations(reference_code: str):
    """Retrieves observations for a specific product reference code."""
    logger.info(f"Get observations request for reference: {reference_code}")
    include_resolved_str = request.args.get('include_resolved', 'true').lower()
    include_resolved = include_resolved_str == 'true'

    try:
        observation_service = _get_observation_service()
        # Serviço retorna lista de objetos ORM
        observations = observation_service.get_observations_for_product(reference_code, include_resolved)
        # Converter lista de objetos ORM para lista de dicts
        observations_data = [obs.to_dict() for obs in observations]
        return jsonify(observations_data), 200

    except ValidationError as e:
         logger.warning(f"Validation error getting observations for '{reference_code}': {e}")
         return jsonify({"error": str(e)}), 400
    except (ServiceError, DatabaseError) as e:
         logger.error(f"Service/DB error getting observations for '{reference_code}': {e}", exc_info=True)
         status_code = e.status_code if hasattr(e, 'status_code') else 500
         msg = e.message if hasattr(e, 'message') else str(e)
         return jsonify({"error": f"Failed to get observations: {msg}"}), status_code
    except Exception as e:
        logger.error(f"Unexpected error getting observations for '{reference_code}': {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500


@observations_bp.route('/product/<string:reference_code>/unresolved_count', methods=['GET'])
@login_required
@products_access_required
def get_product_unresolved_observations_count(reference_code: str):
    """Retrieves the count of unresolved observations for a specific product reference code."""
    logger.info(f"Get unresolved count request for reference: {reference_code}")
    try:
        observation_service = _get_observation_service()
        count = observation_service.get_unresolved_count(reference_code)
        return jsonify({"reference_code": reference_code, "unresolved_count": count}), 200

    except ValidationError as e:
         logger.warning(f"Validation error getting unresolved count for '{reference_code}': {e}")
         return jsonify({"error": str(e)}), 400
    except (ServiceError, DatabaseError) as e:
         logger.error(f"Service/DB error getting unresolved count for '{reference_code}': {e}", exc_info=True)
         status_code = e.status_code if hasattr(e, 'status_code') else 500
         msg = e.message if hasattr(e, 'message') else str(e)
         return jsonify({"error": f"Failed to get unresolved count: {msg}"}), status_code
    except Exception as e:
        logger.error(f"Unexpected error getting unresolved count for '{reference_code}': {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500


@observations_bp.route('/<int:observation_id>/resolve', methods=['PUT'])
@login_required
@products_access_required
def resolve_product_observation(observation_id: int):
    """Marks a specific observation as resolved."""
    logger.info(f"Resolve observation request for ID: {observation_id}")
    try:
        current_user = request.current_user
        observation_service = _get_observation_service()
        success = observation_service.resolve_observation(observation_id, current_user)

        if success:
            return jsonify({"message": f"Observation {observation_id} marked as resolved."}), 200
        else:
             # Serviço pode retornar False se já estava resolvido ou não encontrado
             # O serviço agora levanta NotFoundError, então este 'else' pode indicar 'já resolvido'.
             logger.warning(f"Failed to mark observation {observation_id} as resolved (possibly already resolved).")
             # Manter 400 ou talvez um 200 com mensagem diferente? 400 indica que o estado não mudou como pedido.
             return jsonify({"error": f"Observation {observation_id} could not be resolved (it might already be resolved)."}), 400

    except NotFoundError as e:
        logger.warning(f"Cannot resolve observation ID {observation_id}: Not found.")
        return jsonify({"error": str(e)}), 404
    except ValidationError as e:
         logger.warning(f"Validation error resolving observation {observation_id}: {e}")
         return jsonify({"error": str(e)}), 400
    except (ServiceError, DatabaseError) as e:
         logger.error(f"Service/DB error resolving observation {observation_id}: {e}", exc_info=True)
         status_code = e.status_code if hasattr(e, 'status_code') else 500
         msg = e.message if hasattr(e, 'message') else str(e)
         return jsonify({"error": f"Failed to resolve observation: {msg}"}), status_code
    except Exception as e:
        logger.error(f"Unexpected error resolving observation {observation_id}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500


@observations_bp.route('/pending_references', methods=['GET'])
@login_required
@products_access_required
def get_pending_references():
    """Retrieves references with pending observations."""
    logger.info("Get pending references request received.")
    try:
        observation_service = _get_observation_service()
        # Serviço retorna lista de dicts já formatados pelo repositório
        references = observation_service.get_references_with_pending_observations()
        return jsonify(references), 200
    except (ServiceError, DatabaseError) as e:
         logger.error(f"Service/DB error getting pending references: {e}", exc_info=True)
         status_code = e.status_code if hasattr(e, 'status_code') else 500
         msg = e.message if hasattr(e, 'message') else str(e)
         return jsonify({"error": f"Failed to get pending references: {msg}"}), status_code
    except Exception as e:
        logger.error(f"Unexpected error getting pending references: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500