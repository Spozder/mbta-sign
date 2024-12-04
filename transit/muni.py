import requests
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import json
import logging
from .base import TransitSystem, TransitPrediction, TransitType

class MuniTransit(TransitSystem):
    """SF Muni implementation using official SFMTA/511.org API"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or "YOUR-511-API-KEY"  # Replace with your 511.org API key
        self.base_url = "https://api.511.org/transit"
        self.agency = "SF"  # SFMTA's agency code in 511.org

    def _parse_json_response(self, response: requests.Response) -> Dict:
        """Parse JSON response with better error handling"""
        try:
            # Use utf-8-sig encoding to handle UTF-8 BOM
            return json.loads(response.content.decode('utf-8-sig'))
        except json.JSONDecodeError as e:
            # Log the actual response content
            error_msg = (
                f"Failed to parse JSON response. Error: {str(e)}\n"
                f"Status code: {response.status_code}\n"
                f"Response content: {response.text[:1000]}"  # First 1000 chars to avoid huge logs
            )
            logging.error(error_msg)
            raise ValueError(error_msg) from e

    def get_predictions(self, stop_id: str, direction_id: Optional[str] = None) -> List[TransitPrediction]:
        # Get real-time predictions
        url = f"{self.base_url}/StopMonitoring"
        params = {
            'api_key': self.api_key,
            'agency': self.agency,
            'stopCode': stop_id,
            'format': 'json'
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raise exception for bad status codes
            data = self._parse_json_response(response)

            predictions = []
            deliveries = data.get('ServiceDelivery', {})
            stop_visit = deliveries.get('StopMonitoringDelivery', {}).get('MonitoredStopVisit', [])

            for visit in stop_visit:
                monitored_vehicle = visit.get('MonitoredVehicleJourney', {})

                # Get route information
                route_id = monitored_vehicle.get('LineRef', '').replace('SF:', '')
                route_name = monitored_vehicle.get('PublishedLineName', [route_id])[0]
                destination = monitored_vehicle.get('DestinationName', [''])[0]
                vehicle_id = monitored_vehicle.get('VehicleRef', '').replace('SF:', '')

                # Get arrival time
                call = monitored_vehicle.get('MonitoredCall', {})
                expected_arrival = call.get('ExpectedArrivalTime')

                if expected_arrival:
                    arrival_time = datetime.fromisoformat(expected_arrival.replace('Z', '+00:00'))

                    # Determine transit type based on route
                    transit_type = TransitType.BUS
                    if route_id in ['J', 'K', 'L', 'M', 'N', 'T']:
                        transit_type = TransitType.SUBWAY

                    predictions.append(TransitPrediction(
                        arrival_time=arrival_time,
                        route_id=route_id,
                        route_name=f"Muni {route_name}",
                        destination=destination,
                        vehicle_id=vehicle_id,
                        status=call.get('ArrivalProximityText'),
                        transit_type=transit_type
                    ))

        except requests.RequestException as e:
            logging.error(f"Error fetching Muni predictions: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logging.error(f"Response status: {e.response.status_code}")
                logging.error(f"Response content: {e.response.text[:1000]}")
        except Exception as e:
            logging.error(f"Error processing Muni predictions: {e}")

        return sorted(predictions, key=lambda x: x.arrival_time)[:2]  # Return next 2 arrivals

    def get_stop_info(self, stop_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/stops"
        params = {
            'api_key': self.api_key,
            'agency': self.agency,
            'format': 'json'
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = self._parse_json_response(response)

            stops = data.get('Contents', {}).get('dataObjects', {}).get('ScheduledStopPoint', [])
            for stop in stops:
                if stop.get('id') == f"SF:{stop_id}":
                    return stop
        except requests.RequestException as e:
            logging.error(f"Error fetching stop info: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logging.error(f"Response status: {e.response.status_code}")
                logging.error(f"Response content: {e.response.text[:1000]}")
        except Exception as e:
            logging.error(f"Error processing stop info: {e}")

        return {}

    def get_service_alerts(self) -> List[str]:
        url = f"{self.base_url}/servicealerts"
        params = {
            'api_key': self.api_key,
            'agency': self.agency,
            'format': 'json'
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = self._parse_json_response(response)

            alerts = []
            service_alerts = data.get('ServiceDelivery', {}).get('SituationExchangeDelivery', [{}])[0].get('Situations', {}).get('PtSituationElement', [])

            for alert in service_alerts:
                summary = alert.get('Summary', [{}])[0].get('value')
                if summary:
                    alerts.append(summary)
            return alerts
        except requests.RequestException as e:
            logging.error(f"Error fetching service alerts: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logging.error(f"Response status: {e.response.status_code}")
                logging.error(f"Response content: {e.response.text[:1000]}")
        except Exception as e:
            logging.error(f"Error processing service alerts: {e}")

        return []

    @property
    def name(self) -> str:
        return "Muni"

    @property
    def supported_transit_types(self) -> List[TransitType]:
        return [TransitType.SUBWAY, TransitType.BUS]
