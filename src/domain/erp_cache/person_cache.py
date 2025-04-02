# src/domain/erp_cache/person_cache.py
# Define os modelos ORM para o cache de dados de Pessoas (PF/PJ) e seus dados relacionados do ERP.

from datetime import datetime, date, timezone
from typing import List, Optional

from sqlalchemy import (
    ForeignKey, String, Text, Integer, Boolean, Date,
    TIMESTAMP, NUMERIC, UniqueConstraint, Index, CHAR, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.base import Base # Importa a Base declarativa

# --- Classe Base Auxiliar para Colunas de Controle ---

class CacheControlBase(Base):
    """Classe base abstrata para colunas comuns de controle de cache."""
    __abstract__ = True # Não cria uma tabela para esta classe

    # Timestamps gerenciados pelo nosso aplicativo/banco de dados
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False,
        comment="Timestamp da criação do registro no cache local."
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
        comment="Timestamp da última atualização do registro no cache local."
    )
    # Timestamp da última operação de sincronização bem-sucedida para este registro
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), index=True,
        comment="Timestamp da última sincronização bem-sucedida com o ERP para este registro."
    )

# --- Tabela Principal de Pessoas ---

class Person(CacheControlBase):
    __tablename__ = 'erp_persons'
    __table_args__ = (
        Index('ix_erp_persons_erp_code_type', 'erp_code', 'person_type'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    erp_code: Mapped[int] = mapped_column(
        Integer, unique=True, index=True, nullable=False,
        comment="Código da pessoa no ERP (ex: individuals.items[0].code)."
    )
    person_type: Mapped[str] = mapped_column(
        CHAR(2), nullable=False, index=True,
        comment="Tipo de Pessoa: 'PF' (Física) ou 'PJ' (Jurídica)."
    )
    name: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Nome (PF) ou Razão Social (PJ) da pessoa no ERP."
    )
    is_inactive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True,
        comment="Indica se a pessoa está inativa no ERP (campo 'isInactive')."
    )

    # --- Flags e Status Comuns ---
    is_customer: Mapped[Optional[bool]] = mapped_column(Boolean, comment="Flag 'isCustomer' do ERP.")
    is_supplier: Mapped[Optional[bool]] = mapped_column(Boolean, comment="Flag 'isSupplier' do ERP.")
    is_representative: Mapped[Optional[bool]] = mapped_column(Boolean, comment="Flag 'isRepresentative' do ERP.")
    is_employee: Mapped[Optional[bool]] = mapped_column(Boolean, comment="Flag 'isEmployee' do ERP (principalmente PF).")
    # Outras flags comuns podem ser adicionadas aqui (isPurchasingGuide, isShippingCompany)

    customer_status: Mapped[Optional[str]] = mapped_column(String(50), comment="Status do cliente no ERP (campo 'customerStatus').")
    employee_status: Mapped[Optional[str]] = mapped_column(String(50), comment="Status do funcionário no ERP (campo 'employeeStatus', apenas PF).")

    # --- Timestamps do ERP ---
    erp_insert_date: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        comment="Data de inserção original no ERP (campo 'insertDate')."
    )
    erp_change_date: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), index=True,
        comment="Data da última alteração no ERP (campo 'maxChangeFilterDate'). Usado para sync incremental."
    )

    # --- Relacionamentos ---
    individual_detail: Mapped[Optional["IndividualDetail"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="joined", uselist=False)
    legal_entity_detail: Mapped[Optional["LegalEntityDetail"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="joined", uselist=False)
    addresses: Mapped[List["Address"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="select")
    phones: Mapped[List["Phone"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="select")
    emails: Mapped[List["Email"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="select")
    observations: Mapped[List["ErpPersonObservation"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="select")
    additional_fields: Mapped[List["AdditionalField"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="select")
    classifications: Mapped[List["Classification"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="select")
    references: Mapped[List["Reference"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="select")
    related_persons: Mapped[List["RelatedPerson"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="select")
    representatives: Mapped[List["Representative"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="select")
    preferences: Mapped[Optional["Preference"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="joined", uselist=False)
    familiars: Mapped[List["Familiar"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="select") # Apenas PF
    partners: Mapped[List["Partner"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="select") # Apenas PJ
    contacts: Mapped[List["Contact"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="select") # Apenas PJ
    social_networks: Mapped[List["SocialNetwork"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="select") # Apenas PJ
    payment_methods: Mapped[List["PaymentMethod"]] = relationship(back_populates="person", cascade="all, delete-orphan", lazy="select") # Apenas PJ
    # O relacionamento 'statistics' é definido na classe PersonStatistics e mapeado aqui por back_populates
    statistics: Mapped[Optional["PersonStatistics"]] = relationship(back_populates="person") # Lazy loading default ou 'joined' se definido lá

    def __repr__(self):
        """Representação textual do objeto Person."""
        inactive_str = " (Inactive)" if self.is_inactive else ""
        return (
            f"<Person(id={self.id}, erp_code={self.erp_code}, "
            f"type='{self.person_type}', name='{self.name[:20]}...'{inactive_str})>"
        )

# --- Tabelas de Detalhes Específicos (One-to-One com Person) ---

class IndividualDetail(CacheControlBase):
    __tablename__ = 'erp_individual_details'

    # Chave Primária e Estrangeira
    person_id: Mapped[int] = mapped_column(
        ForeignKey('erp_persons.id', ondelete='CASCADE'), primary_key=True
    )
    # CPF deve ser único
    cpf: Mapped[str] = mapped_column(String(11), unique=True, index=True, nullable=False, comment="CPF do indivíduo (campo 'cpf').")
    rg: Mapped[Optional[str]] = mapped_column(String(30), comment="RG do indivíduo (campo 'rg').")
    rg_federal_agency: Mapped[Optional[str]] = mapped_column(String(20), comment="Órgão emissor do RG (campo 'rgFederalAgency').")
    birth_date: Mapped[Optional[date]] = mapped_column(Date, comment="Data de nascimento (campo 'birthDate').")
    marital_status: Mapped[Optional[str]] = mapped_column(String(20), comment="Estado civil (campo 'maritalStatus').")
    gender: Mapped[Optional[str]] = mapped_column(String(20), comment="Gênero (campo 'gender').")
    mother_name: Mapped[Optional[str]] = mapped_column(Text, comment="Nome da mãe (campo 'motherName').")
    father_name: Mapped[Optional[str]] = mapped_column(Text, comment="Nome do pai (campo 'fatherName').")
    nationality: Mapped[Optional[str]] = mapped_column(String(50), comment="Nacionalidade (campo 'nationality').")
    # Outros campos específicos de PF (ctps, monthlyIncome, occupation, hireDate etc.) podem ser adicionados aqui.

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="individual_detail")

    def __repr__(self):
        return f"<IndividualDetail(person_id={self.person_id}, cpf='{self.cpf}')>"

class LegalEntityDetail(CacheControlBase):
    __tablename__ = 'erp_legal_entity_details'

    # Chave Primária e Estrangeira
    person_id: Mapped[int] = mapped_column(
        ForeignKey('erp_persons.id', ondelete='CASCADE'), primary_key=True
    )
    # CNPJ deve ser único
    cnpj: Mapped[str] = mapped_column(String(14), unique=True, index=True, nullable=False, comment="CNPJ da entidade (campo 'cnpj').")
    fantasy_name: Mapped[Optional[str]] = mapped_column(Text, comment="Nome Fantasia (campo 'fantasyName').")
    state_registration: Mapped[Optional[str]] = mapped_column(String(30), comment="Inscrição Estadual (campo 'numberStateRegistration').")
    state_registration_uf: Mapped[Optional[str]] = mapped_column(String(2), comment="UF da Inscrição Estadual (campo 'uf').")
    foundation_date: Mapped[Optional[date]] = mapped_column(Date, comment="Data de fundação (campo 'dateFoundation').")
    municipal_registration: Mapped[Optional[str]] = mapped_column(String(30), comment="Inscrição Municipal (campo 'registrationMunicipal').")
    share_capital: Mapped[Optional[float]] = mapped_column(NUMERIC(18, 2), comment="Capital Social (campo 'shareCapital').")
    # Outros campos específicos de PJ (codeActivity, numberEmployees, typeTaxRegime etc.) podem ser adicionados aqui.

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="legal_entity_detail")

    def __repr__(self):
        return f"<LegalEntityDetail(person_id={self.person_id}, cnpj='{self.cnpj}')>"

# --- Tabelas de Dados Relacionados (One-to-Many com Person) ---

class Address(CacheControlBase):
    __tablename__ = 'erp_person_addresses'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('erp_persons.id', ondelete='CASCADE'), index=True, nullable=False)
    # Código da sequência do endereço no ERP (campo 'sequenceCode')
    erp_sequence_code: Mapped[Optional[int]] = mapped_column(Integer, comment="Código de sequência do endereço no ERP.")

    # Campos do endereço (mapeados de 'addresses')
    address_type: Mapped[Optional[str]] = mapped_column(String(50), comment="Tipo de endereço (campo 'addressType', ex: Commercial).")
    public_place: Mapped[Optional[str]] = mapped_column(Text, comment="Logradouro (campo 'publicPlace').")
    address_detail: Mapped[Optional[str]] = mapped_column(Text, comment="Endereço (complemento do logradouro, campo 'address').")
    number: Mapped[Optional[str]] = mapped_column(String(20), comment="Número (campo 'addressNumber').")
    complement: Mapped[Optional[str]] = mapped_column(Text, comment="Complemento (campo 'complement').")
    neighborhood: Mapped[Optional[str]] = mapped_column(String(100), comment="Bairro (campo 'neighborhood').")
    city_name: Mapped[Optional[str]] = mapped_column(String(100), comment="Nome da cidade (campo 'cityName').")
    state_abbreviation: Mapped[Optional[str]] = mapped_column(String(2), comment="Sigla do estado (campo 'stateAbbreviation').")
    zip_code: Mapped[Optional[str]] = mapped_column(String(10), index=True, comment="CEP (campo 'cep').")
    country_name: Mapped[Optional[str]] = mapped_column(String(50), comment="Nome do país (campo 'countryName').")
    reference: Mapped[Optional[str]] = mapped_column(Text, comment="Ponto de referência (campo 'reference').")
    # O campo 'isDefault' do ERP pode não existir, inferimos ou definimos manualmente se necessário.
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Indica se este é o endereço padrão (lógica de sync pode definir).")

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="addresses")

    __table_args__ = (UniqueConstraint('person_id', 'erp_sequence_code', name='uq_person_address_sequence'),)

class Phone(CacheControlBase):
    __tablename__ = 'erp_person_phones'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('erp_persons.id', ondelete='CASCADE'), index=True, nullable=False)
    # Código da sequência do telefone no ERP (campo 'Sequence')
    erp_sequence_code: Mapped[Optional[int]] = mapped_column(Integer, comment="Código de sequência do telefone no ERP.")

    # Campos do telefone (mapeados de 'phones')
    type_name: Mapped[Optional[str]] = mapped_column(String(50), comment="Tipo do telefone (campo 'typeName').")
    number: Mapped[Optional[str]] = mapped_column(String(30), comment="Número do telefone (campo 'number').")
    extension: Mapped[Optional[str]] = mapped_column(String(10), comment="Ramal (campo 'branchLine').")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Indica se é o telefone padrão (campo 'isDefault').")

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="phones")

    __table_args__ = (UniqueConstraint('person_id', 'erp_sequence_code', name='uq_person_phone_sequence'),)

class Email(CacheControlBase):
    __tablename__ = 'erp_person_emails'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('erp_persons.id', ondelete='CASCADE'), index=True, nullable=False)
    # Código da sequência do email no ERP (campo 'sequence')
    erp_sequence_code: Mapped[Optional[int]] = mapped_column(Integer, comment="Código de sequência do email no ERP.")

    # Campos do email (mapeados de 'emails')
    type_name: Mapped[Optional[str]] = mapped_column(String(50), comment="Tipo do email (campo 'typeName').")
    email_address: Mapped[Optional[str]] = mapped_column(String(255), index=True, comment="Endereço de email (campo 'email').")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Indica se é o email padrão (campo 'isDefault').")

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="emails")

    __table_args__ = (UniqueConstraint('person_id', 'erp_sequence_code', name='uq_person_email_sequence'),)

class ErpPersonObservation(CacheControlBase):
    __tablename__ = 'erp_person_observations'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('erp_persons.id', ondelete='CASCADE'), index=True, nullable=False)
    # Código da sequência da observação no ERP (campo 'sequence')
    erp_sequence_code: Mapped[Optional[int]] = mapped_column(Integer, comment="Código de sequência da observação no ERP.")

    # Campos da observação (mapeados de 'observations' e 'customerObservations')
    observation_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Tipo da Observação: 'General' (de 'observations') ou 'Customer' (de 'customerObservations')."
    )
    observation_text: Mapped[Optional[str]] = mapped_column(Text, comment="Texto da observação (campo 'observation').")
    is_maintenance: Mapped[Optional[bool]] = mapped_column(Boolean, comment="Flag 'isMaintenance' do ERP.")
    erp_last_change_date: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        comment="Data da última alteração no ERP (apenas para tipo 'Customer', campo 'LastChangeDate')."
    )

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="observations")

    __table_args__ = (UniqueConstraint('person_id', 'observation_type', 'erp_sequence_code', name='uq_person_observation_sequence'),)

class AdditionalField(CacheControlBase):
    __tablename__ = 'erp_person_additional_fields'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('erp_persons.id', ondelete='CASCADE'), index=True, nullable=False)

    # Campos do campo adicional (mapeados de 'additionalFields')
    erp_field_code: Mapped[int] = mapped_column(Integer, nullable=False, comment="Código do campo adicional no ERP (campo 'code').")
    erp_field_name: Mapped[Optional[str]] = mapped_column(String(100), comment="Nome do campo adicional no ERP (campo 'name').")
    erp_field_type: Mapped[Optional[str]] = mapped_column(String(20), comment="Tipo do campo adicional no ERP (campo 'type', ex: String).")
    # Armazenar valor como TEXTO para flexibilidade
    value: Mapped[Optional[str]] = mapped_column(Text, comment="Valor do campo adicional (campo 'value').")

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="additional_fields")

    __table_args__ = (UniqueConstraint('person_id', 'erp_field_code', name='uq_person_additional_field'),)

class Classification(CacheControlBase):
    __tablename__ = 'erp_person_classifications'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('erp_persons.id', ondelete='CASCADE'), index=True, nullable=False)

    # Campos da classificação (mapeados de 'classifications')
    type_code: Mapped[int] = mapped_column(Integer, nullable=False, comment="Código do tipo de classificação no ERP (campo 'typeCode').")
    type_name: Mapped[Optional[str]] = mapped_column(String(100), comment="Nome do tipo de classificação (campo 'typeName').")
    code: Mapped[str] = mapped_column(String(50), nullable=False, comment="Código da classificação dentro do tipo (campo 'code').")
    name: Mapped[Optional[str]] = mapped_column(String(100), comment="Nome da classificação (campo 'name').")

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="classifications")

    __table_args__ = (UniqueConstraint('person_id', 'type_code', 'code', name='uq_person_classification'),)

