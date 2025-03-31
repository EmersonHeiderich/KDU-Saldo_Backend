# src/api/routes/accounts_receivable.py
# Defines API endpoints for the Accounts Receivable module.

from flask import Blueprint, request, jsonify, current_app, Response
from src.services.accounts_receivable_service import AccountsReceivableService
from src.api.decorators import login_required, accounts_receivable_access_required # Use new decorator
from src.api.errors import ApiError, ErpIntegrationError, NotFoundError, ValidationError, ServiceError
from src.utils.logger import logger
from src.config import config

accounts_receivable_bp = Blueprint('accounts_receivable', __name__)

# Helper to get Service instance
def _get_ar_service() -> AccountsReceivableService:
    service = current_app.config.get('accounts_receivable_service')
    if not service:
        logger.critical("AccountsReceivableService not found in application config!")
        raise ServiceError("Accounts Receivable service is unavailable.", 503)
    return service

@accounts_receivable_bp.route('/search', methods=['POST'])
@login_required
@accounts_receivable_access_required # Apply permission check
def search_receivables():
    """
    Searches for accounts receivable documents based on provided filters.
    Handles pagination and customer name enrichment.
    ---
    tags: [Accounts Receivable]
    security:
      - bearerAuth: []
    requestBody:
      required: true
      description: JSON payload containing filters, pagination, order, and expand options.
      content:
        application/json:
          schema:
            # Ideally reference the DocumentRequestModel schema defined elsewhere
            # For now, define structure inline or reference external file if using swagger gen
            type: object
            properties:
              filter:
                type: object
                description: "Object containing various filter fields (see DocumentFilterModel)."
                # Add example filter properties here if needed
                example: {"customerCpfCnpjList": ["11122233300"], "startExpiredDate": "2023-01-01"}
              expand:
                type: string
                description: "Comma-separated list of fields to expand (e.g., 'check,invoice,commissioneds,calculateValue'). 'calculateValue' and 'invoice' are implicitly added if needed."
                example: "check,commissions"
              order:
                type: string
                description: "Comma-separated list for ordering (e.g., '-expiredDate,receivableCode')."
                example: "-expiredDate"
              page:
                type: integer
                description: "Page number (default: 1)"
                default: 1
              pageSize:
                type: integer
                description: "Items per page (default/max: 100)"
                default: 100
    responses:
      200:
        description: List of receivable documents found with pagination info.
        content:
          application/json:
            schema:
              type: object
              properties:
                items:
                  type: array
                  items:
                    # Define schema for FormattedReceivableListItem
                    type: object
                    properties:
                      customer_code: { type: integer, nullable: true }
                      customer_cpf_cnpj: { type: string, nullable: true }
                      customer_name: { type: string, nullable: true }
                      invoice_number: { type: integer, nullable: true }
                      document_number: { type: integer, nullable: true } # receivableCode
                      installment_number: { type: integer, nullable: true }
                      bearer_name: { type: string, nullable: true }
                      issue_date: { type: string, format: "date-time", nullable: true }
                      expired_date: { type: string, format: "date-time", nullable: true }
                      days_late: { type: integer, nullable: true }
                      payment_date: { type: string, format: "date-time", nullable: true }
                      value_original: { type: number, format: "float", nullable: true }
                      value_increase: { type: number, format: "float", nullable: true }
                      value_rebate: { type: number, format: "float", nullable: true }
                      value_paid: { type: number, format: "float", nullable: true }
                      value_corrected: { type: number, format: "float", nullable: true }
                      status: { type: integer, nullable: true, description: "1=Normal, 2=Devolvido, 3=Cancelado, 4=Quebrada" }
                      document_type: { type: integer, nullable: true, description: "e.g., 1=Fatura, 2=Cheque..." }
                      billing_type: { type: integer, nullable: true, description: "e.g., 1=Venda Vista, 2=Venda Prazo..." }
                      discharge_type: { type: integer, nullable: true, description: "e.g., 0=Não Baixado, 1=Via Recebimento..." }
                      charge_type: { type: integer, nullable: true, description: "e.g., 0=Não Cobrança, 1=Simples..." }
                page: { type: integer }
                pageSize: { type: integer }
                totalItems: { type: integer }
                totalPages: { type: integer }
                hasNext: { type: boolean }
      400:
        description: Bad request (Invalid JSON, invalid filters or parameters).
      401:
        description: Unauthorized.
      403:
        description: Forbidden (User lacks permission).
      500:
        description: Internal server error or ERP integration error.
      503:
        description: Service unavailable.
    """
    logger.info("Search accounts receivable request received.")
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON payload type. Expected an object."}), 400

    # Extract filters and pagination
    raw_filters = data.get('filter')
    expand = data.get('expand')
    order = data.get('order')
    try:
        page = int(data.get('page', 1))
        page_size = int(data.get('pageSize', 100)) # Use AR page size limit
    except (ValueError, TypeError):
         return jsonify({"error": "Invalid page or pageSize parameters. Must be integers."}), 400

    try:
        service = _get_ar_service()
        result = service.search_receivables(raw_filters, page, page_size, expand, order)
        return jsonify(result), 200

    except ValidationError as e:
        logger.warning(f"Validation error searching receivables: {e}")
        return jsonify({"error": str(e)}), 400
    except NotFoundError as e:
        logger.warning(f"Not found error searching receivables: {e}")
        # Return 200 with empty list for search not found? Or 404?
        # Let's follow existing pattern and maybe return 200 OK with empty data for search misses
        return jsonify({ "items": [], "page": page, "pageSize": page_size, "totalItems": 0, "totalPages": 0, "hasNext": False }), 200
        # return jsonify({"error": str(e)}), 404 # Alternative: return 404
    except ServiceError as e:
        logger.error(f"Service error searching receivables: {e.message}", exc_info=True if e.status_code >= 500 else False)
        return jsonify({"error": e.message}), e.status_code
    except ApiError as e: # Catch other specific API errors if needed
        logger.error(f"API error searching receivables: {e.message}", exc_info=True if e.status_code >= 500 else False)
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error searching receivables: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred while searching receivables."}), 500


