# src/erp_integration/erp_auth_service.py
# Handles authentication with the TOTVS ERP API to obtain Bearer tokens.

import time
import requests
from typing import Optional, Dict, Any
from threading import Lock
from src.config import config # Import app configuration
from src.utils.logger import logger
from src.api.errors import ErpIntegrationError # Use custom error

class ErpAuthService:
    """
    Manages authentication with the ERP API (TOTVS) using OAuth Password Grant.
    Handles token acquisition, caching, expiration, and renewal.
    Designed as a thread-safe singleton.
    """
    _instance = None
    _lock = Lock()
    _token_lock = Lock() # Separate lock specifically for token refresh logic

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ErpAuthService, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initializes the ErpAuthService (called only once due to Singleton)."""
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                 return

            self._access_token: Optional[str] = None
            self._expires_at: float = 0 # Store expiration time as timestamp
            # Construct full URLs from config
            self.auth_url = f"{config.API_BASE_URL.rstrip('/')}{config.TOKEN_ENDPOINT}"
            self.client_id = config.CLIENT_ID
            self.client_secret = config.CLIENT_SECRET
            self.username = config.API_USERNAME
            self.password = config.API_PASSWORD
            self.grant_type = config.GRANT_TYPE

            if not self.username or not self.password:
                 logger.warning("ERP API username or password not configured. Authentication will likely fail.")
            if not self.client_id: # Client secret might be optional depending on grant type
                 logger.warning("ERP API client_id not configured.")

            self._initialized = True
            logger.info(f"ErpAuthService initialized for URL: {self.auth_url}")

    def get_token(self) -> str:
        """
        Returns a valid Bearer token for accessing the ERP API.
        Handles token expiration and renewal automatically. Thread-safe.

        Returns:
            A valid access token string.

        Raises:
            ErpIntegrationError: If unable to obtain or refresh the token.
        """
        with self._token_lock: # Ensure only one thread refreshes the token at a time
            # Check expiry with a safety margin (e.g., 60 seconds)
            # time.time() is generally preferred over time.monotonic() for expiration checks
            # as it relates to wall-clock time, which 'exp' usually represents.
            safety_margin = 60
            if not self._access_token or time.time() >= (self._expires_at - safety_margin):
                logger.info("ERP token missing or expired/near expiry. Refreshing...")
                try:
                    self._refresh_token()
                except Exception as e:
                    # Log the error from _refresh_token and re-raise specific type
                    logger.critical(f"Failed to refresh ERP token: {e}", exc_info=True)
                    raise ErpIntegrationError("Failed to obtain/refresh ERP API token.") from e

            if not self._access_token:
                 # This should not happen if _refresh_token succeeds, but handle defensively
                 logger.error("Access token is still None after refresh attempt.")
                 raise ErpIntegrationError("Failed to obtain ERP API token after refresh.")

            return self._access_token

    def invalidate_token(self):
        """Forces the token to be refreshed on the next call to get_token()."""
        with self._token_lock:
            logger.info("Invalidating stored ERP token.")
            self._access_token = None
            self._expires_at = 0

    def _refresh_token(self):
        """
        Internal method to request a new token from the ERP's authorization endpoint.
        This method is called internally by get_token() when needed.
        Assumes _token_lock is held by the caller.
        """
        auth_data = {
            'username': self.username,
            'password': self.password,
            'client_id': self.client_id,
            'grant_type': self.grant_type
        }
        # Add client_secret only if it's provided (some grant types might not require it)
        if self.client_secret:
            auth_data['client_secret'] = self.client_secret

        logger.debug(f"Requesting new ERP token from {self.auth_url}")
        try:
            response = requests.post(
                self.auth_url,
                data=auth_data, # Use data for application/x-www-form-urlencoded
                timeout=15 # Increased timeout for auth requests
            )
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            token_data = response.json()

            if 'access_token' not in token_data:
                 logger.error(f"ERP Auth response missing 'access_token'. Response: {token_data}")
                 raise ErpIntegrationError("Received invalid token response from ERP.")

            self._access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600) # Default to 1 hour if missing
            try:
                 # Calculate expiration time based on 'expires_in'
                 self._expires_at = time.time() + int(expires_in)
            except (ValueError, TypeError):
                 logger.warning(f"Invalid 'expires_in' value received: {expires_in}. Defaulting to 1 hour.")
                 self._expires_at = time.time() + 3600

            logger.info(f"Successfully refreshed ERP token. Expires in approx {expires_in} seconds.")
            # Log partial token for debugging if needed, but be careful
            # logger.debug(f"New token: {self._access_token[:10]}...{self._access_token[-10:]}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during ERP token refresh request to {self.auth_url}: {e}", exc_info=True)
            # Invalidate potentially stale token on network error
            self._access_token = None
            self._expires_at = 0
            raise ErpIntegrationError(f"Network error contacting ERP auth server: {e}") from e
        except Exception as e:
             logger.error(f"Unexpected error during ERP token refresh: {e}", exc_info=True)
             # Invalidate potentially stale token on any error
             self._access_token = None
             self._expires_at = 0
             # Include response text in error if available
             err_msg = f"Unexpected error refreshing ERP token: {e}"
             if 'response' in locals() and hasattr(response, 'text'):
                  err_msg += f" | Response: {response.text[:500]}" # Limit response length
             raise ErpIntegrationError(err_msg) from e
