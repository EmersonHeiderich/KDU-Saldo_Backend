from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from src.utils.logger import logger

@dataclass(frozen=True)
class DocumentChangeModel:
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    in_check: Optional[bool] = None

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional['DocumentChangeModel']:
        if not data: return None
        return cls(
            start_date=data.get('startDate'),
            end_date=data.get('endDate'),
            in_check=data.get('inCheck')
        )

    def to_dict(self) -> Dict[str, Any]:
        d = {}
        if self.start_date is not None: d['startDate'] = self.start_date
        if self.end_date is not None: d['endDate'] = self.end_date
        if self.in_check is not None: d['inCheck'] = self.in_check
        return d

@dataclass(frozen=True)
class DocumentFilterModel:
    change: Optional[DocumentChangeModel] = None
    branch_code_list: Optional[List[int]] = field(default_factory=list)
    customer_code_list: Optional[List[int]] = field(default_factory=list)
    customer_cpf_cnpj_list: Optional[List[str]] = field(default_factory=list)
    start_expired_date: Optional[str] = None
    end_expired_date: Optional[str] = None
    start_payment_date: Optional[str] = None
    end_payment_date: Optional[str] = None
    start_issue_date: Optional[str] = None
    end_issue_date: Optional[str] = None
    start_credit_date: Optional[str] = None
    end_credit_date: Optional[str] = None
    status_list: Optional[List[int]] = field(default_factory=list)
    document_type_list: Optional[List[int]] = field(default_factory=list)
    billing_type_list: Optional[List[int]] = field(default_factory=list)
    discharge_type_list: Optional[List[int]] = field(default_factory=list)
    charge_type_list: Optional[List[int]] = field(default_factory=list)
    has_open_invoices: Optional[bool] = None
    receivable_code_list: Optional[List[float]] = field(default_factory=list)
    our_number_list: Optional[List[float]] = field(default_factory=list)
    commissioned_code: Optional[int] = None
    commissioned_cpf_cnpj: Optional[str] = None
    closing_code_commission: Optional[int] = None
    closing_company_commission: Optional[int] = None
    closing_date_commission: Optional[str] = None
    closing_commissioned_code: Optional[int] = None
    closing_commissioned_cpf_cnpj: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {}
        if self.change: d['change'] = self.change.to_dict()
        if self.branch_code_list: d['branchCodeList'] = self.branch_code_list
        if self.customer_code_list: d['customerCodeList'] = self.customer_code_list
        if self.customer_cpf_cnpj_list: d['customerCpfCnpjList'] = self.customer_cpf_cnpj_list
        if self.start_expired_date: d['startExpiredDate'] = self.start_expired_date
        if self.end_expired_date: d['endExpiredDate'] = self.end_expired_date
        if self.start_payment_date: d['startPaymentDate'] = self.start_payment_date
        if self.end_payment_date: d['endPaymentDate'] = self.end_payment_date
        if self.start_issue_date: d['startIssueDate'] = self.start_issue_date
        if self.end_issue_date: d['endIssueDate'] = self.end_issue_date
        if self.start_credit_date: d['startCreditDate'] = self.start_credit_date
        if self.end_credit_date: d['endCreditDate'] = self.end_credit_date
        if self.status_list: d['statusList'] = self.status_list
        if self.document_type_list: d['documentTypeList'] = self.document_type_list
        if self.billing_type_list: d['billingTypeList'] = self.billing_type_list
        if self.discharge_type_list: d['dischargeTypeList'] = self.discharge_type_list
        if self.charge_type_list: d['chargeTypeList'] = self.charge_type_list
        if self.has_open_invoices is not None: d['hasOpenInvoices'] = self.has_open_invoices
        if self.receivable_code_list: d['receivableCodeList'] = self.receivable_code_list
        if self.our_number_list: d['ourNumberList'] = self.our_number_list
        if self.commissioned_code: d['commissionedCode'] = self.commissioned_code
        if self.commissioned_cpf_cnpj: d['commissionedCpfCnpj'] = self.commissioned_cpf_cnpj
        if self.closing_code_commission: d['closingCodeCommission'] = self.closing_code_commission
        if self.closing_company_commission: d['closingCompanyCommission'] = self.closing_company_commission
        if self.closing_date_commission: d['closingDateCommission'] = self.closing_date_commission
        if self.closing_commissioned_code: d['closingCommissionedCode'] = self.closing_commissioned_code
        if self.closing_commissioned_cpf_cnpj: d['closingCommissionedCpfCnpj'] = self.closing_commissioned_cpf_cnpj
        return d


