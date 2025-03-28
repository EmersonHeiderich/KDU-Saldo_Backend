# src/api/routes/users.py
# Defines API endpoints for managing users (CRUD). Requires admin privileges.

from flask import Blueprint, request, jsonify, current_app
from src.services.auth_service import AuthService # Uses User Repo via AuthService
from src.domain.user import User, UserPermissions
from src.database.user_repository import UserRepository # Direct use for CRUD might be okay for admin tasks
from src.api.decorators import admin_required # Decorator for admin access control
from src.api.errors import ApiError, NotFoundError, ValidationError, ForbiddenError # Custom errors
from src.utils.logger import logger

users_bp = Blueprint('users', __name__)

# Helper to get UserRepository instance
def _get_user_repository() -> UserRepository:
      auth_service: AuthService = current_app.config.get('auth_service')
      if auth_service and hasattr(auth_service, 'user_repository'):
          return auth_service.user_repository
      else:
          from src.database import get_user_repository # Lazy import
          logger.warning("UserRepository accessed directly via pool factory in users route.")
          return get_user_repository()

@users_bp.route('', methods=['GET'])
@admin_required
def get_all_users():
    """
    Retrieves a list of all users and their permissions. (Admin only)
    ---
    tags: [Users]
    security:
      - bearerAuth: []
    responses:
      200:
        description: List of users.
        content:
          application/json:
            schema:
              type: object
              properties:
                users:
                  type: array
                  items:
                    # Define User schema (excluding password hash) - Reuse/Define elsewhere for DRY
                    type: object
                    properties:
                      id: {type: integer}
                      username: {type: string}
                      name: {type: string}
                      email: {type: string, nullable: true}
                      created_at: {type: string, format: date-time}
                      last_login: {type: string, format: date-time, nullable: true}
                      is_active: {type: boolean}
                      permissions:
                          type: object
                          properties:
                            id: {type: integer, nullable: true} # ID can be null if no perms row yet
                            user_id: {type: integer, nullable: true}
                            is_admin: {type: boolean}
                            can_access_products: {type: boolean}
                            can_access_fabrics: {type: boolean}
                            can_access_customer_panel: {type: boolean}
                            can_access_fiscal: {type: boolean} # <<<--- ADDED
    401: {description: Unauthorized}
    403: {description: Forbidden (User is not admin)}
    500: {description: Internal server error}
    """
    logger.info("Get all users request received.")
    try:
        user_repo = _get_user_repository()
        users = user_repo.get_all()
        users_data = [user.to_dict(include_hash=False) for user in users]
        return jsonify({"users": users_data}), 200
    except ApiError as e:
          logger.error(f"API error retrieving all users: {e.message}", exc_info=False)
          return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Error retrieving all users: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred while retrieving users."}), 500


@users_bp.route('/<int:user_id>', methods=['GET'])
@admin_required
def get_user_by_id(user_id: int):
    """
    Retrieves a specific user by their ID. (Admin only)
    ---
    tags: [Users]
    security:
      - bearerAuth: []
    parameters:
      - in: path
        name: user_id
        schema: {type: integer}
        required: true
        description: The ID of the user to retrieve.
    responses:
      200:
        description: User details found.
        content:
          application/json:
            schema:
              # Reuse User schema definition from above/elsewhere
              $ref: '#/paths/~1api~1users/get/responses/200/content/application~1json/schema/properties/users/items'
      401: {description: Unauthorized}
      403: {description: Forbidden (User is not admin)}
      404: {description: User not found.}
      500: {description: Internal server error}
    """
    logger.info(f"Get user by ID request received for ID: {user_id}")
    try:
        user_repo = _get_user_repository()
        user = user_repo.find_by_id(user_id)
        if not user:
            logger.warning(f"User with ID {user_id} not found.")
            raise NotFoundError(f"User with ID {user_id} not found.")

        return jsonify(user.to_dict(include_hash=False)), 200
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ApiError as e:
          logger.error(f"API error retrieving user ID {user_id}: {e.message}", exc_info=False)
          return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Error retrieving user ID {user_id}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500


