"""
BlueOS HTTP API Client.

Provides async interface to BlueOS REST API for:
- System information
- Service management
- Parameter configuration
- Extension management
"""

import asyncio
from typing import Any

import aiohttp
from loguru import logger

from app.core.config import settings


class BlueOSClient:
    """
    Async client for BlueOS HTTP API.

    BlueOS runs on the ROV's companion computer (Raspberry Pi)
    and provides REST API for configuration and monitoring.

    Usage:
        async with BlueOSClient() as client:
            info = await client.get_system_info()
            print(info)
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        timeout: int | None = None,
    ) -> None:
        """
        Initialize BlueOS client.

        Args:
            host: BlueOS host IP (default from settings)
            port: BlueOS HTTP port (default from settings)
            timeout: Request timeout in seconds
        """
        self.host = host or settings.blueos_host
        self.port = port or settings.blueos_port
        self.timeout = timeout or settings.blueos_api_timeout
        self.base_url = f"http://{self.host}:{self.port}"
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "BlueOSClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self) -> None:
        """Create HTTP session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
            logger.info(f"BlueOS client connected to {self.base_url}")

    async def disconnect(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("BlueOS client disconnected")

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Make HTTP request to BlueOS API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional aiohttp request arguments

        Returns:
            JSON response as dictionary

        Raises:
            ConnectionError: If BlueOS is unreachable
            ValueError: If response is not valid JSON
        """
        if not self._session:
            await self.connect()

        url = f"{self.base_url}{endpoint}"

        try:
            async with self._session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Cannot connect to BlueOS at {self.base_url}: {e}")
            raise ConnectionError(f"BlueOS unreachable: {e}") from e
        except aiohttp.ContentTypeError:
            # Some endpoints return plain text
            return {"status": "ok"}

    # ==================== System API ====================

    async def get_system_info(self) -> dict[str, Any]:
        """
        Get BlueOS system information.

        Returns:
            System info including version, uptime, hardware
        """
        return await self._request("GET", "/system-information/system")

    async def get_cpu_info(self) -> dict[str, Any]:
        """Get CPU usage and temperature."""
        return await self._request("GET", "/system-information/system/cpu")

    async def get_memory_info(self) -> dict[str, Any]:
        """Get RAM usage statistics."""
        return await self._request("GET", "/system-information/system/memory")

    async def get_disk_info(self) -> dict[str, Any]:
        """Get disk usage statistics."""
        return await self._request("GET", "/system-information/system/disk")

    async def get_network_info(self) -> list[dict[str, Any]]:
        """Get network interfaces information."""
        return await self._request("GET", "/system-information/system/network")

    # ==================== MAVLink API ====================

    async def get_mavlink_endpoints(self) -> list[dict[str, Any]]:
        """Get list of MAVLink endpoints."""
        return await self._request("GET", "/mavlink2rest/endpoints")

    async def get_vehicle_state(self) -> dict[str, Any]:
        """
        Get current vehicle state via MAVLink2REST.

        Returns:
            Vehicle state including armed status, mode, etc.
        """
        return await self._request(
            "GET",
            "/mavlink2rest/mavlink/vehicles/1/components/1/messages/HEARTBEAT",
        )

    async def get_attitude(self) -> dict[str, Any]:
        """
        Get vehicle attitude (roll, pitch, yaw).

        Returns:
            Attitude angles in radians
        """
        return await self._request(
            "GET",
            "/mavlink2rest/mavlink/vehicles/1/components/1/messages/ATTITUDE",
        )

    async def get_depth(self) -> dict[str, Any]:
        """
        Get current depth from pressure sensor.

        Returns:
            Depth information including pressure and temperature
        """
        return await self._request(
            "GET",
            "/mavlink2rest/mavlink/vehicles/1/components/1/messages/SCALED_PRESSURE2",
        )

    async def get_battery_status(self) -> dict[str, Any]:
        """
        Get battery status.

        Returns:
            Battery voltage, current, remaining capacity
        """
        return await self._request(
            "GET",
            "/mavlink2rest/mavlink/vehicles/1/components/1/messages/BATTERY_STATUS",
        )

    # ==================== Parameters API ====================

    async def get_parameters(self) -> dict[str, Any]:
        """Get all vehicle parameters."""
        return await self._request("GET", "/mavlink2rest/helper/parameters")

    async def set_parameter(self, name: str, value: float) -> dict[str, Any]:
        """
        Set a vehicle parameter.

        Args:
            name: Parameter name (e.g., 'LIGHTS1_LEVEL')
            value: Parameter value

        Returns:
            Confirmation response
        """
        return await self._request(
            "POST",
            "/mavlink2rest/helper/parameters",
            json={"id": name, "value": value},
        )

    # ==================== Camera API ====================

    async def get_cameras(self) -> list[dict[str, Any]]:
        """Get list of available cameras."""
        return await self._request("GET", "/mavlink-camera-manager/cameras")

    async def get_video_streams(self) -> list[dict[str, Any]]:
        """Get list of video streams."""
        return await self._request("GET", "/mavlink-camera-manager/streams")

    # ==================== Ping Sonar API ====================

    async def get_ping_devices(self) -> list[dict[str, Any]]:
        """Get list of Ping sonar devices."""
        return await self._request("GET", "/ping/devices")

    async def get_ping_distance(self, device_id: int = 0) -> dict[str, Any]:
        """
        Get distance measurement from Ping sonar.

        Args:
            device_id: Ping device ID

        Returns:
            Distance measurement in mm
        """
        return await self._request("GET", f"/ping/devices/{device_id}/distance")

    # ==================== Extensions API ====================

    async def get_extensions(self) -> list[dict[str, Any]]:
        """Get list of installed BlueOS extensions."""
        return await self._request("GET", "/kraken/extensions/installed")

    async def install_extension(
        self,
        identifier: str,
        tag: str = "latest",
    ) -> dict[str, Any]:
        """
        Install a BlueOS extension.

        Args:
            identifier: Extension Docker image identifier
            tag: Docker image tag

        Returns:
            Installation status
        """
        return await self._request(
            "POST",
            "/kraken/extensions/install",
            json={"identifier": identifier, "tag": tag},
        )

    # ==================== Lights Control ====================

    async def set_lights(self, level: int) -> dict[str, Any]:
        """
        Set ROV lights level.

        Args:
            level: Light level 0-100

        Returns:
            Confirmation response
        """
        # LIGHTS1_LEVEL parameter: 1000-2000 (PWM microseconds)
        pwm_value = 1000 + (level * 10)
        return await self.set_parameter("LIGHTS1_LEVEL", pwm_value)

    # ==================== Health Check ====================

    async def health_check(self) -> bool:
        """
        Check if BlueOS is reachable and healthy.

        Returns:
            True if BlueOS is responding
        """
        try:
            await self.get_system_info()
            return True
        except Exception as e:
            logger.warning(f"BlueOS health check failed: {e}")
            return False


# Singleton instance for dependency injection
_blueos_client: BlueOSClient | None = None


async def get_blueos_client() -> BlueOSClient:
    """
    Get or create BlueOS client singleton.

    Usage with FastAPI:
        @app.get("/rov/status")
        async def get_status(
            client: BlueOSClient = Depends(get_blueos_client)
        ):
            return await client.get_vehicle_state()
    """
    global _blueos_client
    if _blueos_client is None:
        _blueos_client = BlueOSClient()
        await _blueos_client.connect()
    return _blueos_client