class Reference(CacheControlBase):
    __tablename__ = 'erp_person_references'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('erp_persons.id', ondelete='CASCADE'), index=True, nullable=False)
    erp_sequence_code: Mapped[Optional[int]] = mapped_column(Integer, comment="Código de sequência da referência no ERP.")

    # Campos da referência (mapeados de 'references')
    type: Mapped[Optional[str]] = mapped_column(String(20), comment="Tipo da referência (campo 'type', ex: Banking, Commercial).")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="Descrição/Nome da referência (campo 'description').")
    phone_number: Mapped[Optional[str]] = mapped_column(String(30), comment="Telefone da referência (campo 'phoneNumber').")
    responsible_name: Mapped[Optional[str]] = mapped_column(Text, comment="Nome do responsável/contato na referência (campo 'responsiblePersonName').")
    is_inactive: Mapped[Optional[bool]] = mapped_column(Boolean, comment="Flag 'isInactive' da referência no ERP.")

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="references")

    __table_args__ = (UniqueConstraint('person_id', 'erp_sequence_code', name='uq_person_reference_sequence'),)

class RelatedPerson(CacheControlBase):
    __tablename__ = 'erp_person_related'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # A pessoa principal à qual esta relação pertence
    person_id: Mapped[int] = mapped_column(ForeignKey('erp_persons.id', ondelete='CASCADE'), index=True, nullable=False)

    # Detalhes da pessoa relacionada (mapeados de 'relateds')
    related_erp_code: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="Código ERP da pessoa relacionada (campo 'code').")
    related_cpf_cnpj: Mapped[Optional[str]] = mapped_column(String(14), comment="CPF/CNPJ da pessoa relacionada (campo 'cpfCnpj').")
    related_name: Mapped[Optional[str]] = mapped_column(Text, comment="Nome da pessoa relacionada (campo 'name').")

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="related_persons")

    __table_args__ = (UniqueConstraint('person_id', 'related_erp_code', name='uq_person_related_person'),)

