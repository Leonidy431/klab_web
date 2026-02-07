"""
MAVLink Connection Module.

Direct MAVLink communication with ArduSub flight controller
for real-time control and telemetry.

Protocol: MAVLink 2.0
Vehicle Type: ArduSub (Submarine)
"""

import asyncio
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable

from loguru import logger
from pymavlink import mavutil

from app.core.config import settings


class FlightMode(IntEnum):
    """ArduSub flight modes."""

    STABILIZE = 0
    ACRO = 1
    ALT_HOLD = 2
    AUTO = 3
    GUIDED = 4
    CIRCLE = 7
    SURFACE = 9
    POSHOLD = 16
    MANUAL = 19


@dataclass
class VehicleState:
    """Current vehicle state snapshot."""

    armed: bool = False
    mode: FlightMode = FlightMode.MANUAL
    heading: float = 0.0
    depth: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    battery_voltage: float = 0.0
    battery_remaining: int = 0
    lights_level: int = 0


class MAVLinkConnection:
    """
    MAVLink connection manager for ArduSub ROV.

    Provides:
    - Connection management (UDP/TCP/Serial)
    - Message sending/receiving
    - Heartbeat monitoring
    - Command execution

    Usage:
        mav = MAVLinkConnection()
        await mav.connect()
        await mav.arm()
        await mav.set_mode(FlightMode.ALT_HOLD)
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        source_system: int = 255,
        source_component: int = 0,
    ) -> None:
        """
        Initialize MAVLink connection.

        Args:
            host: Vehicle IP address
            port: MAVLink UDP port
            source_system: GCS system ID
            source_component: GCS component ID
        """
        self.host = host or settings.blueos_host
        self.port = port or settings.blueos_mavlink_port
        self.source_system = source_system
        self.source_component = source_component

        self._connection: mavutil.mavlink_connection | None = None
        self._running = False
        self._receive_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None

        self.state = VehicleState()
        self._message_handlers: dict[str, list[Callable]] = {}

    async def connect(self) -> None:
        """
        Establish MAVLink connection.

        Uses UDP for real-time telemetry.
        """
        connection_string = f"udpin:{self.host}:{self.port}"

        try:
            self._connection = mavutil.mavlink_connection(
                connection_string,
                source_system=self.source_system,
                source_component=self.source_component,
            )

            # Wait for first heartbeat
            logger.info(f"Waiting for heartbeat from {connection_string}...")
            self._connection.wait_heartbeat(timeout=10)
            logger.info(
                f"Connected to vehicle (system {self._connection.target_system}, "
                f"component {self._connection.target_component})"
            )

            # Start background tasks
            self._running = True
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        except Exception as e:
            logger.error(f"MAVLink connection failed: {e}")
            raise ConnectionError(f"Cannot connect to vehicle: {e}") from e

    async def disconnect(self) -> None:
        """Close MAVLink connection."""
        self._running = False

        if self._receive_task:
            self._receive_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        if self._connection:
            self._connection.close()
            self._connection = None

        logger.info("MAVLink disconnected")

    async def _receive_loop(self) -> None:
        """Background task to receive and process messages."""
        while self._running and self._connection:
            try:
                msg = self._connection.recv_match(blocking=False)
                if msg:
                    await self._handle_message(msg)
                await asyncio.sleep(0.01)  # 100Hz
            except Exception as e:
                logger.error(f"Error in receive loop: {e}")
                await asyncio.sleep(0.1)

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to vehicle."""
        while self._running and self._connection:
            try:
                self._connection.mav.heartbeat_send(
                    mavutil.mavlink.MAV_TYPE_GCS,
                    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                    0,
                    0,
                    0,
                )
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error sending heartbeat: {e}")
                await asyncio.sleep(1)

    async def _handle_message(self, msg: Any) -> None:
        """
        Process incoming MAVLink message.

        Updates vehicle state and calls registered handlers.
        """
        msg_type = msg.get_type()

        # Update state based on message type
        if msg_type == "HEARTBEAT":
            self.state.armed = msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
            self.state.mode = FlightMode(msg.custom_mode)

        elif msg_type == "ATTITUDE":
            self.state.roll = msg.roll
            self.state.pitch = msg.pitch
            self.state.yaw = msg.yaw

        elif msg_type == "VFR_HUD":
            self.state.heading = msg.heading

        elif msg_type == "SCALED_PRESSURE2":
            # Calculate depth from pressure
            # Assuming freshwater: depth = pressure_diff / 9.80665
            surface_pressure = 101325  # Pa at surface
            pressure_pa = msg.press_abs * 100  # Convert mbar to Pa
            self.state.depth = (pressure_pa - surface_pressure) / 9806.65

        elif msg_type == "BATTERY_STATUS":
            if msg.voltages[0] != 65535:
                self.state.battery_voltage = msg.voltages[0] / 1000.0
            self.state.battery_remaining = msg.battery_remaining

        # Call registered handlers
        handlers = self._message_handlers.get(msg_type, [])
        for handler in handlers:
            try:
                await handler(msg)
            except Exception as e:
                logger.error(f"Handler error for {msg_type}: {e}")

    def on_message(self, msg_type: str) -> Callable:
        """
        Decorator to register message handler.

        Usage:
            @mav.on_message("ATTITUDE")
            async def on_attitude(msg):
                print(f"Roll: {msg.roll}")
        """

        def decorator(func: Callable) -> Callable:
            if msg_type not in self._message_handlers:
                self._message_handlers[msg_type] = []
            self._message_handlers[msg_type].append(func)
            return func

        return decorator

    # ==================== Commands ====================

    async def arm(self) -> bool:
        """
        Arm the vehicle.

        Returns:
            True if arm command was acknowledged
        """
        if not self._connection:
            raise ConnectionError("Not connected")

        self._connection.mav.command_long_send(
            self._connection.target_system,
            self._connection.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1,  # Arm
            0,
            0,
            0,
            0,
            0,
            0,
        )

        # Wait for ACK
        ack = self._connection.recv_match(type="COMMAND_ACK", blocking=True, timeout=3)
        success = ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED
        logger.info(f"Arm command: {'success' if success else 'failed'}")
        return success

    async def disarm(self) -> bool:
        """
        Disarm the vehicle.

        Returns:
            True if disarm command was acknowledged
        """
        if not self._connection:
            raise ConnectionError("Not connected")

        self._connection.mav.command_long_send(
            self._connection.target_system,
            self._connection.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            0,  # Disarm
            0,
            0,
            0,
            0,
            0,
            0,
        )

        ack = self._connection.recv_match(type="COMMAND_ACK", blocking=True, timeout=3)
        success = ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED
        logger.info(f"Disarm command: {'success' if success else 'failed'}")
        return success

    async def set_mode(self, mode: FlightMode) -> bool:
        """
        Set flight mode.

        Args:
            mode: Target flight mode

        Returns:
            True if mode change was acknowledged
        """
        if not self._connection:
            raise ConnectionError("Not connected")

        self._connection.mav.set_mode_send(
            self._connection.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode.value,
        )

        ack = self._connection.recv_match(type="COMMAND_ACK", blocking=True, timeout=3)
        success = ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED
        logger.info(f"Set mode {mode.name}: {'success' if success else 'failed'}")
        return success

    async def set_rc_override(
        self,
        pitch: int = 1500,
        roll: int = 1500,
        throttle: int = 1500,
        yaw: int = 1500,
        forward: int = 1500,
        lateral: int = 1500,
        lights1: int = 1100,
        lights2: int = 1100,
    ) -> None:
        """
        Send RC override for manual control.

        Values are PWM microseconds (1100-1900, center 1500).

        Args:
            pitch: Pitch control
            roll: Roll control
            throttle: Throttle (vertical)
            yaw: Yaw control
            forward: Forward/backward
            lateral: Left/right strafe
            lights1: Main lights level
            lights2: Aux lights level
        """
        if not self._connection:
            raise ConnectionError("Not connected")

        self._connection.mav.rc_channels_override_send(
            self._connection.target_system,
            self._connection.target_component,
            pitch,
            roll,
            throttle,
            yaw,
            forward,
            lateral,
            lights1,
            lights2,
        )

    async def set_lights(self, level: int) -> None:
        """
        Set lights level.

        Args:
            level: Light level 0-100
        """
        pwm = 1100 + int(level * 8)  # Map 0-100 to 1100-1900
        await self.set_rc_override(lights1=pwm, lights2=pwm)


# Singleton for dependency injection
_mavlink_connection: MAVLinkConnection | None = None


async def get_mavlink_connection() -> MAVLinkConnection:
    """Get or create MAVLink connection singleton."""
    global _mavlink_connection
    if _mavlink_connection is None:
        _mavlink_connection = MAVLinkConnection()
        await _mavlink_connection.connect()
    return _mavlink_connection
