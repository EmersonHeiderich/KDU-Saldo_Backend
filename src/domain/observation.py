# src/domain/observation.py
# Defines the data model for Product Observations stored locally.

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from src.utils.logger import logger

@dataclass
class Observation:
    """
    Represents a product observation stored in the local database. Mutable.
    """
    id: Optional[int] = None
    reference_code: str = ""
    observation_text: str = "" # Renamed from 'observation' for clarity
    user: str = ""
    timestamp: Optional[datetime] = field(default_factory=datetime.now)
    resolved: bool = False
    resolved_user: Optional[str] = None
    resolved_timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Observation object to a dictionary, handling datetimes."""
        data = self.__dict__.copy()
        # Convert datetime objects to ISO format strings for JSON serialization
        if isinstance(self.timestamp, datetime):
            data['timestamp'] = self.timestamp.isoformat()
        if isinstance(self.resolved_timestamp, datetime):
            data['resolved_timestamp'] = self.resolved_timestamp.isoformat()
        # Add formatted timestamps for display if needed (optional)
        # data['timestamp_formatted'] = self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None
        # data['resolved_timestamp_formatted'] = self.resolved_timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.resolved_timestamp else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional['Observation']:
        """Creates an Observation object from a dictionary (e.g., from DB)."""
        if not isinstance(data, dict):
            logger.warning(f"Invalid data type for Observation.from_dict: {type(data)}")
            return None

        # Convert ISO timestamp strings back to datetime objects
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except (ValueError, TypeError):
                logger.warning(f"Invalid format for timestamp: {timestamp}. Setting to None.")
                timestamp = None
        elif timestamp is not None and not isinstance(timestamp, datetime):
             logger.warning(f"Unexpected type for timestamp: {type(timestamp)}. Setting to None.")
             timestamp = None


        resolved_timestamp = data.get('resolved_timestamp')
        if isinstance(resolved_timestamp, str):
            try:
                resolved_timestamp = datetime.fromisoformat(resolved_timestamp)
            except (ValueError, TypeError):
                logger.warning(f"Invalid format for resolved_timestamp: {resolved_timestamp}. Setting to None.")
                resolved_timestamp = None
        elif resolved_timestamp is not None and not isinstance(resolved_timestamp, datetime):
             logger.warning(f"Unexpected type for resolved_timestamp: {type(resolved_timestamp)}. Setting to None.")
             resolved_timestamp = None


        try:
            return cls(
                id=data.get('id'),
                reference_code=str(data.get('reference_code', '')),
                observation_text=str(data.get('observation') or data.get('observation_text', '')), # Handle old/new name
                user=str(data.get('user', '')),
                timestamp=timestamp,
                resolved=bool(data.get('resolved', False)),
                resolved_user=data.get('resolved_user'),
                resolved_timestamp=resolved_timestamp
            )
        except Exception as e:
            logger.error(f"Error creating Observation from dict: {e}. Data: {data}")
            return None