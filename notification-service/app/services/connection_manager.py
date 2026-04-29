import logging
from collections import defaultdict
from fastapi import WebSocket

logger = logging.getLogger("connection_manager")


class ConnectionManager:
    """
    Unified WebSocket manager — one socket per user handles both
    personal notifications and thread-level live updates.

    Each socket can subscribe to one or more thread rooms via messages.
    """

    def __init__(self):
        # user_id → list of sockets for that user
        self.user_connections: dict[int, list[WebSocket]] = defaultdict(list)
        # thread_id → set of sockets watching that thread
        self.thread_subscriptions: dict[int, set[WebSocket]] = defaultdict(set)
        # reverse lookup: socket → set of thread_ids it is subscribed to
        self._socket_threads: dict[WebSocket, set[int]] = defaultdict(set)

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.user_connections[user_id].append(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket):
        # Remove from user connections
        if user_id in self.user_connections and websocket in self.user_connections[user_id]:
            self.user_connections[user_id].remove(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        # Remove all thread subscriptions for this socket
        for thread_id in self._socket_threads.pop(websocket, set()):
            self.thread_subscriptions[thread_id].discard(websocket)
            if not self.thread_subscriptions[thread_id]:
                del self.thread_subscriptions[thread_id]

    def subscribe_thread(self, websocket: WebSocket, thread_id: int):
        self.thread_subscriptions[thread_id].add(websocket)
        self._socket_threads[websocket].add(thread_id)
        logger.info("Socket subscribed to thread %s", thread_id)

    def unsubscribe_thread(self, websocket: WebSocket, thread_id: int):
        self.thread_subscriptions[thread_id].discard(websocket)
        if not self.thread_subscriptions[thread_id]:
            del self.thread_subscriptions[thread_id]
        self._socket_threads.get(websocket, set()).discard(thread_id)
        logger.info("Socket unsubscribed from thread %s", thread_id)

    async def send_to_user(self, user_id: int, message):
        stale: list[WebSocket] = []
        for ws in self.user_connections.get(user_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                logger.warning("Stale WS for user_id=%s, removing", user_id)
                stale.append(ws)
        for ws in stale:
            # find user_id for this socket to disconnect properly
            self.disconnect(user_id, ws)

    async def send_to_thread(self, thread_id: int, message):
        stale: list[WebSocket] = []
        for ws in list(self.thread_subscriptions.get(thread_id, set())):
            try:
                await ws.send_json(message)
            except Exception:
                logger.warning("Stale thread WS for thread_id=%s, removing", thread_id)
                stale.append(ws)
        for ws in stale:
            self.thread_subscriptions[thread_id].discard(ws)
            self._socket_threads.get(ws, set()).discard(thread_id)

manager = ConnectionManager()