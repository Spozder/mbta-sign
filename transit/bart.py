import requests
from datetime import datetime
from typing import List, Optional, Dict, Any
from .base import TransitSystem, TransitPrediction, TransitType

class BARTTransit(TransitSystem):
    """BART (Bay Area Rapid Transit) implementation"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.bart.gov/api/etd.aspx"

    def get_predictions(self, stop_id: str, direction_id: Optional[str] = None) -> List[TransitPrediction]:
        params = {
            'cmd': 'etd',
            'orig': stop_id,
            'key': self.api_key or 'MW9S-E7SL-26DU-VV8V',  # Default test key
            'json': 'y'
        }

        response = requests.get(self.base_url, params=params)
        data = response.json()

        predictions = []
        try:
            station_data = data['root']['station'][0]
            etds = station_data['etd']

            for etd in etds:
                destination = etd['destination']
                for estimate in etd['estimate']:
                    # Convert minutes to datetime
                    minutes = int(estimate['minutes'])
                    if minutes == 0:
                        continue  # Skip "Leaving" trains

                    arrival_time = datetime.now().replace(second=0, microsecond=0)
                    arrival_time = arrival_time.replace(minute=arrival_time.minute + minutes)

                    predictions.append(TransitPrediction(
                        arrival_time=arrival_time,
                        route_id=etd['abbreviation'],
                        route_name=f"BART {etd['abbreviation']}",
                        destination=destination,
                        status=estimate['length'] + " car train",
                        transit_type=TransitType.SUBWAY
                    ))
        except (KeyError, IndexError) as e:
            print(f"Error parsing BART response: {e}")

        return sorted(predictions, key=lambda x: x.arrival_time)[:2]  # Return next 2 arrivals

    def get_stop_info(self, stop_id: str) -> Dict[str, Any]:
        # BART station info API endpoint
        url = f"https://api.bart.gov/api/stn.aspx"
        params = {
            'cmd': 'stninfo',
            'orig': stop_id,
            'key': self.api_key or 'MW9S-E7SL-26DU-VV8V',
            'json': 'y'
        }

        response = requests.get(url, params=params)
        return response.json()['root']['stations'][0]

    def get_service_alerts(self) -> List[str]:
        url = "https://api.bart.gov/api/bsa.aspx"
        params = {
            'cmd': 'bsa',
            'key': self.api_key or 'MW9S-E7SL-26DU-VV8V',
            'json': 'y'
        }

        response = requests.get(url, params=params)
        alerts = []
        try:
            bsa = response.json()['root']['bsa']
            for alert in bsa:
                if alert['description'] != "No delays reported.":
                    alerts.append(alert['description'])
        except (KeyError, IndexError) as e:
            print(f"Error parsing BART alerts: {e}")

        return alerts

    @property
    def name(self) -> str:
        return "BART"

    @property
    def supported_transit_types(self) -> List[TransitType]:
        return [TransitType.SUBWAY, TransitType.RAIL]