class Representative(CacheControlBase):
    __tablename__ = 'erp_person_representatives'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('erp_persons.id', ondelete='CASCADE'), index=True, nullable=False)

    # Detalhes do representante associado (mapeados de 'representatives')
    representative_erp_code: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="Código ERP do representante (campo 'representativeCode').")
    cpf_cnpj: Mapped[Optional[str]] = mapped_column(String(14), comment="CPF/CNPJ do representante (campo 'cpfCnpj').")
    classification_code: Mapped[Optional[str]] = mapped_column(String(50), comment="Código da classificação do representante (campo 'classificationCode').")
    classification_type_code: Mapped[Optional[int]] = mapped_column(Integer, comment="Código do tipo de classificação do representante (campo 'classificationTypeCode').")

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="representatives")

    __table_args__ = (UniqueConstraint('person_id', 'representative_erp_code', name='uq_person_representative'),)

class Familiar(CacheControlBase):
    __tablename__ = 'erp_person_familiars' # Aplicável apenas a PF

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('erp_persons.id', ondelete='CASCADE'), index=True, nullable=False)

    # Detalhes do familiar (mapeados de 'familiars')
    name: Mapped[Optional[str]] = mapped_column(Text, comment="Nome do familiar (campo 'name').")
    birth_date: Mapped[Optional[date]] = mapped_column(Date, comment="Data de nascimento do familiar (campo 'birthDate').")
    gender: Mapped[Optional[str]] = mapped_column(String(20), comment="Gênero do familiar (campo 'gender').")
    kinship: Mapped[Optional[str]] = mapped_column(String(50), comment="Parentesco (campo 'kinshipDescription').")

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="familiars")

