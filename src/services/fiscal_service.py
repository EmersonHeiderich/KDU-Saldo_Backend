# src/services/fiscal_service.py
# Contém lógica de negócio para o módulo Fiscal, agora lendo do DB local e gerando DANFE via ERP.

import base64
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# --- Serviços ERP (Necessário para DANFE/XML) ---
from src.erp_integration.erp_fiscal_service import ErpFiscalService

# --- Repositório Local e Session Manager ---
from src.database import get_db_session
from src.database.fiscal_repository import FiscalRepository

# --- Modelos ORM e DTOs ---
from src.domain.fiscal_orm import NotaFiscalOrm
from src.domain.fiscal import (
    FormattedInvoiceListItem, InvoiceXmlOutDto, DanfeResponseModel
)

# --- Utilitários e Erros ---
from src.utils.logger import logger
from src.utils.pdf_utils import decode_base64_to_bytes
from src.api.errors import ErpIntegrationError, ServiceError, NotFoundError, ValidationError, DatabaseError
from src.config import config
from sqlalchemy.exc import SQLAlchemyError

# Páginação padrão para busca local
LOCAL_FISCAL_PAGE_SIZE = 50

class FiscalService:
    """
    Service layer for handling fiscal operations.
    - Searches invoices from the LOCAL database (synced from ERP).
    - Generates DANFE PDF by fetching necessary data from ERP.
    """
    def __init__(self, fiscal_repository: FiscalRepository, erp_fiscal_service: ErpFiscalService):
        """
        Initializes the FiscalService.

        Args:
            fiscal_repository: Repository for accessing local fiscal data (ORM).
            erp_fiscal_service: Service for interacting with ERP for DANFE/XML.
        """
        self.fiscal_repository = fiscal_repository
        self.erp_fiscal_service = erp_fiscal_service
        logger.info("Serviço Fiscal inicializado (usando DB local para busca).")

    # --- Search Invoices (Local Database) ---
    def search_invoices(self, filters: Dict[str, Any], page: int = 1, page_size: int = LOCAL_FISCAL_PAGE_SIZE) -> Dict[str, Any]:
        """
        Searches for invoices in the LOCAL database based on filters and formats the results.

        Args:
            filters: Dictionary of filter criteria (keys should ideally match NotaFiscalOrm attributes or be mapped).
            page: Page number (starting from 1).
            page_size: Number of items per page.

        Returns:
            A dictionary containing the paginated list of formatted invoices.

        Raises:
            ValidationError: If filter validation fails (implementation needed).
            DatabaseError: If a database error occurs.
            ServiceError: For unexpected errors.
        """
        logger.info(f"Buscando notas fiscais no banco local com filtros: {filters}, Página: {page}, Itens por página: {page_size}")

        # Clamp page size (optional, based on preference for local search)
        if page_size < 1: page_size = LOCAL_FISCAL_PAGE_SIZE

        validated_filters = filters

        try:
            with get_db_session() as db:
                # Use the local repository search method
                invoice_orms, total_count = self.fiscal_repository.find_invoices_local(
                    db, validated_filters, page, page_size
                )

            # Format the ORM results into the desired API structure
            formatted_items = [self._format_invoice_list_item(orm) for orm in invoice_orms]

            total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

            result = {
                "items": formatted_items,
                "page": page,
                "pageSize": page_size,
                "totalItems": total_count,
                "totalPages": total_pages
            }
            logger.info(f"Busca concluída com sucesso. Encontrados {len(formatted_items)} notas fiscais para página {page}. Total de Itens: {total_count}")
            return result

        except ValidationError as e:
             logger.warning(f"Falha na validação dos filtros durante busca de notas fiscais: {e}")
             raise e
        except (DatabaseError, SQLAlchemyError) as e:
            logger.error(f"Erro de banco de dados durante busca de notas fiscais: {e}", exc_info=True)
            raise DatabaseError("Falha ao recuperar notas fiscais do banco de dados local.") from e
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar ou processar notas fiscais locais: {e}", exc_info=True)
            raise ServiceError(f"Ocorreu um erro inesperado durante a busca de notas fiscais: {e}") from e

    def _format_invoice_list_item(self, nf_orm: NotaFiscalOrm) -> Dict[str, Any]:
        """Formats a NotaFiscalOrm object into the desired list structure."""
        if not nf_orm:
            return {}

        # Get sales order code (handle potential absence of relationship data)
        sales_order_code = None
        try:
            if nf_orm.sales_orders and nf_orm.sales_orders[0]:
                 sales_order_code = nf_orm.sales_orders[0].order_code
        except Exception as rel_err:
            logger.warning(f"Não foi possível acessar relação sales_orders para NF {nf_orm.id}: {rel_err}")

        # Use the FormattedInvoiceListItem dataclass for structure and conversion
        formatted = FormattedInvoiceListItem(
            status=nf_orm.electronic_invoice_status,
            recipient_name=nf_orm.person_name,
            sales_order_code=sales_order_code,
            invoice_number=nf_orm.invoice_code,
            invoice_series=nf_orm.serial_code,
            issue_date=nf_orm.issue_date.isoformat() if nf_orm.issue_date else (nf_orm.invoice_date.isoformat() if nf_orm.invoice_date else None),
            total_value=float(nf_orm.total_value) if nf_orm.total_value is not None else None,
            total_quantity=float(nf_orm.quantity) if nf_orm.quantity is not None else None,
            operation_name=nf_orm.operation_name,
            shipping_company_name=nf_orm.shipping_company_name,
            access_key=nf_orm.access_key
        )
        return formatted.to_dict()

    # --- DANFE Generation (Still relies on ERP) ---
    def generate_danfe_pdf(self, access_key: str) -> bytes:
        """
        Generates the DANFE PDF for a given invoice access key by fetching data from ERP.
        """
        if not access_key or len(access_key) != 44 or not access_key.isdigit():
             raise ValidationError("Formato de chave de acesso inválido. Deve conter 44 dígitos.")

        logger.info(f"Gerando DANFE via ERP para chave de acesso: ...{access_key[-6:]}")
        try:
            # 1. Get XML Content (Raw) from ERP Service
            logger.debug(f"Etapa 1: Buscando XML do ERP para chave ...{access_key[-6:]}")
            xml_raw_dict = self.erp_fiscal_service.get_xml_content_raw(access_key)

            # Parse raw dict using DTO
            xml_dto = InvoiceXmlOutDto.from_dict(xml_raw_dict)
            if not xml_dto or not xml_dto.main_invoice_xml:
                 logger.error(f"Falha ao interpretar resposta do XML ou campo mainInvoiceXml ausente. Dados brutos: {xml_raw_dict}")
                 raise ServiceError(f"Conteúdo XML inválido ou ausente recebido do ERP para chave ...{access_key[-6:]}.")
            main_xml_base64 = xml_dto.main_invoice_xml
            logger.debug(f"Etapa 1: XML principal obtido com sucesso (Tamanho Base64: {len(main_xml_base64)}).")

            # 2. Get DANFE from XML (Raw) using ERP Service
            logger.debug(f"Etapa 2: Solicitando DANFE do ERP usando XML obtido...")
            danfe_raw_dict = self.erp_fiscal_service.get_danfe_from_xml_raw(main_xml_base64)

            # Parse raw dict using DTO
            danfe_dto = DanfeResponseModel.from_dict(danfe_raw_dict)
            if not danfe_dto or not danfe_dto.danfe_pdf_base64:
                 logger.error(f"Falha ao interpretar resposta do DANFE ou campo danfePdfBase64 ausente. Dados brutos: {danfe_raw_dict}")
                 raise ServiceError("DANFE PDF inválido ou ausente recebido do ERP.")
            pdf_base64 = danfe_dto.danfe_pdf_base64
            logger.debug(f"Etapa 2: DANFE PDF recebido e interpretado com sucesso (Tamanho Base64: {len(pdf_base64)}).")

            # 3. Decode Base64 to PDF bytes
            try:
                pdf_bytes = decode_base64_to_bytes(pdf_base64)
                logger.info(f"DANFE PDF gerado e decodificado com sucesso para chave ...{access_key[-6:]}.")
                return pdf_bytes
            except (ValueError, TypeError, RuntimeError) as decode_err:
                logger.error(f"Falha ao decodificar Base64 do DANFE PDF: {decode_err}", exc_info=True)
                raise ServiceError("Falha ao decodificar o PDF DANFE gerado.")

        except (NotFoundError, ValidationError) as e:
             logger.warning(f"Geração de DANFE falhou para chave ...{access_key[-6:]}: {e}")
             raise e
        except ErpIntegrationError as e:
             logger.error(f"Erro de integração com ERP durante geração de DANFE para chave ...{access_key[-6:]}: {e}", exc_info=False)
             status_code = e.status_code if hasattr(e, 'status_code') else 502
             raise ServiceError(f"Falha na comunicação com o ERP durante geração de DANFE: {e.message}", status_code=status_code) from e
        except ServiceError as e:
             logger.error(f"Erro de serviço durante geração de DANFE para chave ...{access_key[-6:]}: {e}", exc_info=True)
             raise e
        except Exception as e:
            logger.error(f"Erro inesperado ao gerar DANFE para chave de acesso ...{access_key[-6:]}: {e}", exc_info=True)
            raise ServiceError(f"Ocorreu um erro inesperado durante a geração do DANFE: {e}") from e