@users_bp.route('', methods=['POST'])
@admin_required
def create_user():
    """
    Creates a new user with specified permissions. (Admin only)
    ---
    tags: [Users]
    security:
      - bearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              username: {type: string}
              password: {type: string}
              name: {type: string}
              email: {type: string, format: email, nullable: true}
              is_active: {type: boolean, default: true}
              # Permissions
              is_admin: {type: boolean, default: false}
              can_access_products: {type: boolean, default: false}
              can_access_fabrics: {type: boolean, default: false}
              can_access_customer_panel: {type: boolean, default: false}
              can_access_fiscal: {type: boolean, default: false} # <<<--- ADDED
            required: [username, password, name]
    responses:
      201:
        description: User created successfully.
        content:
          application/json:
            schema:
              $ref: '#/paths/~1api~1users/get/responses/200/content/application~1json/schema/properties/users/items'
      400: {description: Bad request (Invalid JSON, missing fields, validation error like duplicate username/email).}
      401: {description: Unauthorized}
      403: {description: Forbidden (User is not admin)}
      500: {description: Internal server error}
    """
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
        # Create Permissions object
        permissions = UserPermissions(
            is_admin=data.get('is_admin', False),
            can_access_products=data.get('can_access_products', False),
            can_access_fabrics=data.get('can_access_fabrics', False),
            can_access_customer_panel=data.get('can_access_customer_panel', False),
            can_access_fiscal=data.get('can_access_fiscal', False) # <<<--- ADDED
        )

        # Create User object
        user = User(
            username=data['username'],
            name=data['name'],
            email=data.get('email'),
            is_active=data.get('is_active', True),
            permissions=permissions
        )
        user.set_password(data['password'])
        if not user.password_hash:
              raise ApiError("Failed to process password.", 500)

        user_repo = _get_user_repository()
        created_user = user_repo.add(user)

        logger.info(f"User '{created_user.username}' (ID: {created_user.id}) created successfully.")
        return jsonify(created_user.to_dict(include_hash=False)), 201

    except ValueError as e: # Catch validation errors (e.g., duplicate username/email)
        logger.warning(f"Validation error creating user: {e}")
        return jsonify({"error": str(e)}), 400
    except ApiError as e:
          logger.error(f"API error creating user: {e.message}", exc_info=False)
          return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error creating user: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred while creating user."}), 500


