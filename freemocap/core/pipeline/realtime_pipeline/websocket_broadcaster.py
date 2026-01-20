"""
WebSocket broadcaster for use within subprocesses.

Runs a WebSocket server in a background thread and provides a simple
interface to broadcast messages to all connected clients.
"""

import asyncio
import json
import logging
import threading
from typing import Set, Optional, Any

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
except ImportError:
    websockets = None

logger = logging.getLogger(__name__)


class WebSocketBroadcaster:
    """
    WebSocket server that runs in a background thread and broadcasts messages.

    Designed for use within subprocesses where the main loop is synchronous.

    Usage:
        broadcaster = WebSocketBroadcaster(host="localhost", port=8765)
        broadcaster.start()

        # In your main loop:
        broadcaster.broadcast({"frame": 0, "data": [...]})

        # On shutdown:
        broadcaster.stop()
    """

    def __init__(self, host: str = "localhost", port: int = 8765):
        """
        Initialize the broadcaster.

        Args:
            host: Host address to bind the WebSocket server
            port: Port number for the WebSocket server
        """
        if websockets is None:
            raise ImportError("websockets library not installed. Install with: pip install websockets")

        self.host = host
        self.port = port
        self._clients: Set[WebSocketServerProtocol] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._server = None

    @property
    def client_count(self) -> int:
        """Return the number of connected clients."""
        return len(self._clients)

    @property
    def has_clients(self) -> bool:
        """Check if there are any connected clients."""
        return len(self._clients) > 0

    async def _register(self, websocket: WebSocketServerProtocol):
        """Register a new client connection."""
        self._clients.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self._clients)}")

    async def _unregister(self, websocket: WebSocketServerProtocol):
        """Unregister a client connection."""
        self._clients.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self._clients)}")

    async def _handler(self, websocket: WebSocketServerProtocol):
        """Handle a client WebSocket connection."""
        await self._register(websocket)
        try:
            async for message in websocket:
                # Handle any incoming messages (for future use)
                pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self._unregister(websocket)

    async def _broadcast_async(self, message: str):
        """Broadcast a message to all connected clients (async)."""
        if not self._clients:
            return

        disconnected = set()
        for client in self._clients.copy():
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
            except Exception as e:
                logger.warning(f"Error sending to client: {e}")
                disconnected.add(client)

        for client in disconnected:
            await self._unregister(client)

    async def _run_server(self):
        """Run the WebSocket server."""
        logger.info(f"Starting WebSocket server on ws://{self.host}:{self.port}")

        async with websockets.serve(self._handler, self.host, self.port) as server:
            self._server = server
            logger.info("WebSocket server started. Waiting for connections...")

            while self._running:
                await asyncio.sleep(0.1)

    def _thread_target(self):
        """Target function for the background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._run_server())
        except Exception as e:
            logger.error(f"WebSocket server error: {e}")
        finally:
            self._loop.close()
            logger.info("WebSocket server thread stopped")

    def start(self):
        """Start the WebSocket server in a background thread."""
        if self._running:
            logger.warning("WebSocket broadcaster already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._thread_target, daemon=True)
        self._thread.start()
        logger.info("WebSocket broadcaster started")

    def stop(self):
        """Stop the WebSocket server."""
        if not self._running:
            return

        logger.info("Stopping WebSocket broadcaster...")
        self._running = False

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        logger.info("WebSocket broadcaster stopped")

    def broadcast(self, data: Any):
        """
        Broadcast data to all connected clients.

        Args:
            data: Data to broadcast. Can be a dict, list, or string.
                  Dicts and lists will be JSON-encoded.
        """
        if not self._running or not self._loop:
            return

        if not self.has_clients:
            return

        # Convert to JSON string if needed
        if isinstance(data, (dict, list)):
            message = json.dumps(data)
        else:
            message = str(data)

        # Schedule the broadcast on the event loop
        asyncio.run_coroutine_threadsafe(
            self._broadcast_async(message),
            self._loop
        )

    def broadcast_json(self, json_string: str):
        """
        Broadcast a pre-formatted JSON string to all connected clients.

        Args:
            json_string: JSON string to broadcast as-is
        """
        if not self._running or not self._loop:
            return

        if not self.has_clients:
            return

        asyncio.run_coroutine_threadsafe(
            self._broadcast_async(json_string),
            self._loop
        )
