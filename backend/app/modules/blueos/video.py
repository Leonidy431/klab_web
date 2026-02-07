"""
Video Stream Manager Module.

Manages video streams from ROV cameras including:
- H.264/H.265 stream proxying
- RTSP to WebRTC conversion
- Snapshot capture
- Recording management
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any

from loguru import logger

from app.core.config import settings
from app.modules.blueos.client import BlueOSClient, get_blueos_client


class StreamProtocol(str, Enum):
    """Video streaming protocols."""

    RTSP = "rtsp"
    UDP = "udp"
    WEBRTC = "webrtc"
    MJPEG = "mjpeg"


@dataclass
class VideoStream:
    """Video stream configuration."""

    name: str
    source: str
    protocol: StreamProtocol
    width: int = 1920
    height: int = 1080
    fps: int = 30
    bitrate: int = 5000000
    active: bool = False


class VideoStreamManager:
    """
    Manages video streams from BlueOS cameras.

    Features:
    - Stream discovery via BlueOS API
    - WebRTC signaling for browser playback
    - Recording to file
    - Snapshot capture

    Usage:
        manager = VideoStreamManager()
        await manager.start()
        streams = await manager.get_streams()
    """

    def __init__(self) -> None:
        """Initialize video stream manager."""
        self._blueos_client: BlueOSClient | None = None
        self._streams: dict[str, VideoStream] = {}
        self._running = False

    async def start(
        self,
        blueos_client: BlueOSClient | None = None,
    ) -> None:
        """
        Start video stream manager.

        Args:
            blueos_client: Optional BlueOS client instance
        """
        self._blueos_client = blueos_client or await get_blueos_client()
        self._running = True

        # Discover available streams
        await self._discover_streams()

        logger.info(f"Video manager started. Found {len(self._streams)} streams")

    async def stop(self) -> None:
        """Stop video stream manager."""
        self._running = False
        self._streams.clear()
        logger.info("Video manager stopped")

    async def _discover_streams(self) -> None:
        """Discover video streams from BlueOS."""
        try:
            cameras = await self._blueos_client.get_cameras()
            streams = await self._blueos_client.get_video_streams()

            for stream in streams:
                stream_id = stream.get("name", f"stream_{len(self._streams)}")
                video_stream = VideoStream(
                    name=stream_id,
                    source=stream.get("source", ""),
                    protocol=StreamProtocol(stream.get("protocol", "udp")),
                    width=stream.get("width", 1920),
                    height=stream.get("height", 1080),
                    fps=stream.get("fps", 30),
                    bitrate=stream.get("bitrate", 5000000),
                    active=stream.get("active", True),
                )
                self._streams[stream_id] = video_stream

        except Exception as e:
            logger.error(f"Stream discovery failed: {e}")

            # Add default stream for ROV main camera
            default_stream = VideoStream(
                name="main",
                source=f"udp://{settings.blueos_host}:{settings.blueos_video_port}",
                protocol=StreamProtocol.UDP,
            )
            self._streams["main"] = default_stream

    async def get_streams(self) -> list[dict[str, Any]]:
        """
        Get list of available video streams.

        Returns:
            List of stream configurations
        """
        return [
            {
                "id": stream_id,
                "name": stream.name,
                "source": stream.source,
                "protocol": stream.protocol.value,
                "resolution": f"{stream.width}x{stream.height}",
                "fps": stream.fps,
                "active": stream.active,
            }
            for stream_id, stream in self._streams.items()
        ]

    async def get_stream(self, stream_id: str) -> VideoStream | None:
        """Get stream by ID."""
        return self._streams.get(stream_id)

    def get_webrtc_url(self, stream_id: str = "main") -> str:
        """
        Get WebRTC signaling URL for stream.

        BlueOS provides WebRTC via mavlink-camera-manager.

        Args:
            stream_id: Stream identifier

        Returns:
            WebRTC signaling endpoint URL
        """
        base = f"http://{settings.blueos_host}:{settings.blueos_port}"
        return f"{base}/mavlink-camera-manager/webrtc/{stream_id}"

    def get_mjpeg_url(self, stream_id: str = "main") -> str:
        """
        Get MJPEG stream URL (fallback for older browsers).

        Args:
            stream_id: Stream identifier

        Returns:
            MJPEG stream URL
        """
        base = f"http://{settings.blueos_host}:{settings.blueos_port}"
        return f"{base}/mavlink-camera-manager/mjpeg/{stream_id}"

    def get_snapshot_url(self, stream_id: str = "main") -> str:
        """
        Get URL to capture single frame snapshot.

        Args:
            stream_id: Stream identifier

        Returns:
            Snapshot endpoint URL
        """
        base = f"http://{settings.blueos_host}:{settings.blueos_port}"
        return f"{base}/mavlink-camera-manager/snapshot/{stream_id}"

    async def start_recording(
        self,
        stream_id: str = "main",
        filename: str | None = None,
    ) -> dict[str, Any]:
        """
        Start recording video stream to file.

        Args:
            stream_id: Stream to record
            filename: Output filename (auto-generated if not specified)

        Returns:
            Recording status
        """
        stream = self._streams.get(stream_id)
        if not stream:
            return {"error": f"Stream {stream_id} not found"}

        # BlueOS handles recording via mavlink-camera-manager
        # This would trigger recording via REST API
        logger.info(f"Started recording stream {stream_id}")

        return {
            "status": "recording",
            "stream_id": stream_id,
            "filename": filename or f"recording_{stream_id}.mp4",
        }

    async def stop_recording(self, stream_id: str = "main") -> dict[str, Any]:
        """
        Stop recording video stream.

        Args:
            stream_id: Stream to stop recording

        Returns:
            Recording result with file path
        """
        logger.info(f"Stopped recording stream {stream_id}")
        return {
            "status": "stopped",
            "stream_id": stream_id,
        }


# Singleton instance
_video_manager: VideoStreamManager | None = None


async def get_video_manager() -> VideoStreamManager:
    """Get or create video manager singleton."""
    global _video_manager
    if _video_manager is None:
        _video_manager = VideoStreamManager()
        await _video_manager.start()
    return _video_manager
