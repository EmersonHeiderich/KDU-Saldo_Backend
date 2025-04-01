# src/database/observation_repository.py
# Handles database operations for Product Observations using SQLAlchemy.

# REMOVER import sqlite3 se não for mais necessário para compatibilidade
# import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
# Importar text do sqlalchemy
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .base_repository import BaseRepository
from src.domain.observation import Observation
from src.utils.logger import logger
from src.api.errors import DatabaseError, NotFoundError, ValidationError

class ObservationRepository(BaseRepository):
    """
    Repository for managing Product Observations using SQLAlchemy.
    """

    def __init__(self, engine: Engine):
        super().__init__(engine)
        logger.info("ObservationRepository initialized with SQLAlchemy engine.")

    def add(self, observation: Observation) -> Observation:
        """Adds a new observation to the database, ensuring commit."""
        if not observation.reference_code or not observation.observation_text or not observation.user:
             raise ValueError("Missing required fields (reference_code, observation_text, user).")

        query = """
            INSERT INTO product_observations
            (reference_code, observation, "user", timestamp, resolved, resolved_user, resolved_timestamp)
            VALUES (:ref_code, :obs_text, :user, :ts, :resolved, :res_user, :res_ts)
            RETURNING id
        """
        now = datetime.now()
        params = {
            "ref_code": observation.reference_code,
            "obs_text": observation.observation_text,
            "user": observation.user,
            "ts": observation.timestamp or now,
            "resolved": observation.resolved,
            "res_user": observation.resolved_user,
            "res_ts": observation.resolved_timestamp
        }

        try:
            # --- CORREÇÃO: Adicionar bloco de conexão e transação ---
            with self.engine.connect() as connection:
                with connection.begin(): # Inicia transação (commit/rollback automático)
                    result = connection.execute(text(query), params)
                    # Use scalar_one() se você espera exatamente um ID retornado
                    inserted_id = result.scalar_one()

            # Se chegou aqui, o commit foi bem-sucedido
            observation.id = inserted_id
            if observation.timestamp is None:
                 observation.timestamp = now

            logger.info(f"Observation added and committed successfully with ID: {observation.id} for ref: {observation.reference_code}")
            return observation
            # ----------------------------------------------------------

        except IntegrityError as e:
             # O rollback é automático ao sair do connection.begin() com erro
             logger.error(f"Database integrity error adding observation: {e}", exc_info=True)
             raise DatabaseError(f"Failed to add observation due to integrity constraint: {e}") from e
        except SQLAlchemyError as e:
             # O rollback é automático
             logger.error(f"Database error adding observation: {e}", exc_info=True)
             # Verificar se é um erro de 'no results' do scalar_one, embora não devesse ocorrer com RETURNING
             if "No rows returned for scalar_one()" in str(e):
                  raise DatabaseError("Failed to insert observation, RETURNING id yielded no result.") from e
             raise DatabaseError(f"Failed to add observation: {e}") from e
        except Exception as e:
             # O rollback é automático
             logger.error(f"Unexpected error adding observation for ref '{observation.reference_code}': {e}", exc_info=True)
             raise DatabaseError(f"An unexpected error occurred while adding observation: {e}") from e


    def find_by_id(self, observation_id: int) -> Optional[Observation]:
        """Finds an observation by its ID."""
        query = "SELECT * FROM product_observations WHERE id = :obs_id"
        params = {"obs_id": observation_id}
        try:
            row = self._execute(query, params=params, fetch_mode="one")
            if row:
                 return Observation.from_dict(row)
            return None
        except DatabaseError:
             return None
        except Exception as e:
             logger.error(f"Unexpected error finding observation by ID {observation_id}: {e}", exc_info=True)
             return None


    def find_by_reference_code(self, reference_code: str, include_resolved: bool = True) -> List[Observation]:
        """Finds all observations for a given product reference code."""
        params = {"ref_code": reference_code}
        if include_resolved:
             query = "SELECT * FROM product_observations WHERE reference_code = :ref_code ORDER BY timestamp DESC"
        else:
             query = "SELECT * FROM product_observations WHERE reference_code = :ref_code AND resolved = FALSE ORDER BY timestamp DESC"

        try:
            rows = self._execute(query, params=params, fetch_mode="all")
            observations = [Observation.from_dict(row) for row in rows if row]
            observations = [obs for obs in observations if obs is not None]
            logger.debug(f"Found {len(observations)} obs for ref '{reference_code}' (resolved={include_resolved}).")
            return observations
        except DatabaseError:
             return []
        except Exception as e:
             logger.error(f"Unexpected error finding obs by ref {reference_code}: {e}", exc_info=True)
             return []

    def update(self, observation: Observation) -> bool:
        """Updates an existing observation in the database."""
        if observation.id is None:
            raise ValueError("Cannot update observation without an ID.")

        query = """
            UPDATE product_observations SET
                reference_code = :ref_code,
                observation = :obs_text,
                "user" = :user,
                timestamp = :ts,
                resolved = :resolved,
                resolved_user = :res_user,
                resolved_timestamp = :res_ts
            WHERE id = :id
        """
        params = {
            "ref_code": observation.reference_code,
            "obs_text": observation.observation_text,
            "user": observation.user,
            "ts": observation.timestamp,
            "resolved": observation.resolved,
            "res_user": observation.resolved_user,
            "res_ts": observation.resolved_timestamp,
            "id": observation.id
        }

        try:
            with self.engine.connect() as connection:
                with connection.begin():
                    result = connection.execute(text(query), params)
                    rows_affected = result.rowcount

            logger.info(f"Observation ID {observation.id} update attempted. Rows affected: {rows_affected}")
            return rows_affected > 0
        except SQLAlchemyError as e:
            logger.error(f"Database error updating observation ID {observation.id}: {e}", exc_info=True)
            raise DatabaseError(f"Failed to update observation: {e}") from e
        except Exception as e:
             logger.error(f"Unexpected error updating observation ID {observation.id}: {e}", exc_info=True)
             raise DatabaseError(f"An unexpected error occurred while updating observation: {e}") from e


    def mark_as_resolved(self, observation_id: int, resolved_by_user: str) -> bool:
        """Marks a specific observation as resolved."""
        query = """
            UPDATE product_observations SET
                resolved = TRUE,
                resolved_user = :res_user,
                resolved_timestamp = :now
            WHERE id = :id AND resolved = FALSE
        """
        # Correção: Usar timezone UTC se o banco usar TIMESTAMPTZ
        # now = datetime.now()
        from datetime import timezone # Importar timezone
        now = datetime.now(timezone.utc)
        params = {
            "res_user": resolved_by_user,
            "now": now,
            "id": observation_id
        }
        rows_affected = 0
        try:
            with self.engine.connect() as connection:
                with connection.begin():
                    result = connection.execute(text(query), params)
                    rows_affected = result.rowcount

            if rows_affected > 0:
                 logger.info(f"Observation ID {observation_id} marked as resolved by {resolved_by_user}.")
                 return True
            else:
                 existing = self.find_by_id(observation_id)
                 if existing and existing.resolved:
                      logger.warning(f"Observation ID {observation_id} was already resolved.")
                      return False
                 elif not existing:
                      logger.warning(f"Attempted to resolve non-existent observation ID {observation_id}.")
                      raise NotFoundError(f"Observation with ID {observation_id} not found.")
                 else:
                      logger.error(f"Failed to mark obs ID {observation_id} as resolved, unknown state.")
                      return False

        except NotFoundError:
             raise
        except SQLAlchemyError as e:
            logger.error(f"Database error marking obs ID {observation_id} as resolved: {e}", exc_info=True)
            raise DatabaseError(f"Failed to resolve observation: {e}") from e
        except Exception as e:
             logger.error(f"Unexpected error marking obs ID {observation_id} as resolved: {e}", exc_info=True)
             raise DatabaseError(f"An unexpected error occurred while resolving observation: {e}") from e

    def get_unresolved_count(self, reference_code: str) -> int:
        """Gets the count of unresolved observations."""
        query = "SELECT COUNT(*) FROM product_observations WHERE reference_code = :ref_code AND resolved = FALSE"
        params = {"ref_code": reference_code}
        try:
            count = self._execute(query, params=params, fetch_mode="none")
            count = count if count is not None else 0
            logger.debug(f"Unresolved observation count for ref '{reference_code}': {count}")
            return count
        except DatabaseError:
            logger.error(f"Failed get unresolved count for ref '{reference_code}'", exc_info=True)
            return 0
        except Exception as e:
            logger.error(f"Unexpected error getting unresolved count for ref '{reference_code}': {e}", exc_info=True)
            return 0

    def get_references_with_pending(self) -> List[Dict[str, Any]]:
        """Gets distinct references with pending observations."""
        query = """
            SELECT
                po.reference_code,
                po."user",
                po.timestamp
            FROM product_observations po
            WHERE po.resolved = FALSE
              AND po.timestamp = (
                  SELECT MAX(sub.timestamp)
                  FROM product_observations sub
                  WHERE sub.reference_code = po.reference_code
                    AND sub.resolved = FALSE
              )
            ORDER BY po.timestamp DESC;
        """
        try:
            results = self._execute(query, fetch_mode="all")
            for r in results:
                 if isinstance(r.get('timestamp'), datetime):
                      r['timestamp'] = r['timestamp'].isoformat()
            logger.debug(f"Found {len(results)} references with pending observations.")
            return results
        except DatabaseError:
            logger.error(f"Failed to get references with pending observations", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting pending references: {e}", exc_info=True)
            return []

    def delete_by_id(self, observation_id: int) -> bool:
        """Deletes an observation by its ID within a transaction."""
        query = "DELETE FROM product_observations WHERE id = :id"
        params = {"id": observation_id}
        rows_affected = 0
        try:
             with self.engine.connect() as connection:
                  with connection.begin(): # Inicia transação
                       result = connection.execute(text(query), params)
                       rows_affected = result.rowcount

             if rows_affected > 0:
                  logger.info(f"Observation ID {observation_id} deleted successfully.")
                  return True
             else:
                  logger.warning(f"Attempted to delete observation ID {observation_id}, but it was not found or delete failed.")
                  return False
        except IntegrityError as e:
             logger.error(f"Integrity error deleting obs ID {observation_id}: {e}", exc_info=True)
             raise DatabaseError(f"Failed to delete observation due to integrity constraint: {e}") from e
        except SQLAlchemyError as e:
             logger.error(f"Database error deleting obs ID {observation_id}: {e}", exc_info=True)
             raise DatabaseError(f"Failed to delete observation: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error deleting obs ID {observation_id}: {e}", exc_info=True)
            raise DatabaseError(f"An unexpected error occurred while deleting observation: {e}") from e