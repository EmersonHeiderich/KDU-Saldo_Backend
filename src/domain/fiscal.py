# src/domain/fiscal.py
# Defines data models related to Fiscal module operations (DANFE, XML, Invoice List).

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from src.utils.logger import logger

@dataclass(frozen=True)
class FormattedInvoiceListItem:
    """Represents essential data for an invoice in a list view, formatted for API response."""
    status: Optional[str] = None        # Mapped from electronicInvoiceStatus
    recipient_name: Optional[str] = None # Mapped from personName
    sales_order_code: Optional[int] = None     # Mapped from salesOrder -> orderCode
    invoice_number: Optional[int] = None   # Mapped from invoiceCode
    invoice_series: Optional[str] = None    # Mapped from serialCode
    issue_date: Optional[str] = None     # Mapped from eletronic -> receivementDate or issueDate
    total_value: Optional[float] = None  # Mapped from totalValue
    total_quantity: Optional[float] = None     # Mapped from quantity
    operation_name: Optional[str] = None # Mapped from operatioName
    shipping_company_name: Optional[str] = None # Mapped from shippingCompany -> shippingCompanyName
    access_key: Optional[str] = None     # Mapped from eletronic -> accessKey

    # Classmethod from_dict is removed - formatting happens in service layer's _format_invoice_list_item

    def to_dict(self) -> Dict[str, Any]:
        """Converts the FormattedInvoiceListItem object to a dictionary."""
        return self.__dict__


@dataclass(frozen=True)
class InvoiceXmlOutDto:
    """
    Represents the response from the GET /xml-contents/{accessKey} endpoint. Immutable.
    Corresponds to the InvoiceXmlOutDto schema.
    """
    processing_type: Optional[str] = None # Maps to ElectronicInvoiceStatusType enum
    main_invoice_xml: Optional[str] = None # Base64 encoded XML
    cancel_invoice_xml: Optional[str] = None # Base64 encoded XML

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional['InvoiceXmlOutDto']:
        if not isinstance(data, dict):
            logger.warning(f"Invalid data type for InvoiceXmlOutDto.from_dict: {type(data)}")
            return None
        return cls(
            processing_type=data.get('processingType'),
            main_invoice_xml=data.get('mainInvoiceXml'),
            cancel_invoice_xml=data.get('cancelInvoiceXml')
        )

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

@dataclass(frozen=True)
class DanfeRequestModel:
    """
    Represents the request body for the POST /danfe-search endpoint. Immutable.
    Corresponds to the DanfeRequestModel schema.
    """
    main_invoice_xml: str # Base64 encoded XML - marked as required in swagger
    nfe_document_type: Optional[int] = None # Maps to NfeDocumentType enum (1=Normal, 2=Simplified)

    def to_dict(self) -> Dict[str, Any]:
        # Return only non-None fields to match typical API expectations
        d = {"mainInvoiceXml": self.main_invoice_xml}
        if self.nfe_document_type is not None:
            d["nfeDocumentType"] = self.nfe_document_type
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional['DanfeRequestModel']:
        if not isinstance(data, dict):
            logger.warning(f"Invalid data type for DanfeRequestModel.from_dict: {type(data)}")
            return None
        main_xml = data.get('mainInvoiceXml')
        if not main_xml:
            logger.warning("Missing required 'mainInvoiceXml' for DanfeRequestModel.")
            return None
        return cls(
            main_invoice_xml=main_xml,
            nfe_document_type=data.get('nfeDocumentType')
        )

@dataclass(frozen=True)
class DanfeResponseModel:
    """
    Represents the response from the POST /danfe-search endpoint. Immutable.
    Corresponds to the DanfeResponseModel schema.
    """
    danfe_pdf_base64: Optional[str] = None # Base64 encoded PDF

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional['DanfeResponseModel']:
        if not isinstance(data, dict):
            logger.warning(f"Invalid data type for DanfeResponseModel.from_dict: {type(data)}")
            return None
        # Adjust key based on testing if needed (e.g., if API returns 'pdfBase64')
        return cls(
            danfe_pdf_base64=data.get('danfePdfBase64')
        )

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__