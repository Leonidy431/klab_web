"""
Telemetry Service Module.

Real-time telemetry aggregation and WebSocket broadcasting
for ROV monitoring dashboards.
"""

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from loguru import logger

from app.modules.blueos.client import BlueOSClient, get_blueos_client
from app.modules.blueos.mavlink import MAVLinkConnection, VehicleState


@dataclass
class TelemetryPacket:
    """Complete telemetry snapshot."""

    timestamp: str
    vehicle: dict[str, Any]
    system: dict[str, Any]
    sensors: dict[str, Any]
    cameras: list[dict[str, Any]]


class TelemetryService:
    """
    Aggregates telemetry from multiple sources.

    Combines:
    - MAVLink vehicle state (attitude, depth, battery)
    - BlueOS system metrics (CPU, RAM, disk)
    - Sensor data (Ping sonar, pressure)
    - Camera status

    Broadcasts via WebSocket for real-time UI updates.
    """

    def __init__(
        self,
        update_interval: float = 0.1,  # 10Hz
        broadcast_interval: float = 0.2,  # 5Hz
    ) -> None:
        """
        Initialize telemetry service.

        Args:
            update_interval: How often to poll telemetry (seconds)
            broadcast_interval: How often to broadcast to clients (seconds)
        """
        self.update_interval = update_interval
        self.broadcast_interval = broadcast_interval

        self._running = False
        self._update_task: asyncio.Task | None = None
        self._broadcast_task: asyncio.Task | None = None

        self._clients: set[Any] = set()  # WebSocket clients
        self._latest_packet: TelemetryPacket | None = None

        self._blueos_client: BlueOSClient | None = None
        self._mavlink: MAVLinkConnection | None = None

    async def start(
        self,
        blueos_client: BlueOSClient | None = None,
        mavlink: MAVLinkConnection | None = None,
    ) -> None:
        """
        Start telemetry service.

        Args:
            blueos_client: Optional BlueOS client instance
            mavlink: Optional MAVLink connection instance
        """
        self._blueos_client = blueos_client or await get_blueos_client()
        self._mavlink = mavlink

        self._running = True
        self._update_task = asyncio.create_task(self._update_loop())
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())

        logger.info("Telemetry service started")

    async def stop(self) -> None:
        """Stop telemetry service."""
        self._running = False

        if self._update_task:
            self._update_task.cancel()
        if self._broadcast_task:
            self._broadcast_task.cancel()

        logger.info("Telemetry service stopped")

    def add_client(self, websocket: Any) -> None:
        """Register WebSocket client for telemetry updates."""
        self._clients.add(websocket)
        logger.debug(f"Telemetry client added. Total: {len(self._clients)}")

    def remove_client(self, websocket: Any) -> None:
        """Unregister WebSocket client."""
        self._clients.discard(websocket)
        logger.debug(f"Telemetry client removed. Total: {len(self._clients)}")

    async def _update_loop(self) -> None:
        """Continuously update telemetry data."""
        while self._running:
            try:
                packet = await self._collect_telemetry()
                self._latest_packet = packet
            except Exception as e:
                logger.error(f"Telemetry update error: {e}")

            await asyncio.sleep(self.update_interval)

    async def _broadcast_loop(self) -> None:
        """Broadcast telemetry to all connected clients."""
        while self._running:
            if self._latest_packet and self._clients:
                message = json.dumps(asdict(self._latest_packet))

                # Send to all clients, remove dead connections
                dead_clients = set()
                for client in self._clients:
                    try:
                        await client.send_text(message)
                    except Exception:
                        dead_clients.add(client)

                self._clients -= dead_clients

            await asyncio.sleep(self.broadcast_interval)

    async def _collect_telemetry(self) -> TelemetryPacket:
        """Collect telemetry from all sources."""
        timestamp = datetime.utcnow().isoformat()

        # Vehicle state from MAVLink
        vehicle_data: dict[str, Any] = {}
        if self._mavlink:
            state = self._mavlink.state
            vehicle_data = {
                "armed": state.armed,
                "mode": state.mode.name if hasattr(state.mode, "name") else str(state.mode),
                "heading": round(state.heading, 1),
                "depth": round(state.depth, 2),
                "attitude": {
                    "roll": round(state.roll, 3),
                    "pitch": round(state.pitch, 3),
                    "yaw": round(state.yaw, 3),
                },
                "battery": {
                    "voltage": round(state.battery_voltage, 2),
                    "remaining": state.battery_remaining,
                },
            }
        else:
            # Fallback to BlueOS REST API
            try:
                attitude = await self._blueos_client.get_attitude()
                depth_data = await self._blueos_client.get_depth()
                battery = await self._blueos_client.get_battery_status()

                vehicle_data = {
                    "armed": False,
                    "mode": "UNKNOWN",
                    "heading": 0,
                    "depth": 0,
                    "attitude": attitude.get("message", {}),
                    "battery": battery.get("message", {}),
                }
            except Exception as e:
                logger.warning(f"Failed to get vehicle data: {e}")

        # System metrics from BlueOS
        system_data: dict[str, Any] = {}
        try:
            cpu = await self._blueos_client.get_cpu_info()
            memory = await self._blueos_client.get_memory_info()
            disk = await self._blueos_client.get_disk_info()

            system_data = {
                "cpu": cpu,
                "memory": memory,
                "disk": disk,
            }
        except Exception as e:
            logger.warning(f"Failed to get system data: {e}")

        # Sensor data
        sensor_data: dict[str, Any] = {}
        try:
            ping_devices = await self._blueos_client.get_ping_devices()
            if ping_devices:
                distance = await self._blueos_client.get_ping_distance()
                sensor_data["ping_sonar"] = {
                    "distance_mm": distance.get("distance", 0),
                    "confidence": distance.get("confidence", 0),
                }
        except Exception:
            pass  # Ping sonar may not be installed

        # Camera status
        cameras: list[dict[str, Any]] = []
        try:
            cameras = await self._blueos_client.get_cameras()
        except Exception:
            pass

        return TelemetryPacket(
            timestamp=timestamp,
            vehicle=vehicle_data,
            system=system_data,
            sensors=sensor_data,
            cameras=cameras,
        )

    async def get_latest(self) -> TelemetryPacket | None:
        """Get latest telemetry packet."""
        return self._latest_packet

    async def get_snapshot(self) -> dict[str, Any]:
        """Get current telemetry as dictionary."""
        if self._latest_packet:
            return asdict(self._latest_packet)
        return {}


# Singleton instance
_telemetry_service: TelemetryService | None = None


async def get_telemetry_service() -> TelemetryService:
    """Get or create telemetry service singleton."""
    global _telemetry_service
    if _telemetry_service is None:
        _telemetry_service = TelemetryService()
    return _telemetry_service
