from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pytz
from redis import Redis

from transit.base import TransitSystem, TransitPrediction, TransitType
from transit.bart import BARTTransit
from transit.muni import MuniTransit
from transit.baywheels import BayWheelsTransit
from config import TRANSIT_CONFIG, DISPLAY_CONFIG

class TransitManager:
    """Manages multiple transit systems and their predictions"""

    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.systems: Dict[str, TransitSystem] = {}
        self.current_stop_index = 0
        self.timezone = pytz.timezone(DISPLAY_CONFIG['timezone'])

        # Initialize transit systems
        if 'bart' in TRANSIT_CONFIG:
            self.systems['bart'] = BARTTransit(api_key=TRANSIT_CONFIG['bart'].get('api_key'))

        if 'muni' in TRANSIT_CONFIG:
            self.systems['muni'] = MuniTransit(api_key=TRANSIT_CONFIG['muni'].get('api_key'))

        if 'baywheels' in TRANSIT_CONFIG:
            self.systems['baywheels'] = BayWheelsTransit()

        # Create flat list of all stops
        self.all_stops = []
        for system_name, config in TRANSIT_CONFIG.items():
            if system_name in self.systems:
                for stop in config['stops']:
                    self.all_stops.append({
                        'system': system_name,
                        'id': stop['id'],
                        'name': stop['name'],
                        'direction_id': stop.get('direction_id')
                    })

    def get_predictions_for_stop(self, stop_data: dict) -> List[TransitPrediction]:
        """Get predictions for a specific stop"""
        system = self.systems.get(stop_data['system'])
        if not system:
            return []

        return system.get_predictions(
            stop_id=stop_data['id'],
            direction_id=stop_data.get('direction_id')
        )

    def get_current_predictions(self) -> Tuple[List[TransitPrediction], str, str]:
        """Get predictions for the current stop and advance to next stop"""
        if not self.all_stops:
            return [], "No transit", "stops configured"

        current_stop = self.all_stops[self.current_stop_index]
        predictions = self.get_predictions_for_stop(current_stop)

        # Advance to next stop
        self.current_stop_index = (self.current_stop_index + 1) % len(self.all_stops)

        if not predictions:
            return [], f"No predictions", f"for {current_stop['name']}"

        # Format predictions for display
        now = datetime.now(self.timezone)
        formatted_preds = []

        for pred in predictions[:DISPLAY_CONFIG['max_predictions']]:
            # Convert to local time
            arrival_time = pred.arrival_time.astimezone(self.timezone)

            # Calculate minutes until arrival
            minutes = int((arrival_time - now).total_seconds() / 60)

            if minutes <= 0:
                time_str = "Arriving"
            elif minutes == 1:
                time_str = "1 min"
            else:
                time_str = f"{minutes} mins"

            formatted_preds.append({
                'route': pred.route_name,
                'time': time_str,
                'destination': pred.destination,
                'transit_type': pred.transit_type
            })

        if len(formatted_preds) >= 2:
            line1 = f"{formatted_preds[0]['route']}: {formatted_preds[0]['time']}"
            line2 = f"{formatted_preds[1]['route']}: {formatted_preds[1]['time']}"
        elif len(formatted_preds) == 1:
            line1 = f"{formatted_preds[0]['route']}: {formatted_preds[0]['time']}"
            line2 = formatted_preds[0]['destination']
        else:
            line1 = "No predictions"
            line2 = f"for {current_stop['name']}"

        return predictions, line1, line2

    def get_service_alerts(self) -> List[str]:
        """Get service alerts from all transit systems"""
        alerts = []
        for system in self.systems.values():
            alerts.extend(system.get_service_alerts())
        return alerts
