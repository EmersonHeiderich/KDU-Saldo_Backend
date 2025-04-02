# src/database/erp_cache/erp_person_repository.py
# Repositório para interagir com as tabelas de cache de Pessoa do ERP.

from datetime import datetime, date, timezone
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy import select, delete, update
from sqlalchemy.orm import Session, joinedload, selectinload, contains_eager
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from src.database.base_repository import BaseRepository
# Importar todos os modelos ORM do cache de pessoa
from src.domain.erp_cache.person_cache import (
    Person, IndividualDetail, LegalEntityDetail, Address, Phone, Email,
    ErpPersonObservation,
    AdditionalField, Classification, Reference, RelatedPerson,
    Representative, Preference, Familiar, Partner, Contact, SocialNetwork,
    PaymentMethod
)
# Importar o modelo de estatísticas separadamente
from src.domain.erp_cache.statistics_cache import PersonStatistics

from src.utils.logger import logger
from src.api.errors import DatabaseError, NotFoundError

class ErpPersonRepository(BaseRepository):
    """
    Repositório para gerenciar dados de Pessoas (PF/PJ) cacheados do ERP
    no banco de dados local usando SQLAlchemy ORM.
    """

    # O construtor herda de BaseRepository (que recebe o engine),
    # mas os métodos usarão a Session passada como argumento.

    def find_by_erp_code(self, db: Session, erp_code: int) -> Optional[Person]:
        """
        Busca uma pessoa no cache local pelo seu código ERP.

        Args:
            db: A sessão SQLAlchemy ativa.
            erp_code: O código da pessoa no ERP.

        Returns:
            O objeto Person encontrado ou None.

        Raises:
            DatabaseError: Em caso de erro de banco de dados.
        """
        logger.debug(f"Buscando pessoa no cache pelo erp_code: {erp_code}")
        try:
            stmt = (
                select(Person)
                .where(Person.erp_code == erp_code)
                # Carregar detalhes e preferências junto, pois são 1-para-1 e frequentemente úteis
                .options(
                    joinedload(Person.individual_detail),
                    joinedload(Person.legal_entity_detail),
                    joinedload(Person.preferences),
                    joinedload(Person.statistics) # Carrega estatísticas também se existirem
                )
            )
            person = db.scalars(stmt).one_or_none()
            if person:
                logger.debug(f"Pessoa encontrada no cache para erp_code {erp_code} (ID: {person.id})")
            else:
                logger.debug(f"Pessoa não encontrada no cache para erp_code {erp_code}")
            return person
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar pessoa no cache por erp_code {erp_code}: {e}", exc_info=True)
            raise DatabaseError(f"Erro ao buscar pessoa no cache: {e}") from e

    def find_persons_to_sync(self, db: Session, changed_since: Optional[datetime] = None) -> List[Tuple[int, datetime]]:
        """
        Busca pessoas no cache que precisam ser atualizadas (baseado em last_sync_at).
        Ou busca todos os erp_codes se changed_since for None (para carga inicial).

        Args:
            db: A sessão SQLAlchemy ativa.
            changed_since: Data/hora limite. Buscará pessoas cuja última sincronização
                           foi *antes* desta data ou nula. Se None, retorna todos.

        Returns:
            Uma lista de tuplas (erp_code, last_sync_at ou data mínima) para referência.
        """
        logger.debug(f"Buscando pessoas no cache para sincronização (changed_since: {changed_since})")
        try:
            stmt = select(Person.erp_code, Person.last_sync_at)
            if changed_since:
                 # Busca registros que foram sincronizados antes da data de corte
                 # ou que nunca foram sincronizados (last_sync_at IS NULL)
                 stmt = stmt.where(
                     (Person.last_sync_at == None) | (Person.last_sync_at < changed_since) # noqa E711
                 )

            results = db.execute(stmt).all()
            # Retorna (erp_code, last_sync_at or very old date) para o serviço decidir
            min_datetime = datetime(1900, 1, 1, tzinfo=timezone.utc)
            persons_to_check = [(erp_code, last_sync or min_datetime) for erp_code, last_sync in results]

            logger.info(f"Encontradas {len(persons_to_check)} pessoas no cache para verificar sincronização.")
            return persons_to_check
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar pessoas para sincronizar no cache: {e}", exc_info=True)
            raise DatabaseError(f"Erro ao buscar pessoas para sincronizar: {e}") from e

    def upsert_person(self, db: Session, person_data: Dict[str, Any], person_type: str) -> Optional[Person]:
        """
        Insere ou atualiza os dados de uma pessoa (PF ou PJ) no cache local.
        Substitui dados relacionados (endereços, telefones, etc.) para garantir consistência.

        Args:
            db: A sessão SQLAlchemy ativa.
            person_data: O dicionário de dados para uma pessoa, vindo do ERP.
            person_type: 'PF' ou 'PJ'.

        Returns:
            O objeto Person inserido ou atualizado, ou None em caso de erro grave nos dados.

        Raises:
            DatabaseError: Em caso de erro de banco de dados.
            ValueError: Se dados essenciais como erp_code estiverem faltando.
        """
        erp_code = person_data.get('code')
        if not erp_code:
            logger.error(f"Dados da pessoa recebidos do ERP sem 'code': {person_data}")
            raise ValueError("Dados da pessoa do ERP estão incompletos (sem 'code').")

        logger.debug(f"Iniciando upsert no cache para Pessoa ERP {erp_code} (Tipo: {person_type})")

        try:
            existing_person = self.find_by_erp_code(db, erp_code)
            sync_time = datetime.now(timezone.utc)

            if existing_person:
                logger.debug(f"Atualizando pessoa existente no cache (ID: {existing_person.id})")
                person = existing_person
                # Limpa relações 1-para-muitos antes de adicionar as novas
                # A cascade delete-orphan cuidará da exclusão dos objetos antigos no flush
                logger.debug(f"Limpando relações existentes para pessoa ID {person.id}...")
                person.addresses.clear()
                person.phones.clear()
                person.emails.clear()
                person.observations.clear()
                person.additional_fields.clear()
                person.classifications.clear()
                person.references.clear()
                person.related_persons.clear()
                person.representatives.clear()
                if person_type == 'PF': person.familiars.clear()
                if person_type == 'PJ':
                    person.partners.clear()
                    person.contacts.clear()
                    person.social_networks.clear()
                    person.payment_methods.clear()
                
                # Força a execução das exclusões pendentes (devido ao delete-orphan)
                logger.debug(f"Executando flush para deletar relações órfãs da pessoa ID {person.id}...")
                db.flush()
                logger.debug(f"Relações órfãs deletadas para pessoa ID {person.id}.")
                # ------------------------------------------------------------

            else:
                logger.debug(f"Criando nova pessoa no cache para erp_code {erp_code}")
                person = Person(erp_code=erp_code, person_type=person_type)
                db.add(person) # Adiciona à sessão para obter o ID na FK

            # Atualiza/Define campos da tabela Person
            self._populate_person_fields(person, person_data, sync_time)

            # Atualiza/Cria detalhes específicos (PF/PJ)
            if person_type == 'PF':
                self._upsert_individual_detail(db, person, person_data, sync_time)
            elif person_type == 'PJ':
                self._upsert_legal_entity_detail(db, person, person_data, sync_time)

            # Atualiza/Cria detalhes 1-para-1 (Preferences)
            self._upsert_preferences(db, person, person_data.get('preferences'), sync_time)

            # Cria objetos relacionados 1-para-muitos (a limpeza foi feita acima se era update)
            logger.debug(f"Atribuindo novas relações para pessoa ID {person.id}...")
            person.addresses = [self._create_address(addr_data, sync_time) for addr_data in person_data.get('addresses', []) if addr_data]
            person.phones = [self._create_phone(phone_data, sync_time) for phone_data in person_data.get('phones', []) if phone_data]
            person.emails = [self._create_email(email_data, sync_time) for email_data in person_data.get('emails', []) if email_data]
            person.observations = self._create_observations(person_data, sync_time)
            person.additional_fields = [self._create_additional_field(field_data, sync_time) for field_data in person_data.get('additionalFields', []) if field_data]
            person.classifications = [self._create_classification(cls_data, sync_time) for cls_data in person_data.get('classifications', []) if cls_data]
            person.references = [self._create_reference(ref_data, sync_time) for ref_data in person_data.get('references', []) if ref_data]
            person.related_persons = [self._create_related_person(rel_data, sync_time) for rel_data in person_data.get('relateds', []) if rel_data]
            person.representatives = [self._create_representative(rep_data, sync_time) for rep_data in person_data.get('representatives', []) if rep_data]

            # Apenas para PF
            if person_type == 'PF':
                person.familiars = [self._create_familiar(fam_data, sync_time) for fam_data in person_data.get('familiars', []) if fam_data]

            # Apenas para PJ
            if person_type == 'PJ':
                person.partners = [self._create_partner(part_data, sync_time) for part_data in person_data.get('partners', []) if part_data]
                person.contacts = [self._create_contact(cont_data, sync_time) for cont_data in person_data.get('contacts', []) if cont_data]
                person.social_networks = [self._create_social_network(sn_data, sync_time) for sn_data in person_data.get('socialNetworks', []) if sn_data]
                payment_methods_data = person_data.get('paymentMethods')
                if isinstance(payment_methods_data, list):
                    person.payment_methods = [self._create_payment_method(pm_code, sync_time) for pm_code in payment_methods_data if isinstance(pm_code, int)]
                elif payment_methods_data is not None:
                     logger.warning(f"Campo 'paymentMethods' inesperado para pessoa ERP {erp_code}: tipo {type(payment_methods_data)}. Esperava lista ou None.")

            # Marcar como sincronizado (o commit será feito pelo serviço)
            person.last_sync_at = sync_time
            logger.info(f"Upsert da Pessoa ERP {erp_code} preparado na sessão.")
            return person

        except IntegrityError as e:
             db.rollback() # Importante reverter em caso de erro de constraint
             logger.error(f"Erro de integridade ao fazer upsert da pessoa ERP {erp_code}: {e}", exc_info=True)
             # Verificar se é erro de CPF/CNPJ duplicado em outra pessoa
             error_info = str(e.orig).lower() if e.orig else str(e).lower()
             if "uq_erp_individual_details_cpf" in error_info:
                  raise DatabaseError(f"CPF já existe para outra pessoa no cache.", is_retryable=False) from e
             if "uq_erp_legal_entity_details_cnpj" in error_info:
                  raise DatabaseError(f"CNPJ já existe para outra pessoa no cache.", is_retryable=False) from e
             raise DatabaseError(f"Erro de integridade no upsert da pessoa: {e}", is_retryable=False) from e # Não tentar novamente
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Erro de SQLAlchemy ao fazer upsert da pessoa ERP {erp_code}: {e}", exc_info=True)
            raise DatabaseError(f"Erro de banco de dados no upsert da pessoa: {e}") from e
        except Exception as e:
            db.rollback()
            logger.error(f"Erro inesperado ao fazer upsert da pessoa ERP {erp_code}: {e}", exc_info=True)
            raise DatabaseError(f"Erro inesperado no upsert da pessoa: {e}") from e

    def update_sync_timestamp(self, db: Session, erp_code: int, sync_time: datetime) -> bool:
        """Atualiza o timestamp da última sincronização para uma pessoa."""
        logger.debug(f"Atualizando last_sync_at para pessoa ERP {erp_code}")
        try:
            stmt = (
                update(Person)
                .where(Person.erp_code == erp_code)
                .values(last_sync_at=sync_time, updated_at=sync_time) # Atualiza updated_at também
                .execution_options(synchronize_session="fetch") # Estratégia de sincronização
            )
            result = db.execute(stmt)
            return result.rowcount > 0 # Retorna True se alguma linha foi atualizada
        except SQLAlchemyError as e:
            logger.error(f"Erro ao atualizar last_sync_at para pessoa ERP {erp_code}: {e}", exc_info=True)
            # Não levanta erro aqui necessariamente, mas loga. O processo pode continuar.
            return False

    # --- Métodos Auxiliares Privados para Popular Dados ---

    def _parse_datetime(self, date_string: Optional[str]) -> Optional[datetime]:
        """Converte string ISO 8601 para datetime com timezone UTC."""
        if not date_string:
            return None
        try:
            # Remove 'Z' e adiciona offset UTC explicitamente se necessário
            if date_string.endswith('Z'):
                date_string = date_string[:-1] + '+00:00'
            dt = datetime.fromisoformat(date_string)
            # Se não tiver timezone, assume UTC (ou a timezone do servidor ERP se conhecida)
            if dt.tzinfo is None:
                 dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            logger.warning(f"Falha ao converter string de data/hora para datetime: {date_string}")
            return None

    def _parse_date(self, date_string: Optional[str]) -> Optional[date]:
        """Converte string ISO 8601 (ou YYYY-MM-DD) para date."""
        if not date_string:
            return None
        try:
            # Tenta extrair apenas a parte da data se for datetime completo
            date_part = date_string.split('T')[0]
            return date.fromisoformat(date_part)
        except ValueError:
            logger.warning(f"Falha ao converter string de data para date: {date_string}")
            return None

    def _populate_person_fields(self, person: Person, data: Dict[str, Any], sync_time: datetime):
        """Popula os campos do objeto Person principal."""
        person.name = data.get('name', 'N/A') # Nome é obrigatório
        person.is_inactive = data.get('isInactive', False)
        person.is_customer = data.get('isCustomer')
        person.is_supplier = data.get('isSupplier')
        person.is_representative = data.get('isRepresentative')
        person.is_employee = data.get('isEmployee')
        person.customer_status = data.get('customerStatus')
        person.employee_status = data.get('employeeStatus')
        person.erp_insert_date = self._parse_datetime(data.get('insertDate'))
        person.erp_change_date = self._parse_datetime(data.get('maxChangeFilterDate'))
        # last_sync_at é definido no final do upsert

    def _upsert_individual_detail(self, db: Session, person: Person, data: Dict[str, Any], sync_time: datetime):
        """Cria ou atualiza os detalhes de Pessoa Física."""
        detail = person.individual_detail
        if not detail:
            detail = IndividualDetail(person=person) # Associa ao criar

        # Popula campos
        detail.cpf = data.get('cpf', 'N/A') # CPF é obrigatório
        if detail.cpf == 'N/A': logger.error(f"CPF faltando para indivíduo ERP {person.erp_code}")
        detail.rg = data.get('rg')
        detail.rg_federal_agency = data.get('rgFederalAgency')
        detail.birth_date = self._parse_date(data.get('birthDate'))
        detail.marital_status = data.get('maritalStatus')
        detail.gender = data.get('gender')
        detail.mother_name = data.get('motherName')
        detail.father_name = data.get('fatherName')
        detail.nationality = data.get('nationality')
        detail.last_sync_at = sync_time
        # Atualiza updated_at do detalhe também (via onupdate=func.now())

        person.individual_detail = detail # Garante a associação

    def _upsert_legal_entity_detail(self, db: Session, person: Person, data: Dict[str, Any], sync_time: datetime):
        """Cria ou atualiza os detalhes de Pessoa Jurídica."""
        detail = person.legal_entity_detail
        if not detail:
            detail = LegalEntityDetail(person=person)

        detail.cnpj = data.get('cnpj', 'N/A') # CNPJ é obrigatório
        if detail.cnpj == 'N/A': logger.error(f"CNPJ faltando para entidade legal ERP {person.erp_code}")
        detail.fantasy_name = data.get('fantasyName')
        detail.state_registration = data.get('numberStateRegistration')
        detail.state_registration_uf = data.get('uf')
        detail.foundation_date = self._parse_date(data.get('dateFoundation'))
        detail.municipal_registration = data.get('registrationMunicipal')
        detail.share_capital = data.get('shareCapital')
        detail.last_sync_at = sync_time

        person.legal_entity_detail = detail

    def _upsert_preferences(self, db: Session, person: Person, pref_data: Optional[Dict[str, Any]], sync_time: datetime):
        """Cria ou atualiza as preferências da pessoa."""
        if not pref_data:
            # Se não há dados de preferência no ERP, removemos do cache se existir
            if person.preferences:
                logger.debug(f"Removendo preferências do cache para pessoa ERP {person.erp_code} pois não vieram do ERP.")
                db.delete(person.preferences)
                person.preferences = None
            return

        pref = person.preferences
        if not pref:
            pref = Preference(person=person)

        pref.payment_condition_code = pref_data.get('paymentConditionCode')
        pref.payment_condition_desc = pref_data.get('paymentConditionDescription')
        pref.shipping_company_code = pref_data.get('shippingCompanyCode')
        pref.shipping_company_name = pref_data.get('shippingCompanyName')
        pref.freight_type = pref_data.get('freightType')
        # Adicionar outros campos se mapeados no modelo Preference
        pref.last_sync_at = sync_time

        person.preferences = pref

    def _create_address(self, data: Dict[str, Any], sync_time: datetime) -> Address:
        """Cria um objeto Address a partir dos dados do ERP."""
        # Obter os dados brutos do ERP
        erp_public_place = data.get('publicPlace')
        erp_address_detail = data.get('address') # 'address' do ERP vai para 'address_detail' no ORM

        # --- CORREÇÃO AQUI ---
        # Mapear para os nomes de atributos corretos da classe ORM Address
        return Address(
            erp_sequence_code=data.get('sequenceCode'),
            address_type=data.get('addressType'),
            public_place=erp_public_place,       # Mapeia para public_place
            address_detail=erp_address_detail, # Mapeia para address_detail
            number=str(data['addressNumber']) if data.get('addressNumber') is not None else None,
            complement=data.get('complement'),
            neighborhood=data.get('neighborhood'),
            city_name=data.get('cityName'),
            state_abbreviation=data.get('stateAbbreviation'),
            zip_code=data.get('cep'),
            country_name=data.get('countryName'),
            reference=data.get('reference'),
            is_default=data.get('isDefault', False),
            last_sync_at=sync_time
        )

    def _create_phone(self, data: Dict[str, Any], sync_time: datetime) -> Phone:
        """Cria um objeto Phone a partir dos dados do ERP."""
        return Phone(
            # Lida com 'Sequence' vs 'sequence'
            erp_sequence_code=data.get('Sequence') or data.get('sequence'),
            type_name=data.get('typeName'),
            number=data.get('number'),
            extension=str(data['branchLine']) if data.get('branchLine') is not None else None,
            is_default=data.get('isDefault', False),
            last_sync_at=sync_time
        )

    def _create_email(self, data: Dict[str, Any], sync_time: datetime) -> Email:
        """Cria um objeto Email a partir dos dados do ERP."""
        return Email(
            erp_sequence_code=data.get('sequence'),
            type_name=data.get('typeName'),
            email_address=data.get('email'),
            is_default=data.get('isDefault', False),
            last_sync_at=sync_time
        )

    def _create_observations(self, person_data: Dict[str, Any], sync_time: datetime) -> List[ErpPersonObservation]:
        """Cria uma lista de objetos ErpPersonObservation a partir dos dados do ERP."""
        observations = []

        # Verificar se a lista existe e não é None antes de iterar ---
        general_observations = person_data.get('observations') # Não usar default aqui ainda
        if isinstance(general_observations, list): # Verifica se é uma lista
            for obs_data in general_observations:
                if obs_data: # Verifica se o item da lista não é None/vazio
                    observations.append(ErpPersonObservation(
                        erp_sequence_code=obs_data.get('sequence'),
                        observation_type='General',
                        observation_text=obs_data.get('observation'),
                        is_maintenance=obs_data.get('isMaintenance'),
                        last_sync_at=sync_time
                    ))
        elif general_observations is not None:
            logger.warning(f"Campo 'observations' inesperado para pessoa ERP {person_data.get('code')}: tipo {type(general_observations)}. Esperava lista ou None.")

        # Verificar se a lista existe e não é None antes de iterar
        customer_observations = person_data.get('customerObservations') # Não usar default aqui ainda
        if isinstance(customer_observations, list): # Verifica se é uma lista
             for obs_data in customer_observations:
                 if obs_data: # Verifica se o item da lista não é None/vazio
                    observations.append(ErpPersonObservation(
                        erp_sequence_code=obs_data.get('sequence'),
                        observation_type='Customer',
                        observation_text=obs_data.get('observation'),
                        is_maintenance=obs_data.get('isMaintenance'),
                        erp_last_change_date=self._parse_datetime(obs_data.get('LastChangeDate')),
                        last_sync_at=sync_time
                    ))
        elif customer_observations is not None:
            logger.warning(f"Campo 'customerObservations' inesperado para pessoa ERP {person_data.get('code')}: tipo {type(customer_observations)}. Esperava lista ou None.")

        return observations

    def _create_additional_field(self, data: Dict[str, Any], sync_time: datetime) -> AdditionalField:
        """Cria um objeto AdditionalField a partir dos dados do ERP."""
        return AdditionalField(
            erp_field_code=data.get('code', -1), # Usar um default inválido se faltar
            erp_field_name=data.get('name'),
            erp_field_type=data.get('type'),
            value=str(data['value']) if data.get('value') is not None else None, # Converte para string
            last_sync_at=sync_time
        )

    def _create_classification(self, data: Dict[str, Any], sync_time: datetime) -> Classification:
        """Cria um objeto Classification a partir dos dados do ERP."""
        return Classification(
            type_code=data.get('typeCode', -1),
            type_name=data.get('typeName'),
            code=data.get('code', 'N/A'),
            name=data.get('name'),
            last_sync_at=sync_time
        )

    def _create_reference(self, data: Dict[str, Any], sync_time: datetime) -> Reference:
        """Cria um objeto Reference a partir dos dados do ERP."""
        return Reference(
            erp_sequence_code=data.get('sequence'),
            type=data.get('type'),
            description=data.get('description'),
            phone_number=data.get('phoneNumber'),
            responsible_name=data.get('responsiblePersonName'),
            is_inactive=data.get('isInactive'),
            last_sync_at=sync_time
        )

    def _create_related_person(self, data: Dict[str, Any], sync_time: datetime) -> RelatedPerson:
        """Cria um objeto RelatedPerson a partir dos dados do ERP."""
        return RelatedPerson(
            related_erp_code=data.get('code', -1),
            related_cpf_cnpj=data.get('cpfCnpj'),
            related_name=data.get('name'),
            last_sync_at=sync_time
        )

    def _create_representative(self, data: Dict[str, Any], sync_time: datetime) -> Representative:
         """Cria um objeto Representative a partir dos dados do ERP."""
         return Representative(
              representative_erp_code=data.get('representativeCode', -1),
              cpf_cnpj=data.get('cpfCnpj'),
              classification_code=data.get('classificationCode'),
              classification_type_code=data.get('classificationTypeCode'),
              last_sync_at=sync_time
         )

    def _create_familiar(self, data: Dict[str, Any], sync_time: datetime) -> Familiar:
         """Cria um objeto Familiar a partir dos dados do ERP."""
         return Familiar(
              name=data.get('name'),
              birth_date=self._parse_date(data.get('birthDate')),
              gender=data.get('gender'),
              kinship=data.get('kinshipDescription'),
              last_sync_at=sync_time
         )

    def _create_partner(self, data: Dict[str, Any], sync_time: datetime) -> Partner:
         """Cria um objeto Partner a partir dos dados do ERP."""
         return Partner(
              partner_erp_code=data.get('code', -1),
              cpf_cnpj=data.get('cpfCnpj'),
              name=data.get('name'),
              participation_percentage=data.get('percentageParticipation'),
              last_sync_at=sync_time
         )

    def _create_contact(self, data: Dict[str, Any], sync_time: datetime) -> Contact:
         """Cria um objeto Contact a partir dos dados do ERP."""
         return Contact(
              erp_sequence_code=data.get('sequence'),
              name=data.get('name'),
              type_name=data.get('typeName'),
              function=data.get('function'),
              phone_number=data.get('phoneNumber'),
              cell_number=data.get('cellNumber'),
              email=data.get('email'),
              birth_date=self._parse_date(data.get('birthDate')),
              is_default=data.get('isDefault', False),
              last_sync_at=sync_time
         )

    def _create_social_network(self, data: Dict[str, Any], sync_time: datetime) -> SocialNetwork:
         """Cria um objeto SocialNetwork a partir dos dados do ERP."""
         return SocialNetwork(
              erp_sequence_code=data.get('sequence'),
              type_name=data.get('typeName'),
              address=data.get('address'),
              last_sync_at=sync_time
         )

    def _create_payment_method(self, code: int, sync_time: datetime) -> PaymentMethod:
         """Cria um objeto PaymentMethod a partir do código do ERP."""
         return PaymentMethod(
              erp_payment_method_code=code,
              last_sync_at=sync_time
         )


    # --- Método para Estatísticas ---
    def upsert_statistics(self, db: Session, person_erp_code: int, stats_data: Dict[str, Any]) -> Optional[PersonStatistics]:
        """
        Insere ou atualiza os dados de estatísticas de uma pessoa no cache.

        Args:
            db: A sessão SQLAlchemy ativa.
            person_erp_code: O código ERP da pessoa à qual as estatísticas pertencem.
            stats_data: Dicionário com os dados de estatísticas vindos do ERP.

        Returns:
            O objeto PersonStatistics inserido/atualizado ou None se a pessoa não for encontrada no cache.

        Raises:
            DatabaseError: Em caso de erro de banco de dados.
        """
        logger.debug(f"Iniciando upsert de estatísticas no cache para Pessoa ERP {person_erp_code}")
        try:
            # 1. Encontra a pessoa no cache para obter o ID interno
            person = self.find_by_erp_code(db, person_erp_code)
            if not person:
                logger.warning(f"Não foi possível fazer upsert das estatísticas: Pessoa ERP {person_erp_code} não encontrada no cache.")
                return None

            sync_time = datetime.now(timezone.utc)

            # 2. Busca ou cria o registro de estatísticas
            stats = person.statistics # Tenta obter via relationship carregado
            if not stats:
                # Se não veio no joinedload ou não existia, tenta buscar explicitamente
                stats_stmt = select(PersonStatistics).where(PersonStatistics.person_id == person.id)
                stats = db.scalars(stats_stmt).one_or_none()
                if not stats:
                    logger.debug(f"Criando novo registro de estatísticas para Pessoa ID {person.id} (ERP {person_erp_code})")
                    stats = PersonStatistics(person_id=person.id) # Cria e associa o ID
                    db.add(stats) # Adiciona à sessão

            # 3. Popula os campos de estatísticas
            stats.average_delay = stats_data.get('averageDelay')
            stats.maximum_delay = stats_data.get('maximumDelay')
            stats.purchase_quantity = stats_data.get('purchaseQuantity')
            stats.total_purchase_value = stats_data.get('totalPurchaseValue')
            stats.average_purchase_value = stats_data.get('averagePurchaseValue')
            stats.biggest_purchase_date = self._parse_date(stats_data.get('biggestPurchaseDate'))
            stats.biggest_purchase_value = stats_data.get('biggestPurchaseValue')
            stats.first_purchase_date = self._parse_date(stats_data.get('firstPurchaseDate'))
            stats.first_purchase_value = stats_data.get('firstPurchaseValue')
            stats.last_purchase_value = stats_data.get('lastPurchaseValue')
            stats.last_purchase_date = self._parse_date(stats_data.get('lastPurchaseDate'))
            stats.total_installments_paid = stats_data.get('totalInstallmentsPaid')
            stats.quantity_installments_paid = stats_data.get('quantityInstallmentsPaid')
            stats.average_value_installments_paid = stats_data.get('averageValueInstallmentsPaid')
            stats.total_installments_delayed = stats_data.get('totalInstallmentsDelayed')
            stats.quantity_installments_delayed = stats_data.get('quantityInstallmentsDelayed')
            stats.average_installment_delay = stats_data.get('averageInstallmentDelay')
            stats.total_installments_open = stats_data.get('totalInstallmentsOpen')
            stats.quantity_installments_open = stats_data.get('quantityInstallmentsOpen')
            stats.average_installments_open = stats_data.get('averageInstallmentsOpen')
            stats.last_invoice_paid_value = stats_data.get('lastInvoicePaidValue')
            stats.last_invoice_paid_date = self._parse_date(stats_data.get('lastInvoicePaidDate'))

            # 4. Atualiza timestamp de sincronização das estatísticas
            stats.last_sync_at = sync_time

            logger.info(f"Upsert das Estatísticas para Pessoa ERP {person_erp_code} preparado na sessão.")
            return stats

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Erro de SQLAlchemy ao fazer upsert das estatísticas para pessoa ERP {person_erp_code}: {e}", exc_info=True)
            raise DatabaseError(f"Erro de banco de dados no upsert das estatísticas: {e}") from e
        except Exception as e:
            db.rollback()
            logger.error(f"Erro inesperado ao fazer upsert das estatísticas para pessoa ERP {person_erp_code}: {e}", exc_info=True)
            raise DatabaseError(f"Erro inesperado no upsert das estatísticas: {e}") from e