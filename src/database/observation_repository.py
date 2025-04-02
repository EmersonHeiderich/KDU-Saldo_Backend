# src/database/observation_repository.py
# Handles database operations for Product Observations using SQLAlchemy ORM.

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, delete, update # Import select, func, delete, update
from sqlalchemy.orm import Session # Import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .base_repository import BaseRepository
from src.domain.observation import Observation # Import ORM model
from src.utils.logger import logger
from src.api.errors import DatabaseError, NotFoundError, ValidationError

class ObservationRepository(BaseRepository):
    """
    Repository for managing Product Observations using SQLAlchemy ORM Sessions.
    Methods now expect a Session object to be passed in.
    """

    # O construtor ainda recebe Engine, mas não o usaremos diretamente nos métodos ORM.
    # def __init__(self, engine: Engine):
    #     super().__init__(engine)
    #     logger.info("ObservationRepository initialized with SQLAlchemy engine (ready for ORM sessions).")


    def add(self, db: Session, observation: Observation) -> Observation:
        """Adds a new observation to the database using ORM Session."""
        if not observation.reference_code or not observation.observation_text or not observation.user:
             raise ValueError("Missing required fields (reference_code, observation_text, user).")

        logger.debug(f"ORM: Adding observation for ref '{observation.reference_code}' to session")
        try:
            # Define timestamp se não estiver definido
            if observation.timestamp is None:
                 observation.timestamp = datetime.now(timezone.utc)

            db.add(observation)
            db.flush() # Para obter o ID gerado
            logger.info(f"ORM: Observation added to session (ID: {observation.id}) for ref: {observation.reference_code}. Commit pending.")
            # Commit é tratado externamente
            return observation
        except IntegrityError as e: # Capturar erros de constraint se houver (improvável aqui)
            db.rollback()
            logger.error(f"ORM: Database integrity error adding observation: {e}", exc_info=True)
            raise DatabaseError(f"Failed to add observation due to integrity constraint: {e}") from e
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"ORM: Database error adding observation: {e}", exc_info=True)
            raise DatabaseError(f"Failed to add observation: {e}") from e
        except Exception as e:
            db.rollback()
            logger.error(f"ORM: Unexpected error adding observation for ref '{observation.reference_code}': {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred while adding observation: {e}") from e

    def find_by_id(self, db: Session, observation_id: int) -> Optional[Observation]:
        """Finds an observation by its ID using ORM Session."""
        logger.debug(f"ORM: Finding observation by ID {observation_id}")
        try:
            observation = db.get(Observation, observation_id)
            if observation:
                 logger.debug(f"ORM: Observation found by ID {observation_id}.")
            else:
                 logger.debug(f"ORM: Observation not found by ID {observation_id}.")
            return observation
        except SQLAlchemyError as e:
             logger.error(f"ORM: Database error finding observation by ID {observation_id}: {e}", exc_info=True)
             raise DatabaseError(f"Database error finding observation by ID: {e}") from e
        except Exception as e:
             logger.error(f"ORM: Unexpected error finding observation by ID {observation_id}: {e}", exc_info=True)
             raise DatabaseError(f"Unexpected error finding observation by ID: {e}") from e


    def find_by_reference_code(self, db: Session, reference_code: str, include_resolved: bool = True) -> List[Observation]:
        """Finds observations for a reference code using ORM Session."""
        logger.debug(f"ORM: Finding obs for ref '{reference_code}' (resolved={include_resolved})")
        try:
            stmt = select(Observation).where(Observation.reference_code == reference_code)
            if not include_resolved:
                stmt = stmt.where(Observation.resolved == False)
            stmt = stmt.order_by(Observation.timestamp.desc())

            observations = db.scalars(stmt).all()
            logger.debug(f"ORM: Found {len(observations)} obs for ref '{reference_code}'.")
            return list(observations)
        except SQLAlchemyError as e:
             logger.error(f"ORM: Database error finding obs by ref '{reference_code}': {e}", exc_info=True)
             raise DatabaseError(f"Database error finding obs by ref: {e}") from e
        except Exception as e:
             logger.error(f"ORM: Unexpected error finding obs by ref {reference_code}: {e}", exc_info=True)
             raise DatabaseError(f"Unexpected error finding obs by ref: {e}") from e

    def update(self, db: Session, observation_to_update: Observation) -> Observation:
        """Updates an existing observation using ORM Session."""
        if observation_to_update.id is None:
            raise ValueError("Cannot update observation without an ID.")

        logger.debug(f"ORM: Updating observation ID {observation_to_update.id} in session")
        try:
            # Se o objeto veio de fora da sessão, buscar primeiro ou usar merge.
            # Assumindo que o objeto já está na sessão ou será gerenciado pelo chamador.
            db.flush() # Envia as alterações pendentes (se houver) sem commitar
            logger.info(f"ORM: Observation ID {observation_to_update.id} marked for update. Commit pending.")
            # Commit é externo
            return observation_to_update
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"ORM: Database error updating observation ID {observation_to_update.id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to update observation: {e}") from e
        except Exception as e:
            db.rollback()
            logger.error(f"ORM: Unexpected error updating observation ID {observation_to_update.id}: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred while updating observation: {e}") from e


    def mark_as_resolved(self, db: Session, observation_id: int, resolved_by_user: str) -> bool:
        """Marks a specific observation as resolved using ORM Session."""
        logger.debug(f"ORM: Marking observation ID {observation_id} as resolved by '{resolved_by_user}'")
        try:
            observation = db.get(Observation, observation_id)
            if not observation:
                 logger.warning(f"ORM: Attempted to resolve non-existent observation ID {observation_id}.")
                 raise NotFoundError(f"Observation with ID {observation_id} not found.")

            if observation.resolved:
                 logger.warning(f"ORM: Observation ID {observation_id} was already resolved.")
                 return False # Indicar que nenhuma alteração foi feita

            observation.resolved = True
            observation.resolved_user = resolved_by_user
            observation.resolved_timestamp = datetime.now(timezone.utc)
            db.flush() # Envia a alteração
            logger.info(f"ORM: Observation ID {observation_id} marked as resolved in session. Commit pending.")
            # Commit é externo
            return True
        except NotFoundError:
             raise # Re-raise not found error
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"ORM: Database error marking obs ID {observation_id} as resolved: {e}", exc_info=True)
            raise DatabaseError(f"Failed to resolve observation: {e}") from e
        except Exception as e:
            db.rollback()
            logger.error(f"ORM: Unexpected error marking obs ID {observation_id} as resolved: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred while resolving observation: {e}") from e

    def get_unresolved_count(self, db: Session, reference_code: str) -> int:
        """Gets the count of unresolved observations using ORM Session."""
        logger.debug(f"ORM: Getting unresolved count for ref '{reference_code}'")
        try:
            stmt = (
                select(func.count(Observation.id))
                .where(Observation.reference_code == reference_code)
                .where(Observation.resolved == False)
            )
            count = db.scalar(stmt)
            count = count if count is not None else 0
            logger.debug(f"ORM: Unresolved count for ref '{reference_code}': {count}")
            return count
        except SQLAlchemyError as e:
            logger.error(f"ORM: Failed get unresolved count for ref '{reference_code}': {e}", exc_info=True)
            raise DatabaseError(f"Database error getting unresolved count: {e}") from e
        except Exception as e:
            logger.error(f"ORM: Unexpected error getting unresolved count for ref '{reference_code}': {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error getting unresolved count: {e}") from e

    def get_references_with_pending(self, db: Session) -> List[Dict[str, Any]]:
        """Gets distinct references with the latest pending observation using ORM."""
        # Esta query é um pouco mais complexa com ORM puro sem window functions diretas
        # Vamos manter a lógica de subquery similar à SQL original
        logger.debug("ORM: Getting references with pending observations")
        try:
            # Subquery para encontrar o timestamp mais recente não resolvido por referência
            subq = (
                select(
                    Observation.reference_code,
                    func.max(Observation.timestamp).label("max_timestamp")
                )
                .where(Observation.resolved == False)
                .group_by(Observation.reference_code)
                .subquery('latest_pending')
            )

            # Query principal para pegar os detalhes da observação mais recente
            stmt = (
                select(
                    Observation.reference_code,
                    Observation.user,
                    Observation.timestamp
                )
                .join(subq, (Observation.reference_code == subq.c.reference_code) & (Observation.timestamp == subq.c.max_timestamp))
                .where(Observation.resolved == False) # Garantir que ainda não foi resolvido (caso haja duplicatas de timestamp)
                .order_by(Observation.timestamp.desc())
            )

            results = db.execute(stmt).mappings().all() # Executa e pega como dicionários

            # Formata o resultado (converte datetime para isoformat)
            formatted_results = [
                 {
                      "reference_code": row["reference_code"],
                      "user": row["user"],
                      "timestamp": row["timestamp"].isoformat() if isinstance(row["timestamp"], datetime) else None
                 } for row in results
            ]

            logger.debug(f"ORM: Found {len(formatted_results)} references with pending observations.")
            return formatted_results
        except SQLAlchemyError as e:
            logger.error(f"ORM: Failed to get references with pending observations: {e}", exc_info=True)
            raise DatabaseError(f"Database error getting pending references: {e}") from e
        except Exception as e:
            logger.error(f"ORM: Unexpected error getting pending references: {e}", exc_info=True)
            raise DatabaseError(f"Unexpected error getting pending references: {e}") from e

    def delete_by_id(self, db: Session, observation_id: int) -> bool:
        """Deletes an observation by its ID using ORM Session."""
        logger.debug(f"ORM: Deleting observation ID {observation_id}")
        try:
            observation = db.get(Observation, observation_id)
            if observation:
                db.delete(observation)
                db.flush()
                logger.info(f"ORM: Observation ID {observation_id} marked for deletion. Commit pending.")
                return True
            else:
                logger.warning(f"ORM: Attempted to delete observation ID {observation_id}, but it was not found.")
                return False
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"ORM: Database error deleting obs ID {observation_id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to delete observation: {e}") from e
        except Exception as e:
            db.rollback()
            logger.error(f"ORM: Unexpected error deleting obs ID {observation_id}: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred while deleting observation: {e}") from e