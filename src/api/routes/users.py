# src/api/routes/users.py
# Defines API endpoints for managing users (CRUD). Requires admin privileges.

from flask import Blueprint, request, jsonify, current_app
from src.domain.user import User, UserPermissions
from src.database.user_repository import UserRepository
from sqlalchemy.orm import Session
from src.database import get_db_session

from src.api.decorators import admin_required
from src.api.errors import ApiError, NotFoundError, ValidationError, ForbiddenError, DatabaseError
from src.utils.logger import logger

from sqlalchemy.exc import SQLAlchemyError

users_bp = Blueprint('users', __name__)

# Helper para obter UserRepository (pode ser movido para um local central se repetido)
def _get_user_repository() -> UserRepository:
      # Tentar obter do contexto da app se injetado (boa prática)
      repo = current_app.config.get('user_repository')
      if repo:
           return repo
      else:
           # Fallback: criar instância (menos ideal para testes, mas funciona)
           from src.database import get_user_repository as get_repo_func
           logger.warning("UserRepository accessed via factory function in users route.")
           return get_repo_func()

@users_bp.route('', methods=['GET'])
@admin_required
def get_all_users():
    """Retrieves a list of all users. (Admin only)"""
    logger.info("Get all users request received.")
    try:
        # Obter sessão e chamar repositório
        with get_db_session() as db:
            user_repo = _get_user_repository()
            users = user_repo.get_all(db) # Passar a sessão 'db'
        # Converter objetos ORM para dicts
        users_data = [user.to_dict(include_hash=False) for user in users]
        return jsonify({"users": users_data}), 200
    except (DatabaseError, SQLAlchemyError) as e:
          logger.error(f"Database error retrieving all users: {e}", exc_info=True)
          # Usar ApiError ou erro específico
          return jsonify({"error": "Failed to retrieve users due to database error."}), 500
    except Exception as e:
        logger.error(f"Error retrieving all users: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred while retrieving users."}), 500


@users_bp.route('/<int:user_id>', methods=['GET'])
@admin_required
def get_user_by_id(user_id: int):
    """Retrieves a specific user by their ID. (Admin only)"""
    logger.info(f"Get user by ID request received for ID: {user_id}")
    try:
        with get_db_session() as db:
            user_repo = _get_user_repository()
            user = user_repo.find_by_id(db, user_id) # Passar a sessão
        if not user:
            logger.warning(f"User with ID {user_id} not found.")
            raise NotFoundError(f"User with ID {user_id} not found.")

        # Converter objeto ORM para dict
        return jsonify(user.to_dict(include_hash=False)), 200
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except (DatabaseError, SQLAlchemyError) as e:
          logger.error(f"Database error retrieving user ID {user_id}: {e}", exc_info=True)
          return jsonify({"error": "Database error retrieving user."}), 500
    except Exception as e:
        logger.error(f"Error retrieving user ID {user_id}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500


@users_bp.route('', methods=['POST'])
@admin_required
def create_user():
    """Creates a new user with specified permissions. (Admin only)"""
    logger.info("Create user request received.")
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()

    required = ['username', 'password', 'name']
    missing = [field for field in required if field not in data or not data[field]]
    if missing:
        logger.warning(f"Create user failed: Missing required fields: {missing}")
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        # Criar instância de UserPermissions a partir dos dados da API
        permissions = UserPermissions(
            is_admin=data.get('is_admin', False),
            can_access_products=data.get('can_access_products', False),
            can_access_fabrics=data.get('can_access_fabrics', False),
            can_access_customer_panel=data.get('can_access_customer_panel', False),
            can_access_fiscal=data.get('can_access_fiscal', False),
            can_access_accounts_receivable=data.get('can_access_accounts_receivable', False)
        )

        # Criar instância de User e associar permissões
        user = User(
            username=data['username'],
            name=data['name'],
            email=data.get('email'),
            is_active=data.get('is_active', True),
            permissions=permissions # Associar o objeto de permissões
        )
        # Definir a senha (o método set_password está no modelo User)
        user.set_password(data['password'])
        if not user.password_hash: # Verificar se o hash foi gerado
              raise ValidationError("Failed to process password.")

        # Usar sessão para adicionar ao banco
        with get_db_session() as db:
            user_repo = _get_user_repository()
            created_user = user_repo.add(db, user) # Passar sessão e objeto User

        logger.info(f"User '{created_user.username}' (ID: {created_user.id}) created successfully.")
        # Converter objeto ORM para dict
        return jsonify(created_user.to_dict(include_hash=False)), 201

    except (ValidationError, ValueError) as e: # Captura erros de validação ou duplicidade
        logger.warning(f"Validation error creating user: {e}")
        return jsonify({"error": str(e)}), 400
    except (DatabaseError, SQLAlchemyError) as e:
         logger.error(f"Database error creating user: {e}", exc_info=True)
         return jsonify({"error": "Database error creating user."}), 500
    except Exception as e:
        logger.error(f"Unexpected error creating user: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred while creating user."}), 500


