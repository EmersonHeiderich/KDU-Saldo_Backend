# src/utils/pdf_utils.py
import base64
import binascii
from .logger import logger

def decode_base64_to_bytes(base64_string: str) -> bytes:
    """
    Decodifica uma string Base64 em bytes.

    Args:
        base64_string: A string codificada em Base64.

    Returns:
        Os bytes decodificados.

    Raises:
        ValueError: Se a string de entrada estiver vazia.
        TypeError: Se a entrada não for uma string.
        binascii.Error: Se a string Base64 for inválida ou corrompida.
    """
    if not base64_string:
        raise ValueError("A string Base64 de entrada não pode ser vazia.")
    if not isinstance(base64_string, str):
        raise TypeError("A entrada deve ser uma string.")

    try:
        decoded_bytes = base64.b64decode(base64_string, validate=True)
        logger.debug(f"Base64 decodificado com sucesso (tamanho: {len(base64_string)}) para bytes (tamanho: {len(decoded_bytes)}).")
        return decoded_bytes
    except binascii.Error as e:
        logger.error(f"Falha ao decodificar a string Base64: {e}", exc_info=True)
        raise ValueError(f"String Base64 inválida fornecida: {e}") from e
    except Exception as e:
        logger.error(f"Erro inesperado durante a decodificação Base64: {e}", exc_info=True)
        raise RuntimeError("Ocorreu um erro inesperado durante a decodificação Base64.") from e
