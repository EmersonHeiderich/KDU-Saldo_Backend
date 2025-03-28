# src/api/routes/fiscal.py
# Defines API endpoints for the Fiscal module.

from typing import Any, Dict
from flask import Blueprint, request, jsonify, current_app, Response
import base64
from src.services.fiscal_service import FiscalService
from src.api.decorators import login_required, fiscal_access_required
from src.api.errors import ApiError, ErpIntegrationError, NotFoundError, ValidationError, ServiceError
from src.utils.logger import logger
from src.config import config # For default fiscal page size

fiscal_bp = Blueprint('fiscal', __name__)

# Helper to get FiscalService instance
def _get_fiscal_service() -> FiscalService:
    service = current_app.config.get('fiscal_service')
    if not service:
        logger.critical("FiscalService not found in application config!")
        raise ServiceError("Fiscal service is unavailable.", 503)
    return service

@fiscal_bp.route('/invoices/search', methods=['POST'])
@login_required
@fiscal_access_required
def search_fiscal_invoices():
    """
    Searches for fiscal invoices based on provided filters.
    Handles pagination.
    ---
    tags: [Fiscal]
    security:
      - bearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              page:
                type: integer
                description: "Page number (default: 1)"
                default: 1
              pageSize:
                type: integer
                description: f"Items per page (default: {config.FISCAL_PAGE_SIZE}, max: 100)"
                default: config.FISCAL_PAGE_SIZE
              # <<<--- MODIFIED: Use a single field for customer input --- >>>
              customer_code_cpf_cnpj:
                type: string
                description: "Customer Code, CPF (11 digits), or CNPJ (14 digits). Can be comma-separated for multiple values (only for codes or only for CPF/CNPJ, not mixed)."
                example: "389" # or "11122233344,55566677788899"
              # ----------------------------------------------------------
              invoice_number:
                type: string
                description: "Single number, comma-separated list, or range (e.g., 100-150)."
                example: "1001,1005"
              start_date:
                type: string
                format: date-time
                description: "Start issue date (ISO 8601 format, e.g., YYYY-MM-DD or YYYY-MM-DDTHH:mm:ss)."
                example: "2023-10-01"
              end_date:
                type: string
                format: date-time
                description: "End issue date (ISO 8601 format)."
                example: "2023-10-31T23:59:59"
              status:
                type: string
                description: "Comma-separated list of statuses (e.g., Authorized, Canceled)."
                example: "Authorized"
    responses:
      200:
        description: List of invoices found with pagination info.
        content:
          application/json:
            schema:
              type: object
              properties:
                items:
                  type: array
                  items:
                     $ref: '#/components/schemas/FormattedInvoiceListItem'
                page: { type: integer }
                pageSize: { type: integer }
                totalItems: { type: integer }
                totalPages: { type: integer }
      400:
        description: Bad request (Invalid filters or parameters).
      401:
        description: Unauthorized.
      403:
        description: Forbidden (User lacks permission).
      500:
        description: Internal server error or ERP integration error.
      503:
        description: Service unavailable.
    """
    logger.info("Search fiscal invoices request received.")
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    if not isinstance(data, dict):
         return jsonify({"error": "Invalid JSON payload type. Expected an object."}), 400

    # Extract filters from request data
    filters = {}
    customer_input = data.get("customer_code_cpf_cnpj")
    invoice_number_input = data.get("invoice_number")
    start_date_input = data.get("start_date")
    end_date_input = data.get("end_date")
    status_input = data.get("status")

    # --- START: Intelligent Customer Filter Mapping ---
    if customer_input:
        customer_input_str = str(customer_input).strip()
        # Basic check: if it contains only digits and maybe commas
        is_potentially_numeric = all(c.isdigit() or c == ',' for c in customer_input_str.replace(" ", ""))

        if is_potentially_numeric:
             # Check length characteristics to distinguish code/list-of-codes from CPF/CNPJ
             codes = [c.strip() for c in customer_input_str.split(',') if c.strip()]
             # Heuristic: Assume codes are shorter than 11 digits, CPF/CNPJ are 11 or 14
             if all(len(code) < 11 for code in codes):
                 logger.debug(f"Treating customer input '{customer_input_str}' as customer_code")
                 filters["customer_code"] = customer_input_str # Pass comma-separated string to service
             elif all(len(code) == 11 or len(code) == 14 for code in codes):
                 logger.debug(f"Treating customer input '{customer_input_str}' as customer_cpf_cnpj")
                 filters["customer_cpf_cnpj"] = customer_input_str # Pass comma-separated string to service
             else:
                 # Ambiguous or mixed format
                 logger.warning(f"Ambiguous customer input format: '{customer_input_str}'. Could not determine if code(s) or CPF/CNPJ(s).")
                 # Return error or try one? Let's return an error for clarity.
                 return jsonify({"error": "Invalid format for 'customer_code_cpf_cnpj'. Provide only code(s) or only CPF/CNPJ(s), not mixed or invalid lengths."}), 400
        else:
             # Contains non-digits (excluding comma/space), definitely not code/CPF/CNPJ
             return jsonify({"error": "Invalid characters found in 'customer_code_cpf_cnpj'."}), 400
    # --- END: Intelligent Customer Filter Mapping ---


    # Add other filters if they exist
    if invoice_number_input:
        filters["invoice_number"] = invoice_number_input
    if start_date_input:
        filters["start_date"] = start_date_input
    if end_date_input:
        filters["end_date"] = end_date_input
    if status_input:
        filters["status"] = status_input

    # Extract pagination parameters with validation
    try:
        page = int(data.get('page', 1))
        page_size = int(data.get('pageSize', config.FISCAL_PAGE_SIZE))

        if page < 1:
            page = 1
        if page_size < 1:
            page_size = config.FISCAL_PAGE_SIZE # Fallback to default
        # Service layer will clamp page_size if > 100

    except (ValueError, TypeError):
         logger.warning(f"Invalid pagination parameters received: page={data.get('page')}, pageSize={data.get('pageSize')}")
         return jsonify({"error": "Invalid page or pageSize parameters. Must be integers."}), 400

    try:
        fiscal_service = _get_fiscal_service()
        # Pass the filters dict (now containing the *correct* key based on input)
        result: Dict[str, Any] = fiscal_service.search_invoices(filters, page, page_size)
        return jsonify(result), 200

    except ValidationError as e:
        logger.warning(f"Validation error searching invoices: {e}")
        return jsonify({"error": str(e)}), 400
    except NotFoundError as e:
        logger.warning(f"Unexpected NotFoundError during invoice search: {e}")
        return jsonify({"error": str(e)}), 404
    except ServiceError as e:
        logger.error(f"Service error searching invoices: {e.message}", exc_info=True if e.status_code >= 500 else False)
        return jsonify({"error": e.message}), e.status_code
    except ApiError as e:
        logger.error(f"API error searching invoices: {e.message}", exc_info=True if e.status_code >= 500 else False)
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error searching invoices: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred while searching invoices."}), 500