@users_bp.route('/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id: int):
    """
    Updates an existing user's details and/or permissions. (Admin only)
    Password can be updated by providing a new 'password' field.
    ---
    tags: [Users]
    security:
      - bearerAuth: []
    parameters:
      - in: path
        name: user_id
        schema: {type: integer}
        required: true
        description: The ID of the user to update.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              name: {type: string}
              email: {type: string, format: email, nullable: true}
              is_active: {type: boolean}
              password: {type: string, description: "Provide new password to change it. Omit or send null/empty to keep existing."}
              # Permissions
              is_admin: {type: boolean}
              can_access_products: {type: boolean}
              can_access_fabrics: {type: boolean}
              can_access_customer_panel: {type: boolean}
              can_access_fiscal: {type: boolean} # <<<--- ADDED
            minProperties: 1 # Require at least one field to update
    responses:
      200:
        description: User updated successfully.
        content:
          application/json:
            schema:
              $ref: '#/paths/~1api~1users/get/responses/200/content/application~1json/schema/properties/users/items'
      400: {description: Bad request (Invalid JSON, validation error like duplicate email).}
      401: {description: Unauthorized}
      403: {description: Forbidden (User is not admin)}
      404: {description: User not found.}
      500: {description: Internal server error}
    """
    logger.info(f"Update user request received for ID: {user_id}")
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    if not data:
          return jsonify({"error": "Request body cannot be empty for update."}), 400

    try:
        user_repo = _get_user_repository()
        user = user_repo.find_by_id(user_id)
        if not user:
            logger.warning(f"Attempted to update non-existent user ID: {user_id}")
            raise NotFoundError(f"User with ID {user_id} not found.")

        # Ensure user has permissions object loaded
        if not user.permissions:
              # This indicates a data inconsistency (user exists but permissions missing)
              logger.error(f"Data inconsistency: Permissions missing for user ID {user_id}. Cannot update.")
              raise ApiError(f"Data inconsistency: Permissions missing for user ID {user_id}.", 500)

        # --- Update user fields ---
        if 'name' in data: user.name = data['name']
        if 'email' in data: user.email = data['email'] # Let repo handle validation
        if 'is_active' in data: user.is_active = data['is_active']

        # Update password only if provided and not empty
        new_password = data.get('password')
        if new_password:
            logger.debug(f"Updating password for user ID: {user_id}")
            user.set_password(new_password)
            if not user.password_hash:
                  raise ApiError("Failed to process new password.", 500)
        # Keep existing hash if 'password' is not in data or is empty/null

        # --- Update permissions ---
        # Use get(key, default_value) where default is current value
        user.permissions.is_admin = data.get('is_admin', user.permissions.is_admin)
        user.permissions.can_access_products = data.get('can_access_products', user.permissions.can_access_products)
        user.permissions.can_access_fabrics = data.get('can_access_fabrics', user.permissions.can_access_fabrics)
        user.permissions.can_access_customer_panel = data.get('can_access_customer_panel', user.permissions.can_access_customer_panel)
        user.permissions.can_access_fiscal = data.get('can_access_fiscal', user.permissions.can_access_fiscal) # <<<--- ADDED

        # --- Persist changes ---
        success = user_repo.update(user) # Repo handles transaction for user+perms

        if not success:
              # update returns False if 0 rows were affected (data was identical or error)
              logger.warning(f"User update for ID {user_id} reported no changes or failed silently (check logs).")
              # Re-fetch to ensure current state is returned even if no DB change occurred
              # or if repo raised an error that was caught below.

        # Fetch again to get potentially updated timestamps etc. and confirm changes
        updated_user = user_repo.find_by_id(user_id)
        if not updated_user: # Should not happen after finding user initially
              raise ApiError("Failed to retrieve user after update attempt.", 500)

        logger.info(f"User ID {user_id} update process completed.")
        return jsonify(updated_user.to_dict(include_hash=False)), 200

    except NotFoundError as e:
          return jsonify({"error": str(e)}), 404
    except ValueError as e: # Catch validation errors (e.g., duplicate email)
        logger.warning(f"Validation error updating user ID {user_id}: {e}")
        return jsonify({"error": str(e)}), 400
    except ApiError as e:
          logger.error(f"API error updating user ID {user_id}: {e.message}", exc_info=False)
          return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error updating user ID {user_id}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred while updating user."}), 500


@users_bp.route('/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id: int):
    """
    Deletes a user by their ID. (Admin only)
    Cannot delete the currently logged-in admin.
    ---
    tags: [Users]
    security:
      - bearerAuth: []
    parameters:
      - in: path
        name: user_id
        schema: {type: integer}
        required: true
        description: The ID of the user to delete.
    responses:
      200:
        description: User deleted successfully.
        content:
          application/json:
            schema:
              type: object
              properties:
                message: {type: string}
      400:
        description: Bad request (e.g., trying to delete self).
      401: {description: Unauthorized}
      403: {description: Forbidden (User is not admin or trying to delete self)}
      404: {description: User not found.}
      500: {description: Internal server error}
    """
    logger.info(f"Delete user request received for ID: {user_id}")
    current_user = request.current_user # Set by @admin_required -> @login_required

    if current_user.id == user_id:
        logger.warning(f"Admin user (ID: {current_user.id}) attempted to delete self.")
        # Use 403 Forbidden instead of 400 Bad Request for this case
        raise ForbiddenError("Cannot delete your own user account.")

    try:
        user_repo = _get_user_repository()
        # Optional: Check if user exists before attempting delete for better logging/response
        user_to_delete = user_repo.find_by_id(user_id)
        if not user_to_delete:
              raise NotFoundError(f"User with ID {user_id} not found.")

        success = user_repo.delete(user_id) # Repo uses CASCADE for permissions

        if success:
            logger.info(f"User ID {user_id} deleted successfully.")
            return jsonify({"message": f"User ID {user_id} deleted successfully."}), 200
        else:
            # This means the delete operation affected 0 rows, implying user didn't exist
            # which contradicts the check above if performed. Raise 404.
            logger.warning(f"Deletion of user ID {user_id} reported failure (likely not found).")
            raise NotFoundError(f"User with ID {user_id} not found.")

    except ForbiddenError as e:
          return jsonify({"error": str(e)}), 403
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ApiError as e:
          logger.error(f"API error deleting user ID {user_id}: {e.message}", exc_info=False)
          return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Unexpected error deleting user ID {user_id}: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred while deleting user."}), 500