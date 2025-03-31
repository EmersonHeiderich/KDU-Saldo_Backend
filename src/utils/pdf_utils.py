# src/utils/pdf_utils.py
# Utility functions for handling PDF data, like decoding Base64.

import base64
import binascii # For catching specific decode errors
from .logger import logger

def decode_base64_to_bytes(base64_string: str) -> bytes:
    """
    Decodes a Base64 encoded string into bytes.

    Args:
        base64_string: The Base64 encoded string.

    Returns:
        The decoded bytes.

    Raises:
        ValueError: If the input string is empty.
        TypeError: If the input is not a string.
        binascii.Error: If the Base64 string is invalid/corrupt.
    """
    if not base64_string:
        raise ValueError("Input Base64 string cannot be empty.")
    if not isinstance(base64_string, str):
        raise TypeError("Input must be a string.")

    try:
        # Standard Base64 decoding
        decoded_bytes = base64.b64decode(base64_string, validate=True)
        logger.debug(f"Successfully decoded Base64 string (length: {len(base64_string)}) to bytes (length: {len(decoded_bytes)}).")
        return decoded_bytes
    except binascii.Error as e:
        logger.error(f"Failed to decode Base64 string: {e}", exc_info=True)
        # Re-raise the specific error for the caller to handle
        raise ValueError(f"Invalid Base64 string provided: {e}") from e
    except Exception as e:
        # Catch any other unexpected errors during decoding
        logger.error(f"Unexpected error during Base64 decoding: {e}", exc_info=True)
        raise RuntimeError("An unexpected error occurred during Base64 decoding.") from e

# Make sure to import it in __init__.py for utils if needed elsewhere easily