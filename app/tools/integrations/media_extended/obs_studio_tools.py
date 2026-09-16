"""
OBS Studio integration.

OBS ships with obs-websocket (built in since OBS 28).
We talk to it via its WebSocket protocol.

Default: ws://127.0.0.1:4455

Tools:
    - obs_start_recording
    - obs_stop_recording
    - obs_start_streaming
    - obs_stop_streaming

Note: obs-websocket requires a password set in OBS.
Configure via OBS_WEBSOCKET_PASSWORD in .env.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from typing import Any, Dict, Optional

from app.core.config_manager import ConfigManager
from app.core.logger import get_logger
from app.tools.base import ToolResult, RiskLevel
from app.tools.integrations.integration_base import AppIntegrationTool

logger = get_logger(__name__)

try:
    import websockets  # type: ignore
    _WS_AVAILABLE = True
except Exception:  # noqa: BLE001
    websockets = None  # type: ignore
    _WS_AVAILABLE = False


# ---------------------------------------------------------------------- #
# OBS WebSocket helpers
# ---------------------------------------------------------------------- #
def _obs_url() -> str:
    return str(ConfigManager.get(
        "integrations.media_extended.obs_websocket_url",
        "ws://127.0.0.1:4455",
    ))


def _obs_password() -> Optional[str]:
    env_key = str(ConfigManager.get(
        "integrations.media_extended.obs_password_env",
        "OBS_WEBSOCKET_PASSWORD",
    ))
    return os.getenv(env_key) or None


def _generate_auth(password: str, salt: str, challenge: str) -> str:
    secret = base64.b64encode(
        hashlib.sha256((password + salt).encode("utf-8")).digest()
    ).decode("ascii")
    auth = base64.b64encode(
        hashlib.sha256((secret + challenge).encode("utf-8")).digest()
    ).decode("ascii")
    return auth


async def _obs_request(request_type: str, request_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Send a request to OBS WebSocket and return the response dict."""
    if not _WS_AVAILABLE:
        raise RuntimeError("websockets library missing. Run: pip install websockets")

    url = _obs_url()
    password = _obs_password()

    async with websockets.connect(url, max_size=8 * 1024 * 1024) as ws:  # type: ignore
        # Hello message
        hello_raw = await ws.recv()
        hello = json.loads(hello_raw)
        hello_data = hello.get("d", {})

        # Authentication
        if hello_data.get("authentication"):
            if not password:
                raise RuntimeError(
                    "OBS requires a password. Set OBS_WEBSOCKET_PASSWORD in .env."
                )
            salt = hello_data["authentication"]["salt"]
            challenge = hello_data["authentication"]["challenge"]
            auth = _generate_auth(password, salt, challenge)
            identify = {
                "op": 1,
                "d": {"rpcVersion": 1, "authentication": auth},
            }
        else:
            identify = {"op": 1, "d": {"rpcVersion": 1}}

        await ws.send(json.dumps(identify))

        # Identified
        identified = json.loads(await ws.recv())
        if identified.get("op") != 2:
            raise RuntimeError(f"OBS auth failed: {identified}")

        # Send the actual request
        req_id = str(secrets.token_hex(8))
        message = {
            "op": 6,
            "d": {
                "requestType": request_type,
                "requestId": req_id,
                "requestData": request_data or {},
            },
        }
        await ws.send(json.dumps(message))

        # Wait for the response with our requestId
        while True:
            raw = await ws.recv()
            data = json.loads(raw)
            if data.get("op") == 7 and data.get("d", {}).get("requestId") == req_id:
                return data["d"]


# ---------------------------------------------------------------------- #
# Tools
# ---------------------------------------------------------------------- #
class OBSStartRecordingTool(AppIntegrationTool):
    APP_KEY = "obs_studio"
    CONFIG_SECTION = "integrations.media_extended"

    name = "obs_start_recording"
    description = "Start recording in OBS Studio."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.MEDIUM
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        try:
            result = await _obs_request("StartRecord")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OBS_FAILED", "message": str(exc)},
            )
        status = result.get("requestStatus", {})
        return ToolResult(
            success=bool(status.get("result")),
            tool=self.name,
            data={"obs": result},
        )


class OBSStopRecordingTool(AppIntegrationTool):
    APP_KEY = "obs_studio"
    CONFIG_SECTION = "integrations.media_extended"

    name = "obs_stop_recording"
    description = "Stop recording in OBS Studio."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        try:
            result = await _obs_request("StopRecord")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OBS_FAILED", "message": str(exc)},
            )
        status = result.get("requestStatus", {})
        return ToolResult(
            success=bool(status.get("result")),
            tool=self.name,
            data={"obs": result},
        )


class OBSStartStreamingTool(AppIntegrationTool):
    APP_KEY = "obs_studio"
    CONFIG_SECTION = "integrations.media_extended"

    name = "obs_start_streaming"
    description = "Start streaming in OBS Studio."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.HIGH
    requires_confirmation = True

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        try:
            result = await _obs_request("StartStream")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OBS_FAILED", "message": str(exc)},
            )
        status = result.get("requestStatus", {})
        return ToolResult(
            success=bool(status.get("result")),
            tool=self.name,
            data={"obs": result},
        )


class OBSStopStreamingTool(AppIntegrationTool):
    APP_KEY = "obs_studio"
    CONFIG_SECTION = "integrations.media_extended"

    name = "obs_stop_streaming"
    description = "Stop streaming in OBS Studio."
    parameters = {"type": "object", "properties": {}, "required": []}
    risk_level = RiskLevel.LOW
    requires_confirmation = False

    async def run_impl(self, **kwargs: Any) -> ToolResult:
        try:
            result = await _obs_request("StopStream")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                tool=self.name,
                error={"code": "OBS_FAILED", "message": str(exc)},
            )
        status = result.get("requestStatus", {})
        return ToolResult(
            success=bool(status.get("result")),
            tool=self.name,
            data={"obs": result},
        )