@users_bp.route('/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id: int):
    """Updates an existing user's details and/or permissions. (Admin only)"""
    logger.info(f"Update user request received for ID: {user_id}")
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    if not data:
          return jsonify({"error": "Request body cannot be empty for update."}), 400

    try:
        with get_db_session() as db:
            user_repo = _get_user_repository()
            # Buscar o usuário existente na sessão atual
            user = user_repo.find_by_id(db, user_id)
            if not user:
                raise NotFoundError(f"User with ID {user_id} not found.")

            # Atualizar campos do objeto User (a sessão rastreia as mudanças)
            if 'name' in data: user.name = data['name']
            if 'email' in data: user.email = data['email']
            if 'is_active' in data: user.is_active = data['is_active']

            new_password = data.get('password')
            if new_password:
                logger.debug(f"Updating password for user ID: {user_id}")
                user.set_password(new_password)
                if not user.password_hash:
                     raise ValidationError("Failed to process new password.")

            # Atualizar permissões (garantir que o objeto permissions existe)
            if not user.permissions:
                 logger.warning(f"User ID {user_id} found but missing permissions object during update. Creating default.")
                 user.permissions = UserPermissions() # Cria default associado

            # Atualizar campos do objeto UserPermissions
            user.permissions.is_admin = data.get('is_admin', user.permissions.is_admin)
            user.permissions.can_access_products = data.get('can_access_products', user.permissions.can_access_products)
            user.permissions.can_access_fabrics = data.get('can_access_fabrics', user.permissions.can_access_fabrics)
            user.permissions.can_access_customer_panel = data.get('can_access_customer_panel', user.permissions.can_access_customer_panel)
            user.permissions.can_access_fiscal = data.get('can_access_fiscal', user.permissions.can_access_fiscal)
            user.permissions.can_access_accounts_receivable = data.get('can_access_accounts_receivable', user.permissions.can_access_accounts_receivable)

            # Chamar o update do repositório (que apenas faz flush opcionalmente)
            # O commit será feito pelo get_db_session
            updated_user = user_repo.update(db, user) # Passa sessão e objeto modificado

        logger.info(f"User ID {user_id} update process completed.")
        # Retornar o usuário atualizado convertido para dict
        return jsonify(updated_user.to_dict(include_hash=False)), 200

    except NotFoundError as e:
          return jsonify({"error": str(e)}), 404
    except (ValidationError, ValueError) as e: # Captura validação ou email duplicado
        logger.warning(f"Validation error updating user ID {user_id}: {e}")
        return jsonify({"error": str(e)}), 400
    except (DatabaseError, SQLAlchemyError) as e:
          logger.error(f"Database error updating user ID {user_id}: {e}", exc_info=True)
          return jsonify({"error": "Database error updating user."}), 500
    except Exception as e:
        logger.error(f"Unexpected error updating user ID {user_id}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred while updating user."}), 500


@users_bp.route('/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id: int):
    """Deletes a user by their ID. (Admin only)"""
    logger.info(f"Delete user request received for ID: {user_id}")
    current_user = request.current_user # Set by @admin_required -> @login_required

    if current_user.id == user_id:
        raise ForbiddenError("Cannot delete your own user account.")

    try:
        with get_db_session() as db:
            user_repo = _get_user_repository()
            success = user_repo.delete(db, user_id) # Passar sessão

        if success:
            logger.info(f"User ID {user_id} deleted successfully.")
            return jsonify({"message": f"User ID {user_id} deleted successfully."}), 200
        else:
            # Se delete retornou False, significa que usuário não foi encontrado
            raise NotFoundError(f"User with ID {user_id} not found for deletion.")

    except ForbiddenError as e:
          return jsonify({"error": str(e)}), 403
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except (DatabaseError, SQLAlchemyError) as e:
          logger.error(f"Database error deleting user ID {user_id}: {e}", exc_info=True)
          return jsonify({"error": "Database error deleting user."}), 500
    except Exception as e:
        logger.error(f"Unexpected error deleting user ID {user_id}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred while deleting user."}), 500