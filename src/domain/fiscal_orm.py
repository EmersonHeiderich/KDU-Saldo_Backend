# src/domain/fiscal_orm.py
# Define os modelos ORM para as tabelas Fiscais usando SQLAlchemy.

from datetime import datetime, date, time # Importar tipos necessários
from typing import Optional, List, Dict, Any # Importar tipos necessários
from sqlalchemy import (
    Integer, String, Text, Boolean, DateTime, Date, Time, Numeric, ForeignKey, func
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import TIMESTAMP, VARCHAR, NUMERIC # Tipos específicos PG

# Importar Base
from src.database.base import Base
from src.utils.logger import logger

# --- Tabela Principal: Nota Fiscal ---
class NotaFiscalOrm(Base):
    __tablename__ = 'nota_fiscal'

    # Chave Primária Composta (ou usar um ID único se preferir?)
    # Usar sequence parece mais robusto como PK se branchCode puder repetir.
    # Vamos usar um ID autoincremento por simplicidade e indexar a chave natural.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    branch_code: Mapped[int] = mapped_column(Integer, nullable=False, index=True) # FK para 'empresas' (futuro)
    invoice_sequence: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # --- Chave Natural (para busca/unicidade) ---
    # unique constraint para (branch_code, invoice_sequence) pode ser adicionado via Alembic
    # __table_args__ = (UniqueConstraint('branch_code', 'invoice_sequence', name='uq_nota_fiscal_branch_sequence'),)

    # --- Dados da Empresa/Pessoa ---
    branch_cnpj: Mapped[Optional[str]] = mapped_column(VARCHAR(14))
    person_code: Mapped[Optional[int]] = mapped_column(Integer, index=True) # FK para 'pessoas' (futuro)
    person_name: Mapped[Optional[str]] = mapped_column(Text)

    # --- Identificação da Nota ---
    invoice_code: Mapped[Optional[int]] = mapped_column(Integer, index=True) # Número da NF-e
    serial_code: Mapped[Optional[str]] = mapped_column(VARCHAR(5)) # Série
    invoice_status: Mapped[Optional[str]] = mapped_column(VARCHAR(20)) # Issued, Canceled, etc.
    access_key: Mapped[Optional[str]] = mapped_column(VARCHAR(44), unique=True, index=True) # Chave de Acesso (pode ser PK?)
    electronic_invoice_status: Mapped[Optional[str]] = mapped_column(VARCHAR(30)) # Authorized, Canceled, Denied
    receipt: Mapped[Optional[str]] = mapped_column(Text) # Protocolo/Recibo (pode ser longo?)
    receivement_date: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True)) # Data autorização
    disable_protocol: Mapped[Optional[str]] = mapped_column(Text)
    disable_date: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    # --- Dados da Transação/Operação ---
    transaction_branch_code: Mapped[Optional[int]] = mapped_column(Integer)
    transaction_date: Mapped[Optional[date]] = mapped_column(Date)
    transaction_code: Mapped[Optional[int]] = mapped_column(Integer)
    inclusion_component_code: Mapped[Optional[str]] = mapped_column(VARCHAR(30))
    user_code: Mapped[Optional[int]] = mapped_column(Integer) # FK para 'usuarios' (futuro)
    origin: Mapped[Optional[str]] = mapped_column(VARCHAR(20)) # Own, ThirdParty
    document_type: Mapped[Optional[int]] = mapped_column(Integer) # 55, 65
    operation_type: Mapped[Optional[str]] = mapped_column(VARCHAR(10)) # Input, Output
    operation_code: Mapped[Optional[int]] = mapped_column(Integer) # FK para 'operacoes' (futuro)
    operation_name: Mapped[Optional[str]] = mapped_column(Text)

    # --- Datas e Horas ---
    invoice_date: Mapped[Optional[date]] = mapped_column(Date) # Data de movimento
    issue_date: Mapped[Optional[date]] = mapped_column(Date, index=True) # Data de emissão
    release_date: Mapped[Optional[date]] = mapped_column(Date) # Data de lançamento
    exit_time: Mapped[Optional[time]] = mapped_column(Time) # Hora de saída
    lastchange_date: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), index=True) # Ultima alteração ERP

    # --- Valores Totais ---
    # Usar NUMERIC para valores monetários
    payment_condition_code: Mapped[Optional[int]] = mapped_column(Integer) # FK para 'cond_pagamento' (futuro)
    payment_condition_name: Mapped[Optional[str]] = mapped_column(Text)
    discount_percentage: Mapped[Optional[float]] = mapped_column(NUMERIC(10, 4)) # Ajustar precisão/escala
    quantity: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 4)) # Ajustar precisão/escala
    product_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2)) # Ajustar precisão/escala
    additional_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    shipping_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    insurance_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    ipi_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    base_icms_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    icms_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    icms_subst_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    total_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))

    # --- Dados de Frete ---
    shipping_company_code: Mapped[Optional[int]] = mapped_column(Integer) # FK para 'pessoas' (futuro)
    shipping_company_name: Mapped[Optional[str]] = mapped_column(Text)
    freight_type: Mapped[Optional[str]] = mapped_column(VARCHAR(50)) # CIF, FOB, etc.
    freight_type_redispatch: Mapped[Optional[str]] = mapped_column(VARCHAR(50))
    freight_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    package_number: Mapped[Optional[int]] = mapped_column(Integer)
    gross_weight: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 3)) # Ajustar precisão/escala
    net_weight: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 3))
    species: Mapped[Optional[str]] = mapped_column(VARCHAR(50))

    # --- Outros ---
    terminal_code: Mapped[Optional[int]] = mapped_column(Integer)
    observation_nfe: Mapped[Optional[str]] = mapped_column(Text) # Campo único de obs NFE

    # Timestamps locais
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    # --- Relacionamentos (um-para-muitos) ---
    items: Mapped[List["NotaFiscalItemOrm"]] = relationship(back_populates="nota_fiscal", cascade="all, delete-orphan", lazy="select")
    payments: Mapped[List["NotaFiscalPagamentoOrm"]] = relationship(back_populates="nota_fiscal", cascade="all, delete-orphan", lazy="select")
    sales_orders: Mapped[List["NotaFiscalPedidoVendaOrm"]] = relationship(back_populates="nota_fiscal", cascade="all, delete-orphan", lazy="select")
    observations: Mapped[List["NotaFiscalObservacaoOrm"]] = relationship(back_populates="nota_fiscal", cascade="all, delete-orphan", lazy="select")

    def __repr__(self):
        return f"<NotaFiscalOrm(id={self.id}, branch={self.branch_code}, seq={self.invoice_sequence}, num={self.invoice_code}, key=...{str(self.access_key)[-6:] if self.access_key else 'N/A'})>"


