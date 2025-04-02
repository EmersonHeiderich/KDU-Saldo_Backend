# src/database/erp_cache/__init__.py
# Torna 'erp_cache' um pacote e exporta os repositórios definidos aqui.

# Importa o Repositório do cache de pessoas (definido em erp_person_repository.py neste diretório)
from .erp_person_repository import ErpPersonRepository # <<<--- CORRIGIDO

# Lista de Repositórios do cache a serem exportados
__all__ = [
    "ErpPersonRepository", # <<<--- CORRIGIDO
]

# NOTA: Os *modelos* ORM (Person, Address, etc.) não precisam ser exportados
# por este __init__.py. Eles são exportados pelo __init__.py do diretório PAI ('src/domain/erp_cache/__init__.py').
# Este __init__.py foca apenas nos artefatos *dentro* de src/database/erp_cache, que no caso é o repositório.