# src/services/observation_service.py
# Contains business logic related to managing product observations.

from typing import List, Dict, Any, Optional
from datetime import datetime
from src.database.observation_repository import ObservationRepository
from src.domain.observation import Observation
from src.domain.user import User # To get username for actions
from src.utils.logger import logger
from src.api.errors import NotFoundError, ServiceError, ValidationError, ForbiddenError

class ObservationService:
    """
    Service layer for managing product observations. Interacts with
    the ObservationRepository.
    """

    def __init__(self, observation_repository: ObservationRepository):
        """
        Initializes the ObservationService.

        Args:
            observation_repository: Instance of ObservationRepository.
        """
        self.observation_repository = observation_repository
        logger.info("ObservationService initialized.")

    def add_observation(self, reference_code: str, observation_text: str, user: User) -> Observation:
        """
        Adds a new observation for a product reference code.

        Args:
            reference_code: The product reference code.
            observation_text: The text content of the observation.
            user: The User object representing the user adding the observation.

        Returns:
            The created Observation object with its ID.

        Raises:
            ValidationError: If input data is invalid.
            ServiceError: If the observation could not be added.
        """
        if not reference_code or not observation_text:
            raise ValidationError("Reference code and observation text cannot be empty.")
        if not user or not user.username:
             raise ValidationError("Valid user information is required to add an observation.")

        logger.info(f"User '{user.username}' adding observation for reference '{reference_code}'.")
        observation = Observation(
            reference_code=reference_code,
            observation_text=observation_text,
            user=user.username, # Store username
            timestamp=datetime.now()
        )

        try:
            created_observation = self.observation_repository.add(observation)
            logger.info(f"Observation (ID: {created_observation.id}) added successfully for reference '{reference_code}'.")
            return created_observation
        except Exception as e:
            logger.error(f"Failed to add observation for reference '{reference_code}': {e}", exc_info=True)
            # Wrap DB errors or other issues
            raise ServiceError(f"Could not add observation: {e}") from e

    def get_observations_for_product(self, reference_code: str, include_resolved: bool = True) -> List[Observation]:
        """
        Retrieves observations for a specific product reference code.

        Args:
            reference_code: The product reference code.
            include_resolved: Flag to include resolved observations.

        Returns:
            A list of Observation objects.
        """
        if not reference_code:
            raise ValidationError("Reference code cannot be empty.")

        logger.debug(f"Fetching observations for reference '{reference_code}' (include_resolved={include_resolved}).")
        try:
            observations = self.observation_repository.find_by_reference_code(reference_code, include_resolved)
            logger.debug(f"Found {len(observations)} observations for reference '{reference_code}'.")
            return observations
        except Exception as e:
            logger.error(f"Failed to retrieve observations for reference '{reference_code}': {e}", exc_info=True)
            raise ServiceError(f"Could not retrieve observations: {e}") from e

    def resolve_observation(self, observation_id: int, resolving_user: User) -> bool:
        """
        Marks an observation as resolved.

        Args:
            observation_id: The ID of the observation to resolve.
            resolving_user: The User object representing the user resolving the observation.

        Returns:
            True if the observation was successfully marked as resolved.

        Raises:
            ValidationError: If input data is invalid.
            NotFoundError: If the observation doesn't exist.
            ForbiddenError: Potentially, if rules about who can resolve are added.
            ServiceError: If the update fails for other reasons.
        """
        if not resolving_user or not resolving_user.username:
             raise ValidationError("Valid user information is required to resolve an observation.")

        logger.info(f"User '{resolving_user.username}' attempting to resolve observation ID: {observation_id}.")
        try:
            # The repository method raises NotFoundError if applicable
            success = self.observation_repository.mark_as_resolved(observation_id, resolving_user.username)
            if success:
                 logger.info(f"Observation ID: {observation_id} resolved successfully by '{resolving_user.username}'.")
            else:
                 # This case might occur if it was already resolved concurrently
                 logger.warning(f"Observation ID: {observation_id} could not be marked as resolved (possibly already resolved or another issue).")
            return success
        except NotFoundError:
            logger.warning(f"Attempt to resolve observation ID: {observation_id} failed: Not found.")
            raise # Re-raise NotFoundError
        except Exception as e:
            logger.error(f"Failed to resolve observation ID {observation_id}: {e}", exc_info=True)
            raise ServiceError(f"Could not resolve observation: {e}") from e

    def get_unresolved_count(self, reference_code: str) -> int:
        """
        Gets the count of unresolved observations for a product reference code.

        Args:
            reference_code: The product reference code.

        Returns:
            The count of unresolved observations.

        Raises:
            ValidationError: If reference_code is empty.
            ServiceError: If the count cannot be retrieved.
        """
        if not reference_code:
            raise ValidationError("Reference code cannot be empty.")

        logger.debug(f"Getting unresolved observation count for reference '{reference_code}'.")
        try:
            count = self.observation_repository.get_unresolved_count(reference_code)
            logger.debug(f"Unresolved count for reference '{reference_code}' is {count}.")
            return count
        except Exception as e:
            logger.error(f"Failed to get unresolved observation count for reference '{reference_code}': {e}", exc_info=True)
            raise ServiceError(f"Could not get unresolved observation count: {e}") from e

    def get_references_with_pending_observations(self) -> List[Dict[str, Any]]:
        """
        Retrieves a list of product reference codes that have pending (unresolved) observations.

        Returns:
            A list of dictionaries, each containing 'reference_code', 'user', 'timestamp'.
        """
        logger.debug("Fetching references with pending observations.")
        try:
            references = self.observation_repository.get_references_with_pending()
            logger.debug(f"Found {len(references)} references with pending observations.")
            return references
        except Exception as e:
            logger.error(f"Failed to retrieve references with pending observations: {e}", exc_info=True)
            raise ServiceError(f"Could not retrieve references with pending observations: {e}") from e