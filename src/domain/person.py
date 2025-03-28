# src/domain/person.py
# Defines data models related to Person data (Individuals, Legal Entities) from the ERP.

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from src.utils.logger import logger

@dataclass(frozen=True)
class Address:
    """Represents a person's address details. Immutable."""
    sequence_code: Optional[int] = None
    address_type_code: Optional[int] = None
    address_type: Optional[str] = None
    public_place: Optional[str] = None
    address: Optional[str] = None
    address_number: Optional[str] = None # API might return string
    complement: Optional[str] = None
    neighborhood: Optional[str] = None
    ibge_city_code: Optional[int] = None
    city_name: Optional[str] = None
    state_abbreviation: Optional[str] = None
    cep: Optional[str] = None
    bcb_country_code: Optional[int] = None
    country_name: Optional[str] = None
    post_office_box: Optional[str] = None # API might return string
    reference: Optional[str] = None
    is_default: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional['Address']:
        """Creates an Address object from a dictionary (e.g., from API)."""
        if not isinstance(data, dict):
            logger.warning(f"Invalid data type for Address.from_dict: {type(data)}")
            return None
        # Use .get with default None for Optional fields
        return cls(
            sequence_code=data.get('sequenceCode'),
            address_type_code=data.get('addressTypeCode'),
            address_type=data.get('addressType'),
            public_place=data.get('publicPlace'),
            address=data.get('address'),
            address_number=str(data['addressNumber']) if data.get('addressNumber') is not None else None,
            complement=data.get('complement'),
            neighborhood=data.get('neighborhood'),
            ibge_city_code=data.get('ibgeCityCode'),
            city_name=data.get('cityName'),
            state_abbreviation=data.get('stateAbbreviation'),
            cep=data.get('cep'),
            bcb_country_code=data.get('bcbCountryCode'),
            country_name=data.get('countryName'),
            post_office_box=str(data['postOfficeBox']) if data.get('postOfficeBox') is not None else None,
            reference=data.get('reference'),
            is_default=data.get('isDefault', False)
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Address object to a dictionary."""
        return self.__dict__

@dataclass(frozen=True)
class Phone:
    """Represents a person's phone number details. Immutable."""
    sequence: Optional[int] = None
    type_code: Optional[int] = None
    type_name: Optional[str] = None
    number: Optional[str] = None
    branch_line: Optional[str] = None # API might return string
    is_default: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional['Phone']:
        """Creates a Phone object from a dictionary (e.g., from API)."""
        if not isinstance(data, dict):
             logger.warning(f"Invalid data type for Phone.from_dict: {type(data)}")
             return None
        # Note the inconsistent capitalization in the original 'Sequence'
        return cls(
            sequence=data.get('Sequence') or data.get('sequence'), # Handle both cases
            type_code=data.get('typeCode'),
            type_name=data.get('typeName'),
            number=data.get('number'),
            branch_line=str(data['branchLine']) if data.get('branchLine') is not None else None,
            is_default=data.get('isDefault', False)
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Phone object to a dictionary."""
        return self.__dict__

@dataclass(frozen=True)
class Email:
    """Represents a person's email address details. Immutable."""
    sequence: Optional[int] = None
    type_code: Optional[int] = None
    type_name: Optional[str] = None
    email: Optional[str] = None
    is_default: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional['Email']:
        """Creates an Email object from a dictionary (e.g., from API)."""
        if not isinstance(data, dict):
            logger.warning(f"Invalid data type for Email.from_dict: {type(data)}")
            return None
        return cls(
            sequence=data.get('sequence'),
            type_code=data.get('typeCode'),
            type_name=data.get('typeName'),
            email=data.get('email'),
            is_default=data.get('isDefault', False)
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Email object to a dictionary."""
        return self.__dict__


@dataclass(frozen=True)
class IndividualDataModel:
    """Represents data for an individual (Pessoa Física). Immutable."""
    code: int
    cpf: str
    is_inactive: bool
    name: str
    rg: Optional[str] = None
    rg_federal_agency: Optional[str] = None
    birth_date: Optional[str] = None # Keep as string from API? Or parse to date? Keep str for now.
    branch_insert_code: Optional[int] = None
    addresses: List[Address] = field(default_factory=list)
    phones: List[Phone] = field(default_factory=list)
    emails: List[Email] = field(default_factory=list)
    is_customer: Optional[bool] = None
    is_supplier: Optional[bool] = None
    is_employee: Optional[bool] = None
    employee_status: Optional[str] = None
    customer_status: Optional[str] = None
    insert_date: Optional[str] = None # Keep as string
    # --- Other fields from original model (add as needed) ---
    marital_status: Optional[str] = None
    gender: Optional[str] = None
    # ctps: Optional[int] = None # Example of omitted fields, add back if needed
    # ... many other fields ...
    max_change_filter_date: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional['IndividualDataModel']:
        """Creates an IndividualDataModel from a dictionary (e.g., from API)."""
        if not isinstance(data, dict):
             logger.warning(f"Invalid data type for IndividualDataModel.from_dict: {type(data)}")
             return None

        code = data.get('code')
        cpf = data.get('cpf')
        name = data.get('name')

        if not code or not cpf or not name:
             logger.warning(f"Missing essential data (code, cpf, name) for IndividualDataModel: {data.get('code')}")
             return None

        # Process nested lists safely
        addresses_data = data.get('addresses', [])
        phones_data = data.get('phones', [])
        emails_data = data.get('emails', [])

        addresses = [Address.from_dict(addr) for addr in addresses_data if isinstance(addr, dict)]
        addresses = [addr for addr in addresses if addr is not None] # Filter out None results
        phones = [Phone.from_dict(phone) for phone in phones_data if isinstance(phone, dict)]
        phones = [phone for phone in phones if phone is not None]
        emails = [Email.from_dict(email) for email in emails_data if isinstance(email, dict)]
        emails = [email for email in emails if email is not None]

        return cls(
            code=code,
            cpf=cpf,
            is_inactive=data.get('isInactive', False),
            name=name,
            rg=data.get('rg'),
            rg_federal_agency=data.get('rgFederalAgency'),
            birth_date=data.get('birthDate'),
            branch_insert_code=data.get('branchInsertCode'),
            addresses=addresses,
            phones=phones,
            emails=emails,
            is_customer=data.get('isCustomer'),
            is_supplier=data.get('isSupplier'),
            is_employee=data.get('isEmployee'),
            employee_status=data.get('employeeStatus'),
            customer_status=data.get('customerStatus'),
            insert_date=data.get('insertDate'),
            marital_status=data.get('maritalStatus'),
            gender=data.get('gender'),
            max_change_filter_date=data.get('maxChangeFilterDate'),
            # Add other fields here if needed
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the IndividualDataModel object to a dictionary."""
        return {
             **self.__dict__,
            'addresses': [a.to_dict() for a in self.addresses],
            'phones': [p.to_dict() for p in self.phones],
            'emails': [e.to_dict() for e in self.emails],
        }

@dataclass(frozen=True)
class LegalEntityDataModel:
    """Represents data for a legal entity (Pessoa Jurídica). Immutable."""
    # --- Fields WITHOUT defaults first ---
    code: int
    cnpj: str
    is_inactive: bool
    name: str # Razão Social

    # --- Fields WITH defaults ---
    branch_insert_code: Optional[int] = None # API schema says required, but play safe
    fantasy_name: Optional[str] = None
    uf: Optional[str] = None
    number_state_registration: Optional[str] = None
    date_foundation: Optional[str] = None # Keep as string
    share_capital: Optional[float] = None
    addresses: List[Address] = field(default_factory=list)
    phones: List[Phone] = field(default_factory=list)
    emails: List[Email] = field(default_factory=list)
    insert_date: Optional[str] = None # Keep as string
    max_change_filter_date: Optional[str] = None
    is_customer: Optional[bool] = None
    is_supplier: Optional[bool] = None
    is_representative: Optional[bool] = None
    customer_status: Optional[str] = None
    # ... add other fields with defaults here ...


    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional['LegalEntityDataModel']:
        """Creates a LegalEntityDataModel from a dictionary (e.g., from API)."""
        if not isinstance(data, dict):
             logger.warning(f"Invalid data type for LegalEntityDataModel.from_dict: {type(data)}")
             return None

        # Essential fields
        code = data.get('code')
        cnpj = data.get('cnpj')
        name = data.get('name') # Razão Social
        is_inactive=data.get('isInactive', False) # Default to False if missing

        if code is None or cnpj is None or name is None:
             logger.warning(f"Missing essential data (code, cnpj, name) for LegalEntityDataModel: {data.get('code')}")
             return None

        # Process nested lists safely
        addresses_data = data.get('addresses', [])
        phones_data = data.get('phones', [])
        emails_data = data.get('emails', [])

        addresses = [Address.from_dict(addr) for addr in addresses_data if isinstance(addr, dict)]
        addresses = [addr for addr in addresses if addr is not None]
        phones = [Phone.from_dict(phone) for phone in phones_data if isinstance(phone, dict)]
        phones = [phone for phone in phones if phone is not None]
        emails = [Email.from_dict(email) for email in emails_data if isinstance(email, dict)]
        emails = [email for email in emails if email is not None]

        return cls(
            # Non-default args first
            code=code,
            cnpj=cnpj,
            is_inactive=is_inactive,
            name=name,
            # Default args next
            branch_insert_code=data.get('branchInsertCode'),
            fantasy_name=data.get('fantasyName'),
            uf=data.get('uf'),
            number_state_registration=data.get('numberStateRegistration'),
            date_foundation=data.get('dateFoundation'),
            share_capital=data.get('shareCapital'),
            addresses=addresses,
            phones=phones,
            emails=emails,
            insert_date=data.get('insertDate'),
            max_change_filter_date=data.get('maxChangeFilterDate'),
            is_customer=data.get('isCustomer'),
            is_supplier=data.get('isSupplier'),
            is_representative=data.get('isRepresentative'),
            customer_status=data.get('customerStatus'),
            # Add other fields here if needed
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the LegalEntityDataModel object to a dictionary."""
        return {
             **self.__dict__,
            'addresses': [a.to_dict() for a in self.addresses],
            'phones': [p.to_dict() for p in self.phones],
            'emails': [e.to_dict() for e in self.emails],
        }


@dataclass(frozen=True)
class PersonStatisticsResponseModel:
    """Represents customer statistics data from the ERP API. Immutable."""
    average_delay: Optional[int] = None
    maximum_delay: Optional[int] = None
    purchase_quantity: Optional[int] = None
    total_purchase_value: Optional[float] = None
    average_purchase_value: Optional[float] = None
    biggest_purchase_date: Optional[str] = None # Keep as string
    biggest_purchase_value: Optional[float] = None
    first_purchase_date: Optional[str] = None # Keep as string
    first_purchase_value: Optional[float] = None
    last_purchase_value: Optional[float] = None
    last_purchase_date: Optional[str] = None # Keep as string
    total_installments_paid: Optional[float] = None
    quantity_installments_paid: Optional[int] = None
    average_value_installments_paid: Optional[float] = None
    total_installments_delayed: Optional[float] = None
    quantity_installments_delayed: Optional[int] = None
    average_installment_delay: Optional[float] = None
    total_installments_open: Optional[float] = None
    quantity_installments_open: Optional[int] = None
    average_installments_open: Optional[float] = None
    last_invoice_paid_value: Optional[float] = None
    last_invoice_paid_date: Optional[str] = None # Keep as string

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional['PersonStatisticsResponseModel']:
        """Creates a PersonStatisticsResponseModel from a dictionary (e.g., from API)."""
        if not isinstance(data, dict):
            logger.warning(f"Invalid data type for PersonStatisticsResponseModel.from_dict: {type(data)}")
            return None
        # Directly map fields, relying on dataclass defaults for missing keys
        # Add type checks/conversions if API types are unreliable
        try:
            return cls(
                average_delay=data.get('averageDelay'),
                maximum_delay=data.get('maximumDelay'),
                purchase_quantity=data.get('purchaseQuantity'),
                total_purchase_value=data.get('totalPurchaseValue'),
                average_purchase_value=data.get('averagePurchaseValue'),
                biggest_purchase_date=data.get('biggestPurchaseDate'),
                biggest_purchase_value=data.get('biggestPurchaseValue'),
                first_purchase_date=data.get('firstPurchaseDate'),
                first_purchase_value=data.get('firstPurchaseValue'),
                last_purchase_value=data.get('lastPurchaseValue'),
                last_purchase_date=data.get('lastPurchaseDate'),
                total_installments_paid=data.get('totalInstallmentsPaid'),
                quantity_installments_paid=data.get('quantityInstallmentsPaid'),
                average_value_installments_paid=data.get('averageValueInstallmentsPaid'),
                total_installments_delayed=data.get('totalInstallmentsDelayed'),
                quantity_installments_delayed=data.get('quantityInstallmentsDelayed'),
                average_installment_delay=data.get('averageInstallmentDelay'),
                total_installments_open=data.get('totalInstallmentsOpen'),
                quantity_installments_open=data.get('quantityInstallmentsOpen'),
                average_installments_open=data.get('averageInstallmentsOpen'),
                last_invoice_paid_value=data.get('lastInvoicePaidValue'),
                last_invoice_paid_date=data.get('lastInvoicePaidDate')
            )
        except (TypeError, ValueError) as e:
            logger.error(f"Error creating PersonStatisticsResponseModel from dict: {e}. Data: {data}", exc_info=True)
            return None # Return None if data types are wrong

    def to_dict(self) -> Dict[str, Any]:
        """Converts the PersonStatisticsResponseModel object to a dictionary."""
        return self.__dict__