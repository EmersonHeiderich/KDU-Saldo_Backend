# src/services/observation_service.py
# Contains business logic related to managing product observations using ORM.

from typing import List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from src.database import get_db_session
from src.database.observation_repository import ObservationRepository
from src.domain.observation import Observation
from src.domain.user import User
from src.utils.logger import logger
from src.api.errors import NotFoundError, ServiceError, ValidationError, ForbiddenError, DatabaseError
from sqlalchemy.exc import SQLAlchemyError

class ObservationService:
    """
    Camada de serviço para gerenciamento de observações de produtos usando ORM Sessions.
    """

    def __init__(self, observation_repository: ObservationRepository):
        self.observation_repository = observation_repository
        logger.info("ObservationService inicializado (ORM).")

    def add_observation(self, reference_code: str, observation_text: str, user: User) -> Observation:
        """Adiciona uma nova observação para um código de referência de produto usando ORM."""
        if not reference_code or not observation_text:
            raise ValidationError("O código de referência e o texto da observação não podem estar vazios.")
        if not user or not user.username:
            raise ValidationError("Informações de usuário válidas são necessárias para adicionar uma observação.")

        logger.info(f"Usuário '{user.username}' adicionando observação para referência '{reference_code}'.")

        observation = Observation(
            reference_code=reference_code,
            observation_text=observation_text,
            user=user.username,
            timestamp=datetime.now(timezone.utc)
        )

        try:
            with get_db_session() as db:
                created_observation = self.observation_repository.add(db, observation)
            logger.info(f"Observação (ID: {created_observation.id}) adicionada com sucesso para referência '{reference_code}'.")
            return created_observation
        except (DatabaseError, SQLAlchemyError) as e:
            logger.error(f"Falha ao adicionar observação para referência '{reference_code}': {e}", exc_info=True)
            raise ServiceError(f"Não foi possível adicionar a observação: {e}") from e
        except Exception as e:
            logger.error(f"Erro inesperado ao adicionar observação: {e}", exc_info=True)
            raise ServiceError(f"Ocorreu um erro inesperado ao adicionar a observação: {e}") from e

    def get_observations_for_product(self, reference_code: str, include_resolved: bool = True) -> List[Observation]:
        """Recupera observações para um código de referência de produto específico usando ORM."""
        if not reference_code:
            raise ValidationError("O código de referência não pode estar vazio.")

        logger.debug(f"Buscando observações para referência '{reference_code}' (include_resolved={include_resolved}).")
        try:
            with get_db_session() as db:
                observations = self.observation_repository.find_by_reference_code(db, reference_code, include_resolved)
            logger.debug(f"Encontradas {len(observations)} observações para referência '{reference_code}'.")
            return observations
        except (DatabaseError, SQLAlchemyError) as e:
            logger.error(f"Falha ao recuperar observações para referência '{reference_code}': {e}", exc_info=True)
            raise ServiceError(f"Não foi possível recuperar as observações: {e}") from e
        except Exception as e:
            logger.error(f"Erro inesperado ao recuperar observações: {e}", exc_info=True)
            raise ServiceError(f"Ocorreu um erro inesperado ao recuperar as observações: {e}") from e

    def resolve_observation(self, observation_id: int, resolving_user: User) -> bool:
        """Marca uma observação como resolvida usando ORM."""
        if not resolving_user or not resolving_user.username:
            raise ValidationError("Informações de usuário válidas são necessárias para resolver uma observação.")

        logger.info(f"Usuário '{resolving_user.username}' tentando resolver observação ID: {observation_id}.")
        try:
            with get_db_session() as db:
                success = self.observation_repository.mark_as_resolved(db, observation_id, resolving_user.username)
            if success:
                logger.info(f"Observação ID: {observation_id} resolvida com sucesso por '{resolving_user.username}'.")
            else:
                logger.warning(f"Observação ID: {observation_id} não pôde ser marcada como resolvida.")
            return success
        except NotFoundError:
            logger.warning(f"Tentativa de resolver observação ID: {observation_id} falhou: Não encontrada.")
            raise
        except (DatabaseError, SQLAlchemyError) as e:
            logger.error(f"Falha ao resolver observação ID {observation_id}: {e}", exc_info=True)
            raise ServiceError(f"Não foi possível resolver a observação: {e}") from e
        except Exception as e:
            logger.error(f"Erro inesperado ao resolver observação: {e}", exc_info=True)
            raise ServiceError(f"Ocorreu um erro inesperado ao resolver a observação: {e}") from e

    def get_unresolved_count(self, reference_code: str) -> int:
        """Obtém a contagem de observações não resolvidas para um código de referência de produto usando ORM."""
        if not reference_code:
            raise ValidationError("O código de referência não pode estar vazio.")

        logger.debug(f"Obtendo contagem de observações não resolvidas para referência '{reference_code}'.")
        try:
            with get_db_session() as db:
                count = self.observation_repository.get_unresolved_count(db, reference_code)
            logger.debug(f"Contagem de não resolvidas para referência '{reference_code}': {count}.")
            return count
        except (DatabaseError, SQLAlchemyError) as e:
            logger.error(f"Falha ao obter contagem de observações não resolvidas para referência '{reference_code}': {e}", exc_info=True)
            raise ServiceError(f"Não foi possível obter a contagem de observações não resolvidas: {e}") from e
        except Exception as e:
            logger.error(f"Erro inesperado ao obter contagem de não resolvidas: {e}", exc_info=True)
            raise ServiceError(f"Ocorreu um erro inesperado ao obter a contagem de observações não resolvidas: {e}") from e

    def get_references_with_pending_observations(self) -> List[Dict[str, Any]]:
        """Recupera referências com observações pendentes usando ORM."""
        logger.debug("Buscando referências com observações pendentes.")
        try:
            with get_db_session() as db:
                references = self.observation_repository.get_references_with_pending(db)
            logger.debug(f"Encontradas {len(references)} referências com observações pendentes.")
            return references
        except (DatabaseError, SQLAlchemyError) as e:
            logger.error(f"Falha ao recuperar referências com observações pendentes: {e}", exc_info=True)
            raise ServiceError(f"Não foi possível recuperar as referências com observações pendentes: {e}") from e
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar referências pendentes: {e}", exc_info=True)
            raise ServiceError(f"Ocorreu um erro inesperado ao buscar referências com observações pendentes: {e}") from e
