# src/api/routes/sync.py
# Define endpoints da API para disparar operações de sincronização com o ERP.

from flask import Blueprint, jsonify, current_app, request
from src.services.sync.person_sync_service import PersonSyncService
from src.api.decorators import admin_required # Importa o decorator de admin
from src.api.errors import ServiceError, ApiError # Importa erros
from src.utils.logger import logger
import time # Para medir tempo de execução

sync_bp = Blueprint('sync', __name__)

# --- Helper para obter o serviço de sync ---
def _get_person_sync_service() -> PersonSyncService:
    service = current_app.config.get('person_sync_service')
    if not service:
        logger.critical("PersonSyncService not found in application config!")
        raise ServiceError("Serviço de sincronização de pessoas indisponível.", 503)
    return service

# --- Rotas ---

@sync_bp.route('/persons/full', methods=['POST'])
@admin_required # Protege a rota, apenas admins podem chamar
def trigger_full_person_sync():
    """
    Dispara a sincronização completa (carga inicial) dos dados de Pessoas (PF/PJ) e Estatísticas
    do ERP para o cache local.
    ---
    tags: [Synchronization]
    security:
      - bearerAuth: []
    responses:
      200:
        description: Sincronização completa iniciada e concluída com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Sincronização completa de pessoas concluída."
                duration_seconds:
                  type: number
                  format: float
                stats:
                  type: object
                  properties:
                    pf_processed: { type: integer }
                    pf_failed: { type: integer }
                    pj_processed: { type: integer }
                    pj_failed: { type: integer }
                    stats_synced: { type: integer }
                    stats_failed: { type: integer }
      401:
        description: Não autorizado (token inválido ou ausente).
      403:
        description: Proibido (usuário não é administrador).
      500:
        description: Erro interno ou erro durante a sincronização.
      503:
        description: Serviço de sincronização indisponível.
    """
    logger.info("Requisição recebida para disparar sincronização completa de pessoas.")
    start_time = time.time()
    try:
        sync_service = _get_person_sync_service()
        # ATENÇÃO: Esta chamada é síncrona e pode demorar!
        # Para produção, considere executar em background (Celery, etc.)
        sync_stats = sync_service.perform_full_sync()
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"Sincronização completa de pessoas concluída em {duration:.2f} segundos.")

        return jsonify({
            "message": "Sincronização completa de pessoas concluída.",
            "duration_seconds": round(duration, 2),
            "stats": sync_stats
        }), 200

    except ServiceError as e:
        logger.error(f"Erro de serviço durante a sincronização completa: {e.message}", exc_info=True)
        return jsonify({"error": e.message}), e.status_code
    except ApiError as e: # Capturar outros erros da API se necessário
        logger.error(f"Erro de API durante a sincronização completa: {e.message}", exc_info=True)
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.critical(f"Erro inesperado ao disparar sincronização completa: {e}", exc_info=True)
        return jsonify({"error": "Ocorreu um erro inesperado durante a sincronização."}), 500


