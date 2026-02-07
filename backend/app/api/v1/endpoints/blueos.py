"""
BlueOS / ROV API Endpoints.

Provides REST API for ROV control and monitoring.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.modules.blueos.client import BlueOSClient, get_blueos_client
from app.modules.blueos.telemetry import TelemetryService, get_telemetry_service
from app.modules.blueos.video import VideoStreamManager, get_video_manager

router = APIRouter()


# ==================== Schemas ====================


class LightsRequest(BaseModel):
    """Request to set lights level."""

    level: int  # 0-100


class ArmRequest(BaseModel):
    """Request to arm/disarm vehicle."""

    arm: bool


class ModeRequest(BaseModel):
    """Request to change flight mode."""

    mode: str  # STABILIZE, ALT_HOLD, MANUAL, etc.


# ==================== System Endpoints ====================


@router.get("/status")
async def get_rov_status(
    client: BlueOSClient = Depends(get_blueos_client),
) -> dict[str, Any]:
    """
    Get ROV system status.

    Returns system info, connection status, and basic telemetry.
    """
    try:
        system_info = await client.get_system_info()
        vehicle_state = await client.get_vehicle_state()

        return {
            "connected": True,
            "system": system_info,
            "vehicle": vehicle_state,
        }
    except ConnectionError:
        return {
            "connected": False,
            "error": "BlueOS not reachable",
        }


@router.get("/telemetry")
async def get_telemetry(
    telemetry: TelemetryService = Depends(get_telemetry_service),
) -> dict[str, Any]:
    """
    Get latest telemetry snapshot.

    Returns current attitude, depth, battery, and sensor data.
    """
    return await telemetry.get_snapshot()


@router.get("/system/cpu")
async def get_cpu_info(
    client: BlueOSClient = Depends(get_blueos_client),
) -> dict[str, Any]:
    """Get CPU usage and temperature."""
    return await client.get_cpu_info()


@router.get("/system/memory")
async def get_memory_info(
    client: BlueOSClient = Depends(get_blueos_client),
) -> dict[str, Any]:
    """Get RAM usage."""
    return await client.get_memory_info()


@router.get("/system/disk")
async def get_disk_info(
    client: BlueOSClient = Depends(get_blueos_client),
) -> dict[str, Any]:
    """Get disk usage."""
    return await client.get_disk_info()


# ==================== Control Endpoints ====================


@router.post("/lights")
async def set_lights(
    request: LightsRequest,
    client: BlueOSClient = Depends(get_blueos_client),
) -> dict[str, Any]:
    """
    Set ROV lights level.

    Args:
        level: Light intensity 0-100%
    """
    if not 0 <= request.level <= 100:
        raise HTTPException(status_code=400, detail="Level must be 0-100")

    result = await client.set_lights(request.level)
    return {"success": True, "level": request.level}


@router.get("/parameters")
async def get_parameters(
    client: BlueOSClient = Depends(get_blueos_client),
) -> dict[str, Any]:
    """Get all vehicle parameters."""
    return await client.get_parameters()


# ==================== Camera Endpoints ====================


@router.get("/cameras")
async def get_cameras(
    client: BlueOSClient = Depends(get_blueos_client),
) -> list[dict[str, Any]]:
    """Get list of available cameras."""
    return await client.get_cameras()


@router.get("/streams")
async def get_video_streams(
    video: VideoStreamManager = Depends(get_video_manager),
) -> list[dict[str, Any]]:
    """Get list of video streams with URLs."""
    streams = await video.get_streams()

    # Add playback URLs
    for stream in streams:
        stream_id = stream["id"]
        stream["webrtc_url"] = video.get_webrtc_url(stream_id)
        stream["mjpeg_url"] = video.get_mjpeg_url(stream_id)
        stream["snapshot_url"] = video.get_snapshot_url(stream_id)

    return streams


# ==================== Sensor Endpoints ====================


@router.get("/ping")
async def get_ping_sonar(
    client: BlueOSClient = Depends(get_blueos_client),
) -> dict[str, Any]:
    """
    Get Ping sonar distance measurement.

    Returns distance to bottom/obstacle in mm.
    """
    try:
        devices = await client.get_ping_devices()
        if not devices:
            return {"available": False, "message": "No Ping sonar detected"}

        distance = await client.get_ping_distance()
        return {
            "available": True,
            "distance_mm": distance.get("distance", 0),
            "distance_m": distance.get("distance", 0) / 1000,
            "confidence": distance.get("confidence", 0),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


# ==================== Extensions ====================


@router.get("/extensions")
async def get_extensions(
    client: BlueOSClient = Depends(get_blueos_client),
) -> list[dict[str, Any]]:
    """Get installed BlueOS extensions."""
    return await client.get_extensions()


# ==================== WebSocket ====================


@router.websocket("/telemetry/ws")
async def telemetry_websocket(
    websocket: WebSocket,
    telemetry: TelemetryService = Depends(get_telemetry_service),
) -> None:
    """
    WebSocket for real-time telemetry updates.

    Sends telemetry packets at ~5Hz.
    """
    await websocket.accept()
    telemetry.add_client(websocket)

    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_text()
            # Could process commands here
    except WebSocketDisconnect:
        telemetry.remove_client(websocket)