@dataclass(frozen=True)
class DocumentRequestModel:
    filter: Optional[DocumentFilterModel] = None
    expand: Optional[str] = None
    order: Optional[str] = None
    page: int = 1
    page_size: int = 100

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "page": self.page,
            "pageSize": self.page_size,
        }
        if self.filter: d['filter'] = self.filter.to_dict()
        if self.expand: d['expand'] = self.expand
        if self.order: d['order'] = self.order
        return d

@dataclass(frozen=True)
class CalculatedValuesModel:
    days_late: Optional[int] = None
    increase_value: Optional[float] = None
    interest_value: Optional[float] = None
    fine_value: Optional[float] = None
    discount_value: Optional[float] = None
    corrected_value: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional['CalculatedValuesModel']:
        if not data: return None
        return cls(
            days_late=data.get('daysLate'),
            increase_value=data.get('increaseValue'),
            interest_value=data.get('interestValue'),
            fine_value=data.get('fineValue'),
            discount_value=data.get('discountValue'),
            corrected_value=data.get('correctedValue')
        )

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

@dataclass(frozen=True)
class InvoiceDataModel:
    invoice_code: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional['InvoiceDataModel']:
        if not data: return None
        return cls(invoice_code=data.get('invoiceCode'))

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

@dataclass(frozen=True)
class DocumentModel:
    branch_code: Optional[int] = None
    customer_code: Optional[int] = None
    customer_cpf_cnpj: Optional[str] = None
    receivable_code: Optional[int] = None
    installment_code: Optional[int] = None
    max_change_filter_date: Optional[str] = None
    expired_date: Optional[str] = None
    payment_date: Optional[str] = None
    issue_date: Optional[str] = None
    settlement_branch_code: Optional[int] = None
    settlement_date: Optional[str] = None
    settlement_sequence: Optional[int] = None
    status: Optional[int] = None
    document_type: Optional[int] = None
    billing_type: Optional[int] = None
    discharge_type: Optional[int] = None
    charge_type: Optional[int] = None
    origin_installment: Optional[int] = None
    bearer_code: Optional[int] = None
    bearer_name: Optional[str] = None
    installment_value: Optional[float] = None
    paid_value: Optional[float] = None
    net_value: Optional[float] = None
    discount_value: Optional[float] = None
    rebate_value: Optional[float] = None
    interest_value: Optional[float] = None
    assessment_value: Optional[float] = None
    bar_code: Optional[str] = None
    digitable_line: Optional[str] = None
    our_number: Optional[int] = None
    dac_our_number: Optional[str] = None
    qr_code_pix: Optional[str] = None
    discharge_user: Optional[int] = None
    registration_user: Optional[int] = None
    calculated_values: Optional[CalculatedValuesModel] = None
    check: Optional[Dict[str, Any]] = None
    invoice: Optional[List[InvoiceDataModel]] = field(default_factory=list)
    commissions: Optional[List[Dict[str, Any]]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional['DocumentModel']:
        if not data: return None

        calculated_values = CalculatedValuesModel.from_dict(data.get('calculatedValues'))
        invoices_raw = data.get('invoice', [])
        invoices = [InvoiceDataModel.from_dict(inv) for inv in invoices_raw if inv] if isinstance(invoices_raw, list) else []
        invoices = [inv for inv in invoices if inv is not None]

        return cls(
            branch_code=data.get('branchCode'),
            customer_code=data.get('customerCode'),
            customer_cpf_cnpj=data.get('customerCpfCnpj'),
            receivable_code=data.get('receivableCode'),
            installment_code=data.get('installmentCode'),
            max_change_filter_date=data.get('maxChangeFilterDate'),
            expired_date=data.get('expiredDate'),
            payment_date=data.get('paymentDate'),
            issue_date=data.get('issueDate'),
            settlement_branch_code=data.get('settlementBranchCode'),
            settlement_date=data.get('settlementDate'),
            settlement_sequence=data.get('settlementSequence'),
            status=data.get('status'),
            document_type=data.get('documentType'),
            billing_type=data.get('billingType'),
            discharge_type=data.get('dischargeType'),
            charge_type=data.get('chargeType'),
            origin_installment=data.get('originInstallment'),
            bearer_code=data.get('bearerCode'),
            bearer_name=data.get('bearerName'),
            installment_value=data.get('installmentValue'),
            paid_value=data.get('paidValue'),
            net_value=data.get('netValue'),
            discount_value=data.get('discountValue'),
            rebate_value=data.get('rebateValue'),
            interest_value=data.get('interestValue'),
            assessment_value=data.get('assessmentValue'),
            bar_code=data.get('barCode'),
            digitable_line=data.get('digitableLine'),
            our_number=data.get('ourNumber'),
            dac_our_number=data.get('dacOurNumber'),
            qr_code_pix=data.get('qrCodePix'),
            discharge_user=data.get('dischargeUser'),
            registration_user=data.get('registrationUser'),
            calculated_values=calculated_values,
            check=data.get('check'),
            invoice=invoices,
            commissions=data.get('commissions')
        )

    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        if self.calculated_values: d['calculated_values'] = self.calculated_values.to_dict()
        if self.invoice: d['invoice'] = [inv.to_dict() for inv in self.invoice]
        return d


@dataclass(frozen=True)
class DocumentResponseModel:
    count: int = 0
    total_pages: int = 0
    has_next: bool = False
    total_items: int = 0
    items: List[DocumentModel] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional['DocumentResponseModel']:
        if not data: return None
        items_raw = data.get('items', [])
        items = [DocumentModel.from_dict(item) for item in items_raw if item] if isinstance(items_raw, list) else []
        items = [item for item in items if item is not None]

        return cls(
            count=data.get('count', 0),
            total_pages=data.get('totalPages', 0),
            has_next=data.get('hasNext', False),
            total_items=data.get('totalItems', 0),
            items=items
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "totalPages": self.total_pages,
            "hasNext": self.has_next,
            "totalItems": self.total_items,
            "items": [item.to_dict() for item in self.items]
        }

@dataclass(frozen=True)
class BankSlipRequestModel:
    branch_code: int
    customer_code: int
    receivable_code: int
    installment_number: int
    customer_cpf_cnpj: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "branchCode": self.branch_code,
            "customerCode": self.customer_code,
            "receivableCode": self.receivable_code,
            "installmentNumber": self.installment_number,
        }
        return d

@dataclass(frozen=True)
class AccountsReceivableTomasResponseModel:
    content: Optional[str] = None
    uniface_response_status: Optional[str] = None
    uniface_message: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional['AccountsReceivableTomasResponseModel']:
        if not data: return None
        return cls(
            content=data.get('content'),
            uniface_response_status=data.get('unifaceResponseStatus'),
            uniface_message=data.get('unifaceMessage')
        )

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

@dataclass(frozen=True)
class FormattedReceivableListItem:
    customer_code: Optional[int] = None
    customer_cpf_cnpj: Optional[str] = None
    customer_name: Optional[str] = None
    invoice_number: Optional[int] = None
    document_number: Optional[int] = None
    installment_number: Optional[int] = None
    bearer_name: Optional[str] = None
    issue_date: Optional[str] = None
    expired_date: Optional[str] = None
    days_late: Optional[int] = None
    payment_date: Optional[str] = None
    value_original: Optional[float] = None
    value_increase: Optional[float] = None
    value_rebate: Optional[float] = None
    value_paid: Optional[float] = None
    value_corrected: Optional[float] = None
    status: Optional[int] = None
    document_type: Optional[int] = None
    billing_type: Optional[int] = None
    discharge_type: Optional[int] = None
    charge_type: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__