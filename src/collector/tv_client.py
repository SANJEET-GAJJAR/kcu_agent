"""TradingView MCP client wrapper.

Wraps the tradingview-mcp Node.js server using the MCP stdio protocol.
Provides a clean async API with retry logic. No business logic here.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

log = logging.getLogger(__name__)

# Path to the tradingview-mcp server entry point, relative to project root.
_DEFAULT_SERVER_SCRIPT = (
    Path(__file__).parents[2] / "tradingview-mcp" / "src" / "server.js"
)

_DEFAULT_MAX_RETRIES = 3
_DEFAULT_RETRY_DELAY = 1.0  # seconds, doubles each attempt


class TVClientError(Exception):
    """Raised when a TradingView MCP call fails."""


class TradingViewClient:
    """Async MCP client for the tradingview-mcp server.

    Usage (async context manager):
        async with TradingViewClient() as client:
            result = await client.call_tool("chart_get_state", {})
    """

    def __init__(
        self,
        server_script: Path = _DEFAULT_SERVER_SCRIPT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        retry_delay: float = _DEFAULT_RETRY_DELAY,
    ) -> None:
        self._server_script = Path(server_script)
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._session: ClientSession | None = None
        self._exit_stack = None

    async def __aenter__(self) -> "TradingViewClient":
        await self._connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._disconnect()

    async def _connect(self) -> None:
        from contextlib import AsyncExitStack

        params = StdioServerParameters(
            command="node",
            args=[str(self._server_script)],
        )
        self._exit_stack = AsyncExitStack()
        read, write = await self._exit_stack.enter_async_context(
            stdio_client(params)
        )
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()
        log.debug("Connected to tradingview-mcp server")

    async def _disconnect(self) -> None:
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._session = None
        log.debug("Disconnected from tradingview-mcp server")

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a TradingView MCP tool with retry logic.

        Returns the parsed result value on success.
        Raises TVClientError on failure after all retries.
        """
        if self._session is None:
            raise TVClientError("Client is not connected. Use as async context manager.")

        last_error: Exception | None = None
        delay = self._retry_delay

        for attempt in range(1, self._max_retries + 1):
            try:
                result = await self._session.call_tool(name, arguments or {})

                # MCP returns a list of content items; the first is usually text JSON.
                if result.isError:
                    error_text = _extract_text(result.content)
                    raise TVClientError(f"Tool {name!r} returned error: {error_text}")

                return _parse_result(result.content)

            except TVClientError:
                raise  # Don't retry on tool-level errors (e.g. invalid args)
            except Exception as exc:
                last_error = exc
                if attempt < self._max_retries:
                    log.warning(
                        "Tool %r attempt %d/%d failed: %s — retrying in %.1fs",
                        name, attempt, self._max_retries, exc, delay,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 30.0)
                else:
                    log.error("Tool %r failed after %d attempts: %s", name, self._max_retries, exc)

        raise TVClientError(
            f"Tool {name!r} failed after {self._max_retries} attempts: {last_error}"
        )

    async def list_tools(self) -> list[str]:
        """Return names of all available tools on the server."""
        if self._session is None:
            raise TVClientError("Client is not connected.")
        result = await self._session.list_tools()
        return [t.name for t in result.tools]


def _extract_text(content: list) -> str:
    for item in content:
        if hasattr(item, "text"):
            return item.text
    return str(content)


def _parse_result(content: list) -> Any:
    """Extract the primary value from MCP content items."""
    import json

    for item in content:
        if hasattr(item, "text"):
            try:
                return json.loads(item.text)
            except (json.JSONDecodeError, TypeError):
                return item.text
    return content


@asynccontextmanager
async def open_client(
    server_script: Path = _DEFAULT_SERVER_SCRIPT,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> "TradingViewClient":
    """Convenience async context manager for one-off client use."""
    async with TradingViewClient(server_script=server_script, max_retries=max_retries) as client:
        yield client
