# src/domain/__init__.py
# Makes 'domain' a package. Exports domain models (Core App + ERP Cache).

# --- Core Application ORM Models ---
from .user import User, UserPermissions
from .observation import Observation # Observation específica do produto

# --- ERP Cache ORM Models ---
from .erp_cache import (
    Person as ErpPerson,
    IndividualDetail as ErpIndividualDetail,
    LegalEntityDetail as ErpLegalEntityDetail,
    Address as ErpAddress,
    Phone as ErpPhone,
    Email as ErpEmail,
    ErpPersonObservation, # <<<--- ATUALIZADO AQUI
    AdditionalField as ErpAdditionalField,
    Classification as ErpClassification,
    Reference as ErpReference,
    RelatedPerson as ErpRelatedPerson,
    Representative as ErpRepresentative,
    Preference as ErpPreference,
    Familiar as ErpFamiliar,
    Partner as ErpPartner,
    Contact as ErpContact,
    SocialNetwork as ErpSocialNetwork,
    PaymentMethod as ErpPaymentMethod,
    PersonStatistics as ErpPersonStatistics
)

# --- Dataclasses (DTOs / Non-cached ERP Models) ---
from .balance import Balance, ProductItem, ProductResponse
from .cost import Cost, ProductCost, CostResponse
from .fabric_details import FabricDetailsItem, FabricDetailValue
# Manter DTOs de pessoa se ainda usados
from .person import Address, Phone, Email, IndividualDataModel, LegalEntityDataModel, PersonStatisticsResponseModel
from .fiscal import FormattedInvoiceListItem, InvoiceXmlOutDto, DanfeRequestModel, DanfeResponseModel
from .accounts_receivable import (
    DocumentChangeModel, DocumentFilterModel, DocumentRequestModel, DocumentModel,
    DocumentResponseModel, BankSlipRequestModel, AccountsReceivableTomasResponseModel,
    FormattedReceivableListItem, CalculatedValuesModel, InvoiceDataModel
)


# --- Export List (`__all__`) ---
__all__ = [
    # Core ORM Models
    "User", "UserPermissions",
    "Observation", # Observação de Produto

    # ERP Cache ORM Models (com Alias)
    "ErpPerson",
    "ErpIndividualDetail",
    "ErpLegalEntityDetail",
    "ErpAddress",
    "ErpPhone",
    "ErpEmail",
    "ErpPersonObservation", # <<<--- ATUALIZADO AQUI
    "ErpAdditionalField",
    "ErpClassification",
    "ErpReference",
    "ErpRelatedPerson",
    "ErpRepresentative",
    "ErpPreference",
    "ErpFamiliar",
    "ErpPartner",
    "ErpContact",
    "ErpSocialNetwork",
    "ErpPaymentMethod",
    "ErpPersonStatistics",

    # Dataclasses / DTOs
    "Balance", "ProductItem", "ProductResponse",
    "Cost", "ProductCost", "CostResponse",
    "FabricDetailsItem", "FabricDetailValue",
    "Address", "Phone", "Email", "IndividualDataModel", "LegalEntityDataModel", "PersonStatisticsResponseModel",
    "FormattedInvoiceListItem", "InvoiceXmlOutDto", "DanfeRequestModel", "DanfeResponseModel",
    "DocumentChangeModel", "DocumentFilterModel", "DocumentRequestModel", "DocumentModel",
    "DocumentResponseModel", "BankSlipRequestModel", "AccountsReceivableTomasResponseModel",
    "FormattedReceivableListItem", "CalculatedValuesModel", "InvoiceDataModel"
]