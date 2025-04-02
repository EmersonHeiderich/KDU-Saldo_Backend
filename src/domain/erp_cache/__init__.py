# src/domain/erp_cache/__init__.py
# Torna 'erp_cache' um pacote e exporta os modelos ORM do cache.

# Importa modelos do cache de pessoas
from .person_cache import (
    Person,
    IndividualDetail,
    LegalEntityDetail,
    Address,
    Phone,
    Email,
    ErpPersonObservation,
    AdditionalField,
    Classification,
    Reference,
    RelatedPerson,
    Representative,
    Preference,
    Familiar,
    Partner,
    Contact,
    SocialNetwork,
    PaymentMethod
    # Note que CacheControlBase não precisa ser exportado, é interno.
)

# Importa modelos do cache de estatísticas
from .statistics_cache import PersonStatistics

# Lista de todos os modelos ORM do cache a serem exportados
__all__ = [
    "Person",
    "IndividualDetail",
    "LegalEntityDetail",
    "Address",
    "Phone",
    "Email",
    "ErpPersonObservation",
    "AdditionalField",
    "Classification",
    "Reference",
    "RelatedPerson",
    "Representative",
    "Preference",
    "Familiar",
    "Partner",
    "Contact",
    "SocialNetwork",
    "PaymentMethod",
    "PersonStatistics",
]