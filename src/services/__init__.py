# src/services/__init__.py
# Makes 'services' a package. Exports service classes.

from .auth_service import AuthService
from .customer_service import CustomerService
from .fabric_service import FabricService
from .observation_service import ObservationService
from .product_service import ProductService
from .fiscal_service import FiscalService
from .accounts_receivable_service import AccountsReceivableService
from .fiscal_sync_service import FiscalSyncService # <<<--- ADDED

# Optionally initialize instances here if they are stateless singletons
# and don't require request context or specific configurations per request.
# However, it's often better to instantiate them in the app factory or inject them.

# Example (if needed, but prefer instantiation in app factory):
# auth_service_instance = AuthService(...)
# observation_service_instance = ObservationService(...)

__all__ = [
    "AuthService",
    "CustomerService",
    "FabricService",
    "ObservationService",
    "ProductService",
    "FiscalService",
    "AccountsReceivableService",
    "FiscalSyncService", # <<<--- ADDED
]