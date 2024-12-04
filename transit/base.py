from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

class TransitType(Enum):
    SUBWAY = "subway"
    BUS = "bus"
    RAIL = "rail"
    BIKESHARE = "bikeshare"

@dataclass
class TransitPrediction:
    arrival_time: datetime
    route_id: str
    route_name: str
    destination: str
    vehicle_id: Optional[str] = None
    status: Optional[str] = None
    transit_type: TransitType = TransitType.SUBWAY

class TransitSystem(ABC):
    """Base class for all transit systems"""

    @abstractmethod
    def get_predictions(self, stop_id: str, direction_id: Optional[str] = None) -> List[TransitPrediction]:
        """Get predictions for a specific stop"""
        pass

    @abstractmethod
    def get_stop_info(self, stop_id: str) -> Dict[str, Any]:
        """Get information about a specific stop"""
        pass

    @abstractmethod
    def get_service_alerts(self) -> List[str]:
        """Get current service alerts"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the transit system"""
        pass

    @property
    @abstractmethod
    def supported_transit_types(self) -> List[TransitType]:
        """List of supported transit types"""
        pass