@fiscal_bp.route('/danfe/<string:access_key>', methods=['GET'])
@login_required
@fiscal_access_required
def generate_danfe(access_key: str):
    """
    Generates and returns the DANFE PDF for a given invoice access key.
    ---
    tags: [Fiscal]
    security:
      - bearerAuth: []
    parameters:
      - in: path
        name: access_key
        schema:
          type: string
          pattern: '^\d{44}$' # Regex for 44 digits
        required: true
        description: The 44-digit access key of the NF-e.
    responses:
      200:
        description: DANFE PDF content.
        content:
          application/pdf:
            schema:
              type: string
              format: binary
      400:
        description: Bad request (Invalid access key format).
      401:
        description: Unauthorized.
      403:
        description: Forbidden (User lacks permission).
      404:
        description: Invoice or DANFE not found for the given access key.
      500:
        description: Internal server error or ERP integration error.
      502:
        description: Error communicating with ERP during DANFE generation.
      503:
        description: Service unavailable.
    """
    logger.info(f"Generate DANFE request received for access key: ...{access_key[-6:]}")

    try:
        fiscal_service = _get_fiscal_service()
        pdf_bytes = fiscal_service.generate_danfe_pdf(access_key)

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'inline; filename="danfe_{access_key}.pdf"'
            }
        )

    except ValidationError as e:
        logger.warning(f"Validation error generating DANFE for key ...{access_key[-6:]}: {e}")
        return jsonify({"error": str(e)}), 400
    except NotFoundError as e:
        logger.warning(f"DANFE/XML not found for key ...{access_key[-6:]}: {e}")
        return jsonify({"error": str(e)}), 404
    except ServiceError as e:
        logger.error(f"Service error generating DANFE for key ...{access_key[-6:]}: {e.message}", exc_info=True if e.status_code >= 500 else False)
        status_code = e.status_code if hasattr(e, 'status_code') and e.status_code else 500
        if isinstance(e.__cause__, ErpIntegrationError) and hasattr(e.__cause__, 'status_code'):
             status_code = e.__cause__.status_code
        return jsonify({"error": e.message}), status_code
    except ApiError as e:
        logger.error(f"API error generating DANFE: {e.message}", exc_info=True if e.status_code >= 500 else False)
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error generating DANFE for key ...{access_key[-6:]}: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred while generating the DANFE."}), 500


# Define Schema for OpenAPI (ensure it matches FormattedInvoiceListItem)
components = {
    "schemas": {
        "FormattedInvoiceListItem": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "nullable": True},
                "recipient_name": {"type": "string", "nullable": True},
                "sales_order_code": {"type": "integer", "nullable": True},
                "invoice_number": {"type": "integer", "nullable": True},
                "invoice_series": {"type": "string", "nullable": True},
                "issue_date": {"type": "string", "format": "date-time", "nullable": True},
                "total_value": {"type": "number", "format": "float", "nullable": True},
                "total_quantity": {"type": "number", "format": "float", "nullable": True},
                "operation_name": {"type": "string", "nullable": True},
                "shipping_company_name": {"type": "string", "nullable": True},
                "access_key": {"type": "string", "nullable": True, "maxLength": 44, "minLength": 44}
            }
        }
    }
}