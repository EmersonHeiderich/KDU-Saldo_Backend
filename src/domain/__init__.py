# src/domain/__init__.py
# Makes 'domain' a package. Exports domain models.

# ORM Models (já convertidos ou serão nos próximos passos)
from .user import User, UserPermissions
from .observation import Observation

# Dataclasses (ainda não convertidos para ORM, se aplicável)
# Se converter todos para ORM, remova os imports específicos de dataclasses
# que foram substituídos.
from .balance import Balance, ProductItem, ProductResponse
from .cost import Cost, ProductCost, CostResponse
from .fabric_details import FabricDetailsItem, FabricDetailValue
from .person import Address, Phone, Email, IndividualDataModel, LegalEntityDataModel, PersonStatisticsResponseModel
from .fiscal import FormattedInvoiceListItem, InvoiceXmlOutDto, DanfeRequestModel, DanfeResponseModel
from .accounts_receivable import (
    DocumentChangeModel, DocumentFilterModel, DocumentRequestModel, DocumentModel,
    DocumentResponseModel, BankSlipRequestModel, AccountsReceivableTomasResponseModel,
    FormattedReceivableListItem, CalculatedValuesModel, InvoiceDataModel
)


# Mantemos todos os exports por enquanto. Se um modelo for *completamente*
# substituído e não for mais usado como Dataclass em nenhum lugar,
# pode ser removido daqui. No entanto, é seguro manter todos.
__all__ = [
    # ORM Models
    "User", "UserPermissions",
    "Observation",

    # Dataclasses (Potencialmente a serem convertidos ou usados como DTOs)
    "Balance", "ProductItem", "ProductResponse",
    "Cost", "ProductCost", "CostResponse",
    "FabricDetailsItem", "FabricDetailValue",
    "Address", "Phone", "Email", "IndividualDataModel", "LegalEntityDataModel", "PersonStatisticsResponseModel",
    "FormattedInvoiceListItem", "InvoiceXmlOutDto", "DanfeRequestModel", "DanfeResponseModel",
    "DocumentChangeModel", "DocumentFilterModel", "DocumentRequestModel", "DocumentModel",
    "DocumentResponseModel", "BankSlipRequestModel", "AccountsReceivableTomasResponseModel",
    "FormattedReceivableListItem", "CalculatedValuesModel", "InvoiceDataModel"
]