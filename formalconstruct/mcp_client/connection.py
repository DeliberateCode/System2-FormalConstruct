"""AXLE MCP subprocess lifecycle manager.

Manages the ``uvx --from axiom-axle-mcp==<version> axle-mcp-server`` subprocess
(the pinned package spec lives in ``AxleConfig``), communicating via JSON-RPC
2.0 over stdin/stdout.
"""

from __future__ import annotations

import asyncio
import json
import os

from formalconstruct import __version__
from formalconstruct.core.config import AxleConfig
from formalconstruct.core.exceptions import (
    AxleConnectionError,
    AxleRateLimitedError,
    AxleTimeoutError,
    AxleUnavailableError,
    AxleValidationError,
    MissingApiKeyError,
)


class AxleMcpConnection:
    """Manages the AXLE MCP server subprocess."""

    def __init__(
        self,
        config: AxleConfig | None = None,
        api_key: str | None = None,
    ) -> None:
        self._config = config or AxleConfig()
        self._api_key = api_key or os.environ.get("AXLE_API_KEY")
        if not self._api_key:
            raise MissingApiKeyError(
                "AXLE_API_KEY environment variable is required"
            )
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Launch axle-mcp-server via uvx and perform JSON-RPC initialize handshake."""
        env = os.environ.copy()
        env["AXLE_API_KEY"] = self._api_key
        self._process = await asyncio.create_subprocess_exec(
            "uvx",
            "--from",
            self._config.axle_mcp_package,
            self._config.axle_mcp_server,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            await self._send_initialize()
        except Exception:
            await self.shutdown()
            raise

    async def send_request(self, method: str, params: dict) -> dict:
        """Send a JSON-RPC tools/call request and return the parsed result.

        Serialized with an asyncio.Lock to prevent concurrent requests
        from crossing responses on the shared subprocess.
        """
        async with self._lock:
            return await self._send_request_locked(method, params)

    async def _send_request_locked(self, method: str, params: dict) -> dict:
        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise AxleConnectionError("AXLE subprocess not started; call start() first")
        self._request_id += 1
        request_id = self._request_id
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": method, "arguments": params},
        }
        data = json.dumps(request) + "\n"
        self._process.stdin.write(data.encode())
        await self._process.stdin.drain()

        try:
            line = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=self._config.timeout_seconds,
            )
        except asyncio.TimeoutError:
            await self._drain_stale_response()
            raise AxleTimeoutError(
                f"AXLE call '{method}' timed out after {self._config.timeout_seconds}s"
            )

        if not line:
            raise AxleConnectionError("AXLE subprocess closed unexpectedly")
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AxleConnectionError(
                f"AXLE subprocess returned invalid JSON: {exc}"
            ) from exc

        resp_id = response.get("id")
        if resp_id != request_id:
            raise AxleConnectionError(
                f"Response ID mismatch: sent {request_id}, got {resp_id}"
            )

        if "error" in response:
            raise self._classify_error(response["error"])

        result = response.get("result", {})
        content = result.get("content", [])
        if (
            content
            and isinstance(content, list)
            and isinstance(content[0], dict)
            and content[0].get("type") == "text"
        ):
            text = content[0]["text"]
            if not text:
                return result
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                if text.startswith("AXLE error"):
                    raise AxleValidationError(text)
                raise AxleConnectionError(
                    f"AXLE response content is not valid JSON: {text[:200]}"
                )
        return result

    async def _drain_stale_response(self) -> None:
        """After a timeout, attempt to read and discard the stale response."""
        if self._process is None or self._process.stdout is None:
            return
        try:
            await asyncio.wait_for(self._process.stdout.readline(), timeout=5)
        except (asyncio.TimeoutError, Exception):
            pass

    async def shutdown(self) -> None:
        """Gracefully terminate the subprocess, falling back to kill on timeout."""
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()

    async def __aenter__(self) -> AxleMcpConnection:
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.shutdown()

    async def _send_initialize(self) -> None:
        """Perform the MCP protocol initialize handshake."""
        if self._process is None or self._process.stdin is None or self._process.stdout is None:
            raise AxleConnectionError("AXLE subprocess not started; call start() first")
        self._request_id += 1
        init_req = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "formalconstruct", "version": __version__},
            },
        }
        data = json.dumps(init_req) + "\n"
        self._process.stdin.write(data.encode())
        await self._process.stdin.drain()
        try:
            line = await asyncio.wait_for(self._process.stdout.readline(), timeout=10)
        except asyncio.TimeoutError:
            raise AxleConnectionError("AXLE server did not respond to initialize handshake")
        if not line:
            raise AxleConnectionError("AXLE server closed during initialize handshake")
        try:
            resp = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AxleConnectionError(
                f"AXLE initialize handshake returned invalid JSON: {exc}"
            ) from exc
        if "error" in resp:
            raise AxleConnectionError(
                f"AXLE initialize handshake failed: {resp['error']}"
            )
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        data = json.dumps(notif) + "\n"
        self._process.stdin.write(data.encode())
        await self._process.stdin.drain()

    @staticmethod
    def _classify_error(error: dict) -> Exception:
        """Map JSON-RPC error codes to the exception hierarchy."""
        code = error.get("code", 0)
        message = error.get("message", "Unknown error")
        if code == 429:
            data = error.get("data", {})
            retry_after = data.get("retry_after") if isinstance(data, dict) else None
            return AxleRateLimitedError(message, retry_after=retry_after)
        if code == 503:
            return AxleUnavailableError(message)
        return AxleValidationError(message)
