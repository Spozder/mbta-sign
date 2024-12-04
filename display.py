import time
import argparse
from datetime import datetime
import logging
from typing import Optional
from enum import Enum
import pytz
from redis import Redis
from abc import ABC, abstractmethod
try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
    MATRIX_AVAILABLE = True
except ImportError:
    MATRIX_AVAILABLE = False

from transit.base import TransitType
from transit_manager import TransitManager
from config import DISPLAY_CONFIG

# Redis channel keys
UPDATE_KEY = "update"
CUSTOM_TEXT_KEY = "custom"
DEBUG = False

class Color:
    """Color definitions that work for both RGB matrix and terminal"""

    # ANSI escape codes for terminal colors
    TERMINAL_COLORS = {
        'RED': '\033[91m',
        'BLUE': '\033[94m',
        'GREEN': '\033[92m',
        'ORANGE': '\033[93m',
        'PURPLE': '\033[95m',
        'RESET': '\033[0m'
    }

    def __init__(self, r: int, g: int, b: int, name: str):
        self.r = r
        self.g = g
        self.b = b
        self.name = name

    def to_matrix_color(self):
        """Convert to RGB Matrix color if available"""
        if MATRIX_AVAILABLE:
            return graphics.Color(self.r, self.g, self.b)
        return None

    def to_terminal_color(self):
        """Convert to terminal color code"""
        return self.TERMINAL_COLORS.get(self.name, self.TERMINAL_COLORS['RESET'])

class DisplayColors:
    """Color definitions for different transit types"""
    SUBWAY = Color(200, 0, 0, 'RED')
    BUS = Color(0, 128, 255, 'BLUE')
    RAIL = Color(237, 139, 0, 'ORANGE')
    BIKESHARE = Color(0, 204, 0, 'GREEN')
    DEFAULT = Color(102, 51, 153, 'PURPLE')

class DisplayInterface(ABC):
    """Abstract interface for display implementations"""

    @abstractmethod
    def set_text(self, line1: str, line2: str, color: Color):
        """Update the display with new text"""
        pass

    @abstractmethod
    def clear(self):
        """Clear the display"""
        pass

class MatrixDisplay(DisplayInterface):
    """Physical RGB Matrix display implementation"""

    def __init__(self):
        if not MATRIX_AVAILABLE:
            raise ImportError("RGB Matrix library not available")

        options = RGBMatrixOptions()
        options.rows = 16
        options.cols = 96
        options.brightness = 35
        options.hardware_mapping = "adafruit-hat"

        self.matrix = RGBMatrix(options=options)
        self.canvas = self.matrix.CreateFrameCanvas()
        self.font = graphics.Font()
        self.font.LoadFont("/home/pi/mbta-sign/rpi-rgb-led-matrix/fonts/5x7.bdf")

    def set_text(self, line1: str, line2: str, color: Color):
        self.canvas.Clear()
        matrix_color = color.to_matrix_color()
        graphics.DrawText(self.canvas, self.font, 1, 7, matrix_color, line1[:18])
        graphics.DrawText(self.canvas, self.font, 1, 15, matrix_color, line2[:18])
        self.canvas = self.matrix.SwapOnVSync(self.canvas)

    def clear(self):
        self.matrix.Clear()

class TerminalDisplay(DisplayInterface):
    """Terminal-based display simulation"""

    def __init__(self):
        self.width = 90  # Match the character limit of the LED matrix

    def set_text(self, line1: str, line2: str, color: Color):
        # Clear previous lines (move cursor up 4 lines and clear)
        print('\033[4A\033[J', end='')

        # Draw box around text
        terminal_color = color.to_terminal_color()
        reset_color = Color.TERMINAL_COLORS['RESET']

        print('┌' + '─' * (self.width + 2) + '┐')
        print(f'│ {terminal_color}{line1[:self.width]:<{self.width}}{reset_color} │')
        print(f'│ {terminal_color}{line2[:self.width]:<{self.width}}{reset_color} │')
        print('└' + '─' * (self.width + 2) + '┘')

    def clear(self):
        print('\033[2J\033[H', end='')  # Clear screen and move cursor to top