# --- Tabela de Itens da Nota Fiscal ---
class NotaFiscalItemOrm(Base):
    __tablename__ = 'nota_fiscal_item'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nota_fiscal_id: Mapped[int] = mapped_column(ForeignKey('nota_fiscal.id', ondelete='CASCADE'), index=True)

    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(Text) # Código fiscal do produto
    name: Mapped[Optional[str]] = mapped_column(Text)
    ncm: Mapped[Optional[str]] = mapped_column(VARCHAR(12))
    cfop: Mapped[Optional[int]] = mapped_column(Integer)
    measure_unit: Mapped[Optional[str]] = mapped_column(VARCHAR(6))
    quantity: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 4))
    gross_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    discount_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    net_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    unit_gross_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 6)) # Mais casas decimais para unitário
    unit_discount_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 6))
    unit_net_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 6))
    additional_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    freight_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    insurance_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    additional_item_information: Mapped[Optional[str]] = mapped_column(Text)

    # --- Relacionamento (muitos-para-um) ---
    nota_fiscal: Mapped["NotaFiscalOrm"] = relationship(back_populates="items")

    # --- Relacionamento (um-para-muitos para produtos do item) ---
    item_products: Mapped[List["NotaFiscalItemProdutoOrm"]] = relationship(back_populates="item", cascade="all, delete-orphan", lazy="select")

    def __repr__(self):
        return f"<NotaFiscalItemOrm(id={self.id}, nf_id={self.nota_fiscal_id}, seq={self.sequence})>"