class Partner(CacheControlBase):
    __tablename__ = 'erp_person_partners' # Aplicável apenas a PJ

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('erp_persons.id', ondelete='CASCADE'), index=True, nullable=False)

    # Detalhes do sócio (mapeados de 'partners')
    partner_erp_code: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="Código ERP do sócio (campo 'code').")
    cpf_cnpj: Mapped[Optional[str]] = mapped_column(String(14), comment="CPF/CNPJ do sócio (campo 'cpfCnpj').")
    name: Mapped[Optional[str]] = mapped_column(Text, comment="Nome do sócio (campo 'name').")
    participation_percentage: Mapped[Optional[float]] = mapped_column(NUMERIC(5, 2), comment="Percentual de participação (campo 'percentageParticipation').") # Ex: 99.99

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="partners")

    __table_args__ = (UniqueConstraint('person_id', 'partner_erp_code', name='uq_person_partner'),)

class Contact(CacheControlBase):
    __tablename__ = 'erp_person_contacts' # Aplicável apenas a PJ

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('erp_persons.id', ondelete='CASCADE'), index=True, nullable=False)
    erp_sequence_code: Mapped[Optional[int]] = mapped_column(Integer, comment="Código de sequência do contato no ERP.")

    # Detalhes do contato (mapeados de 'contacts')
    name: Mapped[Optional[str]] = mapped_column(Text, comment="Nome do contato (campo 'name').")
    type_name: Mapped[Optional[str]] = mapped_column(String(50), comment="Tipo do contato (campo 'typeName').")
    function: Mapped[Optional[str]] = mapped_column(String(100), comment="Função/Cargo do contato (campo 'function').")
    phone_number: Mapped[Optional[str]] = mapped_column(String(30), comment="Telefone do contato (campo 'phoneNumber').")
    cell_number: Mapped[Optional[str]] = mapped_column(String(30), comment="Celular do contato (campo 'cellNumber').")
    email: Mapped[Optional[str]] = mapped_column(String(255), comment="Email do contato (campo 'email').")
    birth_date: Mapped[Optional[date]] = mapped_column(Date, comment="Data de nascimento do contato (campo 'birthDate').")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Indica se é o contato padrão (campo 'isDefault').")

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="contacts")

    __table_args__ = (UniqueConstraint('person_id', 'erp_sequence_code', name='uq_person_contact_sequence'),)

