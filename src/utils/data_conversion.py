# src/utils/data_conversion.py
from datetime import datetime, date, time, timezone
from typing import Any, Optional, Union
from .logger import logger
import sys

def safe_int(value: Any) -> Optional[int]:
    """Converte um valor para inteiro de forma segura, retornando None em caso de falha."""
    if value is None:
        return None
    try:
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            try:
                float_val = float(value)
                if float_val.is_integer():
                    return int(float_val)
            except ValueError:
                pass 
        return int(value)
    except (ValueError, TypeError) as e:
        logger.debug(f"Não foi possível converter o valor '{value}' (tipo: {type(value)}) para inteiro: {e}")
        return None

def safe_float(value: Any) -> Optional[float]:
    """Converte um valor para float de forma segura, retornando None em caso de falha."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError) as e:
        logger.debug(f"Não foi possível converter o valor '{value}' (tipo: {type(value)}) para float: {e}")
        return None

def parse_optional_datetime(value: Optional[str]) -> Optional[datetime]:
    """Converte uma string ISO 8601 para um objeto datetime com fuso horário UTC, retornando None em caso de falha."""
    if not value or not isinstance(value, str):
        return None
    try:
        dt_str = value.replace('Z', '+00:00')
        formatos = [
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
        ]
        parsed_dt = None
        for fmt in formatos:
            try:
                parsed_dt = datetime.strptime(dt_str, fmt)
                break
            except ValueError:
                continue

        if parsed_dt is None:
            parsed_dt = datetime.fromisoformat(dt_str)

        if parsed_dt.tzinfo is None:
            parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
        else:
            parsed_dt = parsed_dt.astimezone(timezone.utc)

        return parsed_dt
    except (ValueError, TypeError) as e:
        logger.warning(f"Não foi possível converter '{value}' para datetime: {e}")
        return None

def parse_optional_date(value: Optional[str]) -> Optional[date]:
    """Converte uma string (YYYY-MM-DD) para um objeto date, retornando None em caso de falha."""
    if not value or not isinstance(value, str):
        return None
    try:
        date_str = value.split('T')[0]
        return date.fromisoformat(date_str)
    except (ValueError, TypeError) as e:
        logger.warning(f"Não foi possível converter '{value}' para date: {e}")
        return None

def parse_optional_time(value: Optional[str]) -> Optional[time]:
    """Converte uma string (HH:MM:SS ou HH:MM:SS.ffffff) para um objeto time, retornando None em caso de falha."""
    if not value or not isinstance(value, str):
        return None
    try:
        time_str = value.split('T')[-1].split('+')[0].split('-')[0].split('Z')[0]
        formatos = ["%H:%M:%S.%f", "%H:%M:%S"]
        parsed_time = None
        for fmt in formatos:
            try:
                dt_obj = datetime.strptime(time_str, fmt)
                parsed_time = dt_obj.time()
                break
            except ValueError:
                continue
        if parsed_time is None:
            raise ValueError("Formato de hora não reconhecido")
        return parsed_time
    except (ValueError, TypeError, IndexError) as e:
        logger.warning(f"Não foi possível converter '{value}' para time: {e}")
        return None
