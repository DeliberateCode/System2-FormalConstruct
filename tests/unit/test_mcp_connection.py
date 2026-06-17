"""Unit tests for formalconstruct.mcp_client.connection -- AxleMcpConnection.

Tests subprocess lifecycle, JSON-RPC communication, error classification,
and async context manager protocol. All subprocess interactions are mocked.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from formalconstruct.core.config import AxleConfig
from formalconstruct.core.exceptions import (
    AxleRateLimitedError,
    AxleTimeoutError,
    AxleUnavailableError,
    AxleValidationError,
    MissingApiKeyError,
)
from formalconstruct.mcp_client.connection import AxleMcpConnection


class TestConstructor:
    def test_raises_missing_api_key_when_no_key(self, monkeypatch):
        monkeypatch.delenv("AXLE_API_KEY", raising=False)
        with pytest.raises(MissingApiKeyError):
            AxleMcpConnection(api_key=None)

    def test_accepts_explicit_api_key(self, monkeypatch):
        monkeypatch.delenv("AXLE_API_KEY", raising=False)
        conn = AxleMcpConnection(api_key="test-key-123")
        assert conn._api_key == "test-key-123"

    def test_reads_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "env-key-456")
        conn = AxleMcpConnection()
        assert conn._api_key == "env-key-456"

    def test_explicit_key_overrides_env(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "env-key")
        conn = AxleMcpConnection(api_key="explicit-key")
        assert conn._api_key == "explicit-key"

    def test_uses_default_config_when_none(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "key")
        conn = AxleMcpConnection()
        assert conn._config.timeout_seconds == 120

    def test_uses_provided_config(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "key")
        config = AxleConfig(timeout_seconds=30)
        conn = AxleMcpConnection(config=config)
        assert conn._config.timeout_seconds == 30

    def test_initial_state(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "key")
        conn = AxleMcpConnection()
        assert conn._process is None
        assert conn._request_id == 0


def _make_mock_process(responses: list[dict] | None = None):
    """Create a mock subprocess with stdin/stdout for JSON-RPC communication."""
    proc = AsyncMock(spec=asyncio.subprocess.Process)
    proc.stdin = MagicMock()
    proc.stdin.write = MagicMock()
    proc.stdin.drain = AsyncMock()

    if responses is None:
        responses = []

    lines = [json.dumps(r).encode() + b"\n" for r in responses]
    read_index = 0

    async def readline():
        nonlocal read_index
        if read_index < len(lines):
            line = lines[read_index]
            read_index += 1
            return line
        return b""

    proc.stdout = MagicMock()
    proc.stdout.readline = readline
    proc.stderr = MagicMock()
    proc.returncode = None
    proc.wait = AsyncMock()
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    return proc


class TestStart:
    @pytest.mark.asyncio
    async def test_start_launches_subprocess(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "test-key")
        conn = AxleMcpConnection()

        init_response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        proc = _make_mock_process([init_response])

        with patch("asyncio.create_subprocess_exec", return_value=proc) as mock_exec:
            await conn.start()

        mock_exec.assert_called_once()
        args = mock_exec.call_args
        assert args[0] == ("uvx", "--from", "axiom-axle-mcp==0.3.5", "axle-mcp-server")
        assert args[1]["env"]["AXLE_API_KEY"] == "test-key"

    @pytest.mark.asyncio
    async def test_start_sends_initialize_handshake(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "test-key")
        conn = AxleMcpConnection()

        init_response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        proc = _make_mock_process([init_response])

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await conn.start()

        # Should have written initialize request and initialized notification
        assert proc.stdin.write.call_count == 2
        first_write = proc.stdin.write.call_args_list[0][0][0]
        init_req = json.loads(first_write.decode())
        assert init_req["method"] == "initialize"
        assert init_req["params"]["protocolVersion"] == "2024-11-05"
        assert init_req["params"]["clientInfo"]["name"] == "formalconstruct"

        second_write = proc.stdin.write.call_args_list[1][0][0]
        notif = json.loads(second_write.decode())
        assert notif["method"] == "notifications/initialized"
        assert "id" not in notif


class TestSendRequest:
    @pytest.mark.asyncio
    async def test_send_request_returns_parsed_content(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "test-key")
        conn = AxleMcpConnection()

        init_response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        tool_response = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "lean_messages": {"errors": [], "warnings": [], "infos": []},
                                "tool_messages": {"errors": [], "warnings": [], "infos": []},
                            }
                        ),
                    }
                ]
            },
        }
        proc = _make_mock_process([init_response, tool_response])

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await conn.start()
            result = await conn.send_request("check", {"content": "test", "environment": "lean-4.29.0"})

        assert result["lean_messages"]["errors"] == []

    @pytest.mark.asyncio
    async def test_send_request_increments_request_id(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "test-key")
        conn = AxleMcpConnection()

        init_response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        resp1 = {"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": "{}"}]}}
        resp2 = {"jsonrpc": "2.0", "id": 3, "result": {"content": [{"type": "text", "text": "{}"}]}}
        proc = _make_mock_process([init_response, resp1, resp2])

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await conn.start()
            await conn.send_request("check", {"content": "a"})
            await conn.send_request("check", {"content": "b"})

        # init uses id=1, first call id=2, second call id=3
        writes = proc.stdin.write.call_args_list
        # Skip init and notification writes (indices 0, 1)
        req1 = json.loads(writes[2][0][0].decode())
        req2 = json.loads(writes[3][0][0].decode())
        assert req1["id"] == 2
        assert req2["id"] == 3

    @pytest.mark.asyncio
    async def test_send_request_uses_tools_call_method(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "test-key")
        conn = AxleMcpConnection()

        init_response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        tool_response = {"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": "{}"}]}}
        proc = _make_mock_process([init_response, tool_response])

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await conn.start()
            await conn.send_request("verify_proof", {"content": "test"})

        writes = proc.stdin.write.call_args_list
        req = json.loads(writes[2][0][0].decode())
        assert req["method"] == "tools/call"
        assert req["params"]["name"] == "verify_proof"
        assert req["params"]["arguments"] == {"content": "test"}

    @pytest.mark.asyncio
    async def test_send_request_timeout_raises_axle_timeout(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "test-key")
        config = AxleConfig(timeout_seconds=1)
        conn = AxleMcpConnection(config=config)

        init_response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        proc = _make_mock_process([init_response])

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await conn.start()

            # Override readline to hang AFTER init handshake completes
            async def hang():
                await asyncio.sleep(100)
                return b""

            proc.stdout.readline = hang
            with pytest.raises(AxleTimeoutError, match="timed out"):
                await conn.send_request("check", {"content": "test"})

    @pytest.mark.asyncio
    async def test_send_request_returns_result_when_no_content(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "test-key")
        conn = AxleMcpConnection()

        init_response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        tool_response = {"jsonrpc": "2.0", "id": 2, "result": {"some_key": "some_value"}}
        proc = _make_mock_process([init_response, tool_response])

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await conn.start()
            result = await conn.send_request("check", {"content": "test"})

        assert result == {"some_key": "some_value"}


class TestErrorClassification:
    @pytest.mark.asyncio
    async def test_rate_limited_error(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "test-key")
        conn = AxleMcpConnection()

        init_response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        error_response = {
            "jsonrpc": "2.0",
            "id": 2,
            "error": {"code": 429, "message": "Rate limited"},
        }
        proc = _make_mock_process([init_response, error_response])

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await conn.start()
            with pytest.raises(AxleRateLimitedError):
                await conn.send_request("check", {"content": "test"})

    @pytest.mark.asyncio
    async def test_unavailable_error(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "test-key")
        conn = AxleMcpConnection()

        init_response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        error_response = {
            "jsonrpc": "2.0",
            "id": 2,
            "error": {"code": 503, "message": "Service unavailable"},
        }
        proc = _make_mock_process([init_response, error_response])

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await conn.start()
            with pytest.raises(AxleUnavailableError):
                await conn.send_request("check", {"content": "test"})

    @pytest.mark.asyncio
    async def test_validation_error_for_unknown_code(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "test-key")
        conn = AxleMcpConnection()

        init_response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        error_response = {
            "jsonrpc": "2.0",
            "id": 2,
            "error": {"code": -32600, "message": "Invalid request"},
        }
        proc = _make_mock_process([init_response, error_response])

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await conn.start()
            with pytest.raises(AxleValidationError):
                await conn.send_request("check", {"content": "test"})


class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_terminates_process(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "test-key")
        conn = AxleMcpConnection()

        init_response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        proc = _make_mock_process([init_response])

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await conn.start()
            await conn.shutdown()

        proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_kills_on_timeout(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "test-key")
        conn = AxleMcpConnection()

        init_response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        proc = _make_mock_process([init_response])
        proc.wait = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            await conn.start()
            await conn.shutdown()

        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_noop_when_no_process(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "test-key")
        conn = AxleMcpConnection()
        await conn.shutdown()  # Should not raise


class TestContextManager:
    @pytest.mark.asyncio
    async def test_async_context_manager(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "test-key")

        init_response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        proc = _make_mock_process([init_response])

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            async with AxleMcpConnection() as conn:
                assert conn._process is not None

        proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_shuts_down_on_exception(self, monkeypatch):
        monkeypatch.setenv("AXLE_API_KEY", "test-key")

        init_response = {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}}
        proc = _make_mock_process([init_response])

        with pytest.raises(RuntimeError):
            with patch("asyncio.create_subprocess_exec", return_value=proc):
                async with AxleMcpConnection() as _conn:
                    raise RuntimeError("test error")

        proc.terminate.assert_called_once()


class TestImport:
    def test_importable_from_mcp_client(self):
        from formalconstruct.mcp_client import AxleMcpConnection as Cls

        assert Cls is not None

    def test_importable_from_connection_module(self):
        from formalconstruct.mcp_client.connection import AxleMcpConnection as Cls

        assert Cls is not None
