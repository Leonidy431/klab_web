"""
BlueOS Integration Module.

This module provides integration with Blue Robotics BlueOS
for ROV control, telemetry, and video streaming.

BlueOS API Documentation: https://docs.bluerobotics.com/blueos/
"""

from app.modules.blueos.client import BlueOSClient
from app.modules.blueos.mavlink import MAVLinkConnection
from app.modules.blueos.telemetry import TelemetryService
from app.modules.blueos.video import VideoStreamManager

__all__ = [
    "BlueOSClient",
    "MAVLinkConnection",
    "TelemetryService",
    "VideoStreamManager",
]
