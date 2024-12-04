from typing import List, Dict, Any

# Configuration for different transit systems
TRANSIT_CONFIG = {
    # BART Configuration
    # "bart": {
    #     "stops": [
    #         # Example stops - replace with your actual nearby stops
    #         {"id": "16TH", "name": "16th St. Mission", "direction_id": None},
    #         {"id": "24TH", "name": "24th St. Mission", "direction_id": None},
    #     ],
    #     "api_key": None  # Add your BART API key here if you have one
    # },

    # Muni Configuration
    "muni": {
        "stops": [
            # Example stops - replace with your actual nearby stops
            {"id": "14422", "name": "24 S @ Geary"},
            {"id": "14294", "name": "38 E @ Divisadero"},
        ],
        "api_key": ""
    },

    # Bay Wheels Configuration
    "baywheels": {
        "stops": [
            # Example stops - replace with actual nearby bike stations
            {"id": "3144f47a-86f7-40f6-9ff0-5c8120babf6a", "name": "O'Farrell St @ Divis"},
        ]
    }
}

# Display configuration
DISPLAY_CONFIG = {
    "scroll_interval": 5,  # seconds between switching displays
    "update_interval": 30,  # seconds between API updates
    "max_predictions": 2,   # maximum number of predictions to show per stop
    "timezone": "America/Los_Angeles",
}