# --- Tabela de Produtos do Item da Nota Fiscal ---
class NotaFiscalItemProdutoOrm(Base):
    __tablename__ = 'nota_fiscal_item_produto'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey('nota_fiscal_item.id', ondelete='CASCADE'), index=True)

    product_code: Mapped[Optional[int]] = mapped_column(Integer) # FK para 'produtos' (futuro)
    product_name: Mapped[Optional[str]] = mapped_column(Text)
    dealer_code: Mapped[Optional[int]] = mapped_column(Integer)
    quantity: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 4))
    unit_gross_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 6))
    unit_discount_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 6))
    unit_net_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 6))
    gross_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    discount_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    net_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))

    # --- Relacionamento (muitos-para-um) ---
    item: Mapped["NotaFiscalItemOrm"] = relationship(back_populates="item_products")

    def __repr__(self):
        return f"<NotaFiscalItemProdutoOrm(id={self.id}, item_id={self.item_id}, product_code={self.product_code})>"


# --- Tabela de Pagamentos da Nota Fiscal ---
class NotaFiscalPagamentoOrm(Base):
    __tablename__ = 'nota_fiscal_pagamento'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nota_fiscal_id: Mapped[int] = mapped_column(ForeignKey('nota_fiscal.id', ondelete='CASCADE'), index=True)

    document_number: Mapped[Optional[int]] = mapped_column(Integer)
    expiration_date: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    payment_value: Mapped[Optional[float]] = mapped_column(NUMERIC(15, 2))
    document_type_code: Mapped[Optional[int]] = mapped_column(Integer)
    document_type: Mapped[Optional[str]] = mapped_column(VARCHAR(50))
    installment: Mapped[Optional[int]] = mapped_column(Integer)
    bearer_code: Mapped[Optional[int]] = mapped_column(Integer)
    bearer_name: Mapped[Optional[str]] = mapped_column(Text)

    # --- Relacionamento (muitos-para-um) ---
    nota_fiscal: Mapped["NotaFiscalOrm"] = relationship(back_populates="payments")

    def __repr__(self):
        return f"<NotaFiscalPagamentoOrm(id={self.id}, nf_id={self.nota_fiscal_id}, installment={self.installment})>"


# --- Tabela de Pedidos de Venda da Nota Fiscal ---
class NotaFiscalPedidoVendaOrm(Base):
    __tablename__ = 'nota_fiscal_pedido_venda'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nota_fiscal_id: Mapped[int] = mapped_column(ForeignKey('nota_fiscal.id', ondelete='CASCADE'), index=True)

    branch_code: Mapped[Optional[int]] = mapped_column(Integer)
    order_code: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    customer_order_code: Mapped[Optional[str]] = mapped_column(Text)

    # --- Relacionamento (muitos-para-um) ---
    nota_fiscal: Mapped["NotaFiscalOrm"] = relationship(back_populates="sales_orders")

    def __repr__(self):
        return f"<NotaFiscalPedidoVendaOrm(id={self.id}, nf_id={self.nota_fiscal_id}, order_code={self.order_code})>"


# --- Tabela de Observações da Nota Fiscal ---
class NotaFiscalObservacaoOrm(Base):
    __tablename__ = 'nota_fiscal_observacao'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nota_fiscal_id: Mapped[int] = mapped_column(ForeignKey('nota_fiscal.id', ondelete='CASCADE'), index=True)

    observation: Mapped[Optional[str]] = mapped_column(Text)
    sequence: Mapped[Optional[int]] = mapped_column(Integer)

    # --- Relacionamento (muitos-para-um) ---
    nota_fiscal: Mapped["NotaFiscalOrm"] = relationship(back_populates="observations")

    def __repr__(self):
        return f"<NotaFiscalObservacaoOrm(id={self.id}, nf_id={self.nota_fiscal_id}, seq={self.sequence})>"