class SocialNetwork(CacheControlBase):
    __tablename__ = 'erp_person_social_networks' # Aplicável apenas a PJ

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('erp_persons.id', ondelete='CASCADE'), index=True, nullable=False)
    erp_sequence_code: Mapped[Optional[int]] = mapped_column(Integer, comment="Código de sequência da rede social no ERP.")

    # Detalhes da rede social (mapeados de 'socialNetworks')
    type_name: Mapped[Optional[str]] = mapped_column(String(50), comment="Tipo da rede social (campo 'typeName').")
    address: Mapped[Optional[str]] = mapped_column(Text, comment="Endereço/URL/Handle da rede social (campo 'address').")

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="social_networks")

    __table_args__ = (UniqueConstraint('person_id', 'erp_sequence_code', name='uq_person_social_network_sequence'),)

class PaymentMethod(CacheControlBase):
    __tablename__ = 'erp_person_payment_methods' # Aplicável apenas a PJ

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey('erp_persons.id', ondelete='CASCADE'), index=True, nullable=False)
    # O ERP retorna uma lista de inteiros, cada um representa um código de método de pagamento.
    erp_payment_method_code: Mapped[int] = mapped_column(Integer, nullable=False, comment="Código do método de pagamento aceito pela pessoa no ERP.")

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="payment_methods")

    # Garante que cada método de pagamento seja listado apenas uma vez por pessoa
    __table_args__ = (UniqueConstraint('person_id', 'erp_payment_method_code', name='uq_person_payment_method'),)