class TransitDisplay:
    """Handles the display for transit predictions"""

    def __init__(self, redis_client: Redis, simulation_mode: bool = False):
        # Initialize display
        self.simulation_mode = simulation_mode
        try:
            self.display = TerminalDisplay() if simulation_mode else MatrixDisplay()
        except ImportError:
            print("RGB Matrix library not available, falling back to terminal display")
            self.display = TerminalDisplay()
            self.simulation_mode = True

        # Initialize Redis and transit manager
        self.redis = redis_client
        self.transit_manager = TransitManager(redis_client)

        # Subscribe to Redis channels
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(UPDATE_KEY)
        self.pubsub.subscribe(CUSTOM_TEXT_KEY)

        # Initialize display state
        self.line1 = ""
        self.line2 = ""
        self.current_color = DisplayColors.DEFAULT

        self.set_text("Now booting up", "Please hold...", DisplayColors.DEFAULT)
        self.last_update = datetime.now(pytz.timezone(DISPLAY_CONFIG['timezone']))

        # Print initial newlines for terminal display
        if self.simulation_mode:
            print('\n' * 4)

    def get_color_for_transit_type(self, transit_type: Optional[TransitType] = None) -> Color:
        """Get the display color for a transit type"""
        if not transit_type:
            return DisplayColors.DEFAULT

        color_map = {
            TransitType.SUBWAY: DisplayColors.SUBWAY,
            TransitType.BUS: DisplayColors.BUS,
            TransitType.RAIL: DisplayColors.RAIL,
            TransitType.BIKESHARE: DisplayColors.BIKESHARE
        }
        return color_map.get(transit_type, DisplayColors.DEFAULT)

    def set_text(self, line1: str, line2: str, color: Color):
        """Update the display with new text"""
        if DEBUG:
            print(f"Setting Text: {line1}, {line2}")

        if line1 != self.line1 or line2 != self.line2:
            self.display.set_text(line1, line2, color)
            self.line1 = line1
            self.line2 = line2
            self.current_color = color

    def handle_custom_text(self, message: str):
        """Handle custom text messages from Redis"""
        try:
            text = message.split('|')
            if len(text) >= 2:
                self.set_text(text[0], text[1], DisplayColors.DEFAULT)
            else:
                self.set_text(text[0], "", DisplayColors.DEFAULT)
        except Exception as e:
            logging.error(f"Error handling custom text: {e}")

    def update_display(self):
        """Update the display with new predictions"""
        now = datetime.now(pytz.timezone(DISPLAY_CONFIG['timezone']))

        # Check if it's time to update
        if (now - self.last_update).total_seconds() < DISPLAY_CONFIG['update_interval']:
            return

        predictions, line1, line2 = self.transit_manager.get_current_predictions()

        # Get color based on transit type of first prediction
        color = self.get_color_for_transit_type(
            predictions[0].transit_type if predictions else None
        )

        self.set_text(line1, line2, color)
        self.last_update = now

    def run(self):
        """Main display loop"""
        try:
            while True:
                # Check for custom messages
                message = self.pubsub.get_message(timeout=1)
                if message and message['type'] == 'message':
                    if message['channel'] == CUSTOM_TEXT_KEY:
                        self.handle_custom_text(message['data'])
                    elif message['channel'] == UPDATE_KEY:
                        self.update_display()

                # Regular display updates
                self.update_display()

                time.sleep(0.1)  # Prevent CPU overload

        except KeyboardInterrupt:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        self.pubsub.unsubscribe()
        self.display.clear()


if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Transit Display')
    parser.add_argument('--simulate', action='store_true',
                      help='Run in terminal simulation mode instead of using RGB matrix')
    args = parser.parse_args()

    # Initialize Redis connection
    redis_client = Redis(
        host="127.0.0.1",
        port=6379,
        charset="utf-8",
        decode_responses=True
    )

    # Create and run display
    display = TransitDisplay(redis_client, simulation_mode=args.simulate)
    display.run()
