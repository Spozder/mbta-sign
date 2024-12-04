import requests
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from .base import TransitSystem, TransitPrediction, TransitType

class BayWheelsTransit(TransitSystem):
    """Bay Wheels (Lyft Bike Share) implementation using GBFS feed"""

    def __init__(self):
        self.base_url = "https://gbfs.baywheels.com/gbfs/en"
        self.system_info = self._get_system_info()

    def _get_system_info(self) -> Dict:
        """Get system information including feed URLs"""
        response = requests.get(f"{self.base_url}/gbfs.json")
        data = response.json()
        feeds = {}
        for feed in data['data']['en']['feeds']:
            feeds[feed['name']] = feed['url']
        return feeds

    def get_predictions(self, stop_id: str, direction_id: Optional[str] = None) -> List[TransitPrediction]:
        """
        For bike share, we'll return the current bike/dock availability as "predictions"
        The arrival_time will be set to now since it represents current availability
        """
        # Get station information
        station_info_response = requests.get(self.system_info['station_information'])
        station_status_response = requests.get(self.system_info['station_status'])

        station_info = station_info_response.json()['data']['stations']
        station_status = station_status_response.json()['data']['stations']

        # Find matching station
        station_dict = {station['station_id']: station for station in station_info}
        status_dict = {station['station_id']: station for station in station_status}

        if stop_id not in station_dict or stop_id not in status_dict:
            return []

        info = station_dict[stop_id]
        status = status_dict[stop_id]

        now = datetime.now()
        predictions = []

        # Create "prediction" for available bikes
        if status['num_bikes_available'] > 0:
            predictions.append(TransitPrediction(
                arrival_time=now,
                route_id='bikes',
                route_name='Bay Wheels',
                destination=f"{status['num_bikes_available']} bikes available",
                status=f"at {info['name']}",
                transit_type=TransitType.BIKESHARE
            ))

        # Create "prediction" for available docks
        if status['num_docks_available'] > 0:
            predictions.append(TransitPrediction(
                arrival_time=now + timedelta(seconds=1),  # Slightly later to maintain order
                route_id='docks',
                route_name='Bay Wheels',
                destination=f"{status['num_docks_available']} docks available",
                status=f"at {info['name']}",
                transit_type=TransitType.BIKESHARE
            ))

        return predictions

    def get_stop_info(self, stop_id: str) -> Dict[str, Any]:
        response = requests.get(self.system_info['station_information'])
        stations = response.json()['data']['stations']
        for station in stations:
            if station['station_id'] == stop_id:
                return station
        return {}

    def get_service_alerts(self) -> List[str]:
        # GBFS doesn't have a standard alerts feed
        # Could potentially check system information for rental/return unavailability
        return []

    @property
    def name(self) -> str:
        return "Bay Wheels"

    @property
    def supported_transit_types(self) -> List[TransitType]:
        return [TransitType.BIKESHARE]