@accounts_receivable_bp.route('/boleto', methods=['POST'])
@login_required
@accounts_receivable_access_required # Apply permission check
def generate_boleto():
    """
    Generates and returns the Bank Slip (Boleto) PDF for a specific installment.
    ---
    tags: [Accounts Receivable]
    security:
      - bearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            # Reference BankSlipRequestModel schema
            type: object
            properties:
              branchCode:
                type: integer
                description: "Código da empresa (max 4)."
                example: 1
              customerCode:
                type: integer
                description: "Código do cliente (max 9)."
                example: 12345
              customerCpfCnpj:
                type: string
                description: "CPF/CNPJ do cliente (alternativa a customerCode)."
                example: "11122233300"
              receivableCode:
                type: integer
                format: int64 # As per swagger
                description: "Código da fatura (max 10)."
                example: 98765
              installmentNumber:
                type: integer
                description: "Número da parcela (max 3)."
                example: 1
            required: [branchCode, customerCode, receivableCode, installmentNumber]
    responses:
      200:
        description: Boleto PDF content.
        content:
          application/pdf:
            schema:
              type: string
              format: binary
      400:
        description: Bad request (Invalid JSON, missing required fields, validation error).
      401:
        description: Unauthorized.
      403:
        description: Forbidden (User lacks permission).
      404:
        description: Boleto could not be generated (e.g., installment not found or not eligible).
      500:
        description: Internal server error or ERP integration error.
      502:
        description: Error communicating with ERP during Boleto generation.
      503:
        description: Service unavailable.
    """
    logger.info("Generate boleto request received.")
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON payload type. Expected an object."}), 400

    # Basic check for required fields
    required = ['branchCode', 'customerCode', 'receivableCode', 'installmentNumber']
    if not all(field in data for field in required):
         missing = [field for field in required if field not in data]
         return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        service = _get_ar_service()
        pdf_bytes = service.generate_boleto_pdf(data)

        doc_num = data.get('receivableCode', 'unknown')
        inst_num = data.get('installmentNumber', 'unknown')
        filename = f"boleto_{doc_num}_{inst_num}.pdf"

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'inline; filename="{filename}"'
            }
        )

    except ValidationError as e:
        logger.warning(f"Validation error generating boleto: {e}")
        return jsonify({"error": str(e)}), 400
    except NotFoundError as e:
        logger.warning(f"Boleto generation failed - Not Found: {e}")
        return jsonify({"error": str(e)}), 404
    except ServiceError as e:
        logger.error(f"Service error generating boleto: {e.message}", exc_info=True if e.status_code >= 500 else False)
        status_code = e.status_code
        # Check if underlying cause was ERP specific status code
        if isinstance(e.__cause__, ErpIntegrationError) and hasattr(e.__cause__, 'status_code'):
             status_code = e.__cause__.status_code # Use original ERP status if available
        return jsonify({"error": e.message}), status_code
    except ApiError as e: # Catch other specific API errors if needed
        logger.error(f"API error generating boleto: {e.message}", exc_info=True if e.status_code >= 500 else False)
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error generating boleto: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred while generating the boleto."}), 500