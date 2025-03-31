# src/erp_integration/__init__.py
# Makes 'erp_integration' a package. Exports ERP service classes.

from .erp_auth_service import ErpAuthService
from .erp_balance_service import ErpBalanceService
from .erp_cost_service import ErpCostService
from .erp_person_service import ErpPersonService
from .erp_product_service import ErpProductService
from .erp_fiscal_service import ErpFiscalService
from .erp_accounts_receivable_service import ErpAccountsReceivableService # Added Accounts Receivable service

# Instantiate singleton for ERP Auth if desired, as it's likely stateless
# and used by other ERP services.
erp_auth_service = ErpAuthService()

# Other services might be instantiated here or passed the auth service instance
# when they are created (dependency injection).

__all__ = [
    "ErpAuthService",
    "erp_auth_service", # Export instance too
    "ErpBalanceService",
    "ErpCostService",
    "ErpPersonService",
    "ErpProductService",
    "ErpFiscalService",
    "ErpAccountsReceivableService", # Added to exports
]