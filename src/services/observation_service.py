# src/services/observation_service.py
# Contains business logic related to managing product observations using ORM.

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone # <<<--- ADICIONAR timezone AQUI

# Import Session and session manager
from sqlalchemy.orm import Session
from src.database import get_db_session

# Import ORM models and Repository
from src.database.observation_repository import ObservationRepository
from src.domain.observation import Observation
from src.domain.user import User # Still needed for user info

from src.utils.logger import logger
from src.api.errors import NotFoundError, ServiceError, ValidationError, ForbiddenError, DatabaseError
from sqlalchemy.exc import SQLAlchemyError

class ObservationService:
    """
    Service layer for managing product observations using ORM Sessions.
    """

    def __init__(self, observation_repository: ObservationRepository):
        """
        Initializes the ObservationService.

        Args:
            observation_repository: Instance of ObservationRepository.
        """
        self.observation_repository = observation_repository
        logger.info("ObservationService initialized (ORM).")

    def add_observation(self, reference_code: str, observation_text: str, user: User) -> Observation:
        """Adds a new observation for a product reference code using ORM."""
        if not reference_code or not observation_text:
            raise ValidationError("Reference code and observation text cannot be empty.")
        if not user or not user.username:
             raise ValidationError("Valid user information is required to add an observation.")

        logger.info(f"User '{user.username}' adding observation for reference '{reference_code}'.")
        # Criar instância do modelo ORM
        observation = Observation(
            reference_code=reference_code,
            observation_text=observation_text, # Atributo agora é observation_text
            user=user.username, # Store username
            timestamp=datetime.now(timezone.utc) # Usar UTC (agora timezone está importado)
        )

        try:
            # Usar sessão para adicionar ao banco
            with get_db_session() as db:
                created_observation = self.observation_repository.add(db, observation)
            # A sessão é commitada automaticamente ao sair do 'with' sem erro
            logger.info(f"Observation (ID: {created_observation.id}) added successfully for reference '{reference_code}'.")
            return created_observation
        except (DatabaseError, SQLAlchemyError) as e:
            logger.error(f"Failed to add observation for reference '{reference_code}': {e}", exc_info=True)
            raise ServiceError(f"Could not add observation: {e}") from e
        except Exception as e:
             logger.error(f"Unexpected error adding observation: {e}", exc_info=True)
             raise ServiceError(f"An unexpected error occurred while adding observation: {e}") from e


    def get_observations_for_product(self, reference_code: str, include_resolved: bool = True) -> List[Observation]:
        """Retrieves observations for a specific product reference code using ORM."""
        if not reference_code:
            raise ValidationError("Reference code cannot be empty.")

        logger.debug(f"Fetching observations for reference '{reference_code}' (include_resolved={include_resolved}).")
        try:
            # Usar sessão para buscar
            with get_db_session() as db:
                observations = self.observation_repository.find_by_reference_code(db, reference_code, include_resolved)
            logger.debug(f"Found {len(observations)} observations for reference '{reference_code}'.")
            # Retornar a lista de objetos ORM diretamente (ou converter para dicts se a API precisar)
            return observations
        except (DatabaseError, SQLAlchemyError) as e:
            logger.error(f"Failed to retrieve observations for reference '{reference_code}': {e}", exc_info=True)
            raise ServiceError(f"Could not retrieve observations: {e}") from e
        except Exception as e:
             logger.error(f"Unexpected error retrieving observations: {e}", exc_info=True)
             raise ServiceError(f"An unexpected error occurred while retrieving observations: {e}") from e

    def resolve_observation(self, observation_id: int, resolving_user: User) -> bool:
        """Marks an observation as resolved using ORM."""
        if not resolving_user or not resolving_user.username:
             raise ValidationError("Valid user information is required to resolve an observation.")

        logger.info(f"User '{resolving_user.username}' attempting to resolve observation ID: {observation_id}.")
        try:
            # Usar sessão para marcar como resolvido
            with get_db_session() as db:
                success = self.observation_repository.mark_as_resolved(db, observation_id, resolving_user.username)
            # Commit/rollback é gerenciado pelo get_db_session
            if success:
                 logger.info(f"Observation ID: {observation_id} resolved successfully by '{resolving_user.username}'.")
            else:
                 logger.warning(f"Observation ID: {observation_id} could not be marked as resolved (possibly already resolved or not found).")
            return success
        except NotFoundError:
             logger.warning(f"Attempt to resolve observation ID: {observation_id} failed: Not found.")
             raise # Re-raise NotFoundError
        except (DatabaseError, SQLAlchemyError) as e:
            logger.error(f"Failed to resolve observation ID {observation_id}: {e}", exc_info=True)
            raise ServiceError(f"Could not resolve observation: {e}") from e
        except Exception as e:
             logger.error(f"Unexpected error resolving observation: {e}", exc_info=True)
             raise ServiceError(f"An unexpected error occurred while resolving observation: {e}") from e

    def get_unresolved_count(self, reference_code: str) -> int:
        """Gets the count of unresolved observations for a product reference code using ORM."""
        if not reference_code:
            raise ValidationError("Reference code cannot be empty.")

        logger.debug(f"Getting unresolved observation count for reference '{reference_code}'.")
        try:
            # Usar sessão para contar
            with get_db_session() as db:
                count = self.observation_repository.get_unresolved_count(db, reference_code)
            logger.debug(f"Unresolved count for reference '{reference_code}' is {count}.")
            return count
        except (DatabaseError, SQLAlchemyError) as e:
            logger.error(f"Failed to get unresolved observation count for reference '{reference_code}': {e}", exc_info=True)
            raise ServiceError(f"Could not get unresolved observation count: {e}") from e
        except Exception as e:
             logger.error(f"Unexpected error getting unresolved count: {e}", exc_info=True)
             raise ServiceError(f"An unexpected error occurred while getting unresolved count: {e}") from e

    def get_references_with_pending_observations(self) -> List[Dict[str, Any]]:
        """Retrieves references with pending observations using ORM."""
        logger.debug("Fetching references with pending observations.")
        try:
            # Usar sessão para buscar
            with get_db_session() as db:
                references = self.observation_repository.get_references_with_pending(db)
            logger.debug(f"Found {len(references)} references with pending observations.")
            # O repositório já retorna dicts formatados
            return references
        except (DatabaseError, SQLAlchemyError) as e:
            logger.error(f"Failed to retrieve references with pending observations: {e}", exc_info=True)
            raise ServiceError(f"Could not retrieve references with pending observations: {e}") from e
        except Exception as e:
             logger.error(f"Unexpected error getting pending references: {e}", exc_info=True)
             raise ServiceError(f"An unexpected error occurred while getting pending references: {e}") from e