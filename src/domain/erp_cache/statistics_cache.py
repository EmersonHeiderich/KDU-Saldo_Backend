# src/domain/erp_cache/statistics_cache.py
# Define o modelo ORM para o cache de dados de Estatísticas de Pessoas do ERP.

from datetime import datetime, date, timezone
from typing import Optional

from sqlalchemy import (
    ForeignKey, Integer, Date, TIMESTAMP, NUMERIC, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.base import Base # Importa a Base declarativa

# Importa a classe base de controle, assumindo que ela está acessível
# Se person_cache.py não estiver no mesmo nível ou path, ajuste o import.
# Uma opção é mover CacheControlBase para um base_cache.py se for usada por mais módulos.
# Por enquanto, assumimos que está visível. Se der erro de import, precisaremos ajustar.
try:
    from .person_cache import CacheControlBase # Tenta importar do vizinho
except ImportError:
    # Alternativa se CacheControlBase for movida para um local mais central
    # from .base_cache import CacheControlBase
    # Ou, como fallback temporário, redefinir (não ideal):
    class CacheControlBase(Base):
        __abstract__ = True
        created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
        updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
        last_sync_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), index=True)


# --- Tabela de Estatísticas (One-to-One com Person) ---

class PersonStatistics(CacheControlBase):
    __tablename__ = 'erp_person_statistics'

    # Chave Primária e Estrangeira para garantir relação 1-para-1
    person_id: Mapped[int] = mapped_column(
        ForeignKey('erp_persons.id', ondelete='CASCADE'),
        primary_key=True,
        comment="Chave estrangeira referenciando a pessoa (erp_persons.id)."
    )

    # --- Campos de Estatísticas ---
    # Mapeados do endpoint GET /person-statistics
    average_delay: Mapped[Optional[int]] = mapped_column(Integer, comment="Atraso médio em dias (averageDelay).")
    maximum_delay: Mapped[Optional[int]] = mapped_column(Integer, comment="Atraso máximo em dias (maximumDelay).")
    purchase_quantity: Mapped[Optional[int]] = mapped_column(Integer, comment="Quantidade de compras (purchaseQuantity).")
    total_purchase_value: Mapped[Optional[float]] = mapped_column(NUMERIC(18, 2), comment="Valor total das compras (totalPurchaseValue).")
    average_purchase_value: Mapped[Optional[float]] = mapped_column(NUMERIC(18, 2), comment="Valor médio das compras (averagePurchaseValue).")
    biggest_purchase_date: Mapped[Optional[date]] = mapped_column(Date, comment="Data da maior compra (biggestPurchaseDate).")
    biggest_purchase_value: Mapped[Optional[float]] = mapped_column(NUMERIC(18, 2), comment="Valor da maior compra (biggestPurchaseValue).")
    first_purchase_date: Mapped[Optional[date]] = mapped_column(Date, comment="Data da primeira compra (firstPurchaseDate).")
    first_purchase_value: Mapped[Optional[float]] = mapped_column(NUMERIC(18, 2), comment="Valor da primeira compra (firstPurchaseValue).")
    last_purchase_value: Mapped[Optional[float]] = mapped_column(NUMERIC(18, 2), comment="Valor da última compra (lastPurchaseValue).")
    last_purchase_date: Mapped[Optional[date]] = mapped_column(Date, comment="Data da última compra (lastPurchaseDate).")
    total_installments_paid: Mapped[Optional[float]] = mapped_column(NUMERIC(18, 2), comment="Valor total das parcelas pagas (totalInstallmentsPaid).")
    quantity_installments_paid: Mapped[Optional[int]] = mapped_column(Integer, comment="Quantidade de parcelas pagas (quantityInstallmentsPaid).")
    average_value_installments_paid: Mapped[Optional[float]] = mapped_column(NUMERIC(18, 2), comment="Valor médio das parcelas pagas (averageValueInstallmentsPaid).")
    total_installments_delayed: Mapped[Optional[float]] = mapped_column(NUMERIC(18, 2), comment="Valor total das parcelas atrasadas (totalInstallmentsDelayed).")
    quantity_installments_delayed: Mapped[Optional[int]] = mapped_column(Integer, comment="Quantidade de parcelas atrasadas (quantityInstallmentsDelayed).")
    average_installment_delay: Mapped[Optional[float]] = mapped_column(NUMERIC(18, 2), comment="Atraso médio das parcelas (averageInstallmentDelay).") # Pode ser fracionado
    total_installments_open: Mapped[Optional[float]] = mapped_column(NUMERIC(18, 2), comment="Valor total das parcelas em aberto (totalInstallmentsOpen).")
    quantity_installments_open: Mapped[Optional[int]] = mapped_column(Integer, comment="Quantidade de parcelas em aberto (quantityInstallmentsOpen).")
    average_installments_open: Mapped[Optional[float]] = mapped_column(NUMERIC(18, 2), comment="Valor médio das parcelas em aberto (averageInstallmentsOpen).")
    last_invoice_paid_value: Mapped[Optional[float]] = mapped_column(NUMERIC(18, 2), comment="Valor da última fatura paga (lastInvoicePaidValue).")
    last_invoice_paid_date: Mapped[Optional[date]] = mapped_column(Date, comment="Data da última fatura paga (lastInvoicePaidDate).")

    # --- Relacionamento de volta para Person ---
    person: Mapped["Person"] = relationship(back_populates="statistics") # "Person" precisa ser importável ou definido como string

    def __repr__(self):
        """Representação textual do objeto PersonStatistics."""
        sync_time_str = self.last_sync_at.isoformat() if self.last_sync_at else 'Never'
        return f"<PersonStatistics(person_id={self.person_id}, last_sync_at='{sync_time_str}')>"