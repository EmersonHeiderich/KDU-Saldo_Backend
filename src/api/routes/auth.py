# src/api/routes/auth.py

from flask import Blueprint, request, jsonify, current_app, session
from src.services.auth_service import AuthService
from src.api.decorators import login_required
from src.api.errors import AuthenticationError, ApiError
from src.utils.logger import logger

auth_bp = Blueprint('auth', __name__)

def _get_auth_service() -> AuthService:
     service = current_app.config.get('auth_service')
     if not service:
          logger.critical("Serviço de autenticação não encontrado na configuração da aplicação!")
          raise ApiError("Serviço de autenticação indisponível.", 503)
     return service

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Endpoint for user login. Expects JSON payload with 'username' and 'password'.
    Sets a token in the session and returns user info upon success.
    ---
    tags: [Authentication]
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              username:
                type: string
                example: "testuser"
              password:
                type: string
                example: "password123"
            required: [username, password]
    responses:
      200:
        description: Login successful
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Login successful"
                token:
                  type: string
                  description: JWT token (also set in session cookie)
                user:
                  type: object
                  example: {"id": 1, "username": "testuser", "name": "Test User", "email": "test@example.com", "is_active": true, "permissions": {"is_admin": false, ...}}
      400:
        description: Bad request (missing fields or invalid JSON)
      401:
        description: Authentication failed (invalid credentials or inactive user)
      500:
        description: Internal server error
    """
    logger.info("Requisição de login recebida.")
    if not request.is_json:
        logger.warning("Login falhou: Requisição não é JSON.")
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        logger.warning("Login falhou: Usuário ou senha ausentes.")
        return jsonify({"error": "Username and password are required"}), 400

    try:
        auth_service = _get_auth_service()
        token, user_data = auth_service.login(username, password)
        logger.info(f"Usuário '{username}' logado com sucesso.")
        return jsonify({
            "message": "Login successful",
            "token": token,
            "user": user_data
        }), 200
    except AuthenticationError as e:
        logger.warning(f"Login falhou para '{username}': {e}")
        return jsonify({"error": str(e)}), 401
    except ApiError as e:
         logger.error(f"Erro de API durante login para '{username}': {e.message}", exc_info=True)
         return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Erro inesperado durante login para '{username}': {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred during login."}), 500


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """
    Endpoint for user logout. Clears the session token.
    ---
    tags: [Authentication]
    security:
      - bearerAuth: []
    responses:
      200:
        description: Logout successful
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Logout successful"
      401:
        description: Unauthorized (not logged in)
      500:
        description: Internal server error
    """
    logger.info(f"Requisição de logout recebida para usuário: {getattr(request, 'current_user', 'Desconhecido')}")
    try:
        auth_service = _get_auth_service()
        auth_service.logout()
        return jsonify({"message": "Logout successful"}), 200
    except Exception as e:
        logger.error(f"Erro durante logout: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred during logout."}), 500


@auth_bp.route('/verify', methods=['GET'])
@login_required
def verify_token():
    """
    Endpoint to verify the current user's token (passed via header or session).
    Returns current user information if the token is valid.
    Implicitly tested by the @login_required decorator.
    ---
    tags: [Authentication]
    security:
      - bearerAuth: []
    responses:
      200:
        description: Token is valid
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: "Token is valid"
                user:
                  type: object
                  example: {"id": 1, "username": "testuser", ...}
      401:
        description: Unauthorized (invalid or expired token)
      500:
        description: Internal server error
    """
    try:
        user = request.current_user
        logger.info(f"Token verificado para usuário: {user.username} (ID: {user.id})")
        user_data = user.to_dict(include_hash=False)
        return jsonify({
            "message": "Token is valid",
            "user": user_data
        }), 200
    except AttributeError:
         logger.error("request.current_user não definido após @login_required passar!")
         return jsonify({"error": "Internal server error during token verification."}), 500
    except Exception as e:
         logger.error(f"Erro inesperado durante verificação de token: {e}", exc_info=True)
         return jsonify({"error": "An internal server error occurred during verification."}), 500