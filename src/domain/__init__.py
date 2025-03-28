# src/domain/__init__.py
# Makes 'domain' a package. Exports domain models.

from .balance import Balance, ProductItem, ProductResponse
from .cost import Cost, ProductCost, CostResponse
from .fabric_details import FabricDetailsItem, FabricDetailValue
from .observation import Observation
from .person import Address, Phone, Email, IndividualDataModel, LegalEntityDataModel, PersonStatisticsResponseModel
from .user import User, UserPermissions
from .fiscal import FormattedInvoiceListItem, InvoiceXmlOutDto, DanfeRequestModel, DanfeResponseModel

__all__ = [
    "Balance", "ProductItem", "ProductResponse",
    "Cost", "ProductCost", "CostResponse",
    "FabricDetailsItem", "FabricDetailValue",
    "Observation",
    "Address", "Phone", "Email", "IndividualDataModel", "LegalEntityDataModel", "PersonStatisticsResponseModel",
    "User", "UserPermissions",
    "FormattedInvoiceListItem",
    "InvoiceXmlOutDto",
    "DanfeRequestModel",
    "DanfeResponseModel",
]