# --- Tabela de Preferências (One-to-One com Person) ---

class Preference(CacheControlBase):
    __tablename__ = 'erp_person_preferences'

    # Chave Primária e Estrangeira
    person_id: Mapped[int] = mapped_column(
        ForeignKey('erp_persons.id', ondelete='CASCADE'), primary_key=True
    )

    # Campos de preferências (mapeados de 'preferences')
    payment_condition_code: Mapped[Optional[int]] = mapped_column(Integer, comment="Código da condição de pagamento padrão (campo 'paymentConditionCode').")
    payment_condition_desc: Mapped[Optional[str]] = mapped_column(String(100), comment="Descrição da condição de pagamento (campo 'paymentConditionDescription').")
    shipping_company_code: Mapped[Optional[int]] = mapped_column(Integer, comment="Código da transportadora padrão (campo 'shippingCompanyCode').")
    shipping_company_name: Mapped[Optional[str]] = mapped_column(Text, comment="Nome da transportadora padrão (campo 'shippingCompanyName').")
    freight_type: Mapped[Optional[str]] = mapped_column(String(20), comment="Tipo de frete padrão (campo 'freightType').")
    # Adicionar outros campos de preferência aqui (bridgeShippingCompany, priceTable, bearer, etc.) se necessário

    # Relacionamento reverso
    person: Mapped["Person"] = relationship(back_populates="preferences")

    def __repr__(self):
        return f"<ErpPersonObservation(id={self.id}, person_id={self.person_id}, type='{self.observation_type}')>"