@sync_bp.route('/persons/incremental', methods=['POST'])
@admin_required # Protege a rota
def trigger_incremental_person_sync():
    """
    Dispara a sincronização incremental dos dados de Pessoas (PF/PJ)
    alteradas recentemente no ERP para o cache local.
    Por padrão, verifica os últimos 60 minutos. Pode ser ajustado via query param 'minutes'.
    ---
    tags: [Synchronization]
    security:
      - bearerAuth: []
    parameters:
      - in: query
        name: minutes
        schema:
          type: integer
          default: 60
        description: Número de minutos para verificar alterações retroativamente.
    responses:
      200:
        description: Sincronização incremental iniciada e concluída com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Sincronização incremental de pessoas concluída."
                duration_seconds:
                  type: number
                  format: float
                lookback_minutes:
                  type: integer
                stats:
                  type: object
                  properties:
                    pf_processed: { type: integer }
                    pf_failed: { type: integer }
                    pj_processed: { type: integer }
                    pj_failed: { type: integer }
      400:
        description: Parâmetro 'minutes' inválido.
      401:
        description: Não autorizado.
      403:
        description: Proibido (usuário não é administrador).
      500:
        description: Erro interno ou erro durante a sincronização.
      503:
        description: Serviço de sincronização indisponível.
    """
    logger.info("Requisição recebida para disparar sincronização incremental de pessoas.")
    start_time = time.time()

    # Obtém o lookback em minutos do query parameter
    try:
        lookback_minutes = int(request.args.get('minutes', 60))
        if lookback_minutes <= 0:
            raise ValueError("Minutes must be positive.")
    except (ValueError, TypeError):
        logger.warning("Parâmetro 'minutes' inválido na query string. Usando padrão 60.")
        return jsonify({"error": "Parâmetro 'minutes' deve ser um inteiro positivo."}), 400

    try:
        sync_service = _get_person_sync_service()
        # ATENÇÃO: Chamada síncrona.
        sync_stats = sync_service.perform_incremental_sync(lookback_minutes=lookback_minutes)
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"Sincronização incremental de pessoas (últimos {lookback_minutes} min) concluída em {duration:.2f} segundos.")

        return jsonify({
            "message": "Sincronização incremental de pessoas concluída.",
            "duration_seconds": round(duration, 2),
            "lookback_minutes": lookback_minutes,
            "stats": sync_stats
        }), 200

    except ServiceError as e:
        logger.error(f"Erro de serviço durante a sincronização incremental: {e.message}", exc_info=True)
        return jsonify({"error": e.message}), e.status_code
    except ApiError as e:
        logger.error(f"Erro de API durante a sincronização incremental: {e.message}", exc_info=True)
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.critical(f"Erro inesperado ao disparar sincronização incremental: {e}", exc_info=True)
        return jsonify({"error": "Ocorreu um erro inesperado durante a sincronização."}), 500


@sync_bp.route('/statistics/full', methods=['POST'])
@admin_required # Protege a rota
def trigger_full_statistics_sync():
    """
    Dispara a sincronização completa das Estatísticas de todos os clientes
    presentes no cache local. Use com cautela, pode ser demorado.
    ---
    tags: [Synchronization]
    security:
      - bearerAuth: []
    responses:
      200:
        description: Sincronização de estatísticas iniciada e concluída com sucesso.
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Sincronização completa de estatísticas concluída."
                duration_seconds:
                  type: number
                  format: float
                stats:
                  type: object
                  properties:
                    stats_synced: { type: integer }
                    stats_failed: { type: integer }
      401:
        description: Não autorizado.
      403:
        description: Proibido.
      500:
        description: Erro interno ou erro durante a sincronização.
      503:
        description: Serviço de sincronização indisponível.
    """
    logger.info("Requisição recebida para disparar sincronização completa de estatísticas.")
    start_time = time.time()
    try:
        sync_service = _get_person_sync_service()
        # ATENÇÃO: Chamada síncrona. Pode demorar MUITO se houver muitos clientes.
        sync_stats = sync_service.sync_all_statistics()
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"Sincronização completa de estatísticas concluída em {duration:.2f} segundos.")

        return jsonify({
            "message": "Sincronização completa de estatísticas concluída.",
            "duration_seconds": round(duration, 2),
            "stats": { # Renomear chaves para consistência com a API
                "statistics_synced": sync_stats.get("synced", 0),
                "statistics_failed": sync_stats.get("failed", 0),
            }
        }), 200

    except ServiceError as e:
        logger.error(f"Erro de serviço durante a sincronização de estatísticas: {e.message}", exc_info=True)
        return jsonify({"error": e.message}), e.status_code
    except ApiError as e:
        logger.error(f"Erro de API durante a sincronização de estatísticas: {e.message}", exc_info=True)
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.critical(f"Erro inesperado ao disparar sincronização de estatísticas: {e}", exc_info=True)
        return jsonify({"error": "Ocorreu um erro inesperado durante a sincronização de estatísticas."}), 500