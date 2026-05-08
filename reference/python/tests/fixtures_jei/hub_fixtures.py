"""Hub mock fixtures — QUEST-CROSS-002 bilateral tests.

Replicates StoreForwardQueue and MessageRouter APIs from amaru/hub.py.
"""
import time
from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class QueuedMessage:
    payload: dict
    queued_at: float = field(default_factory=time.time)
    ttl_seconds: int = 604800

    def is_expired(self) -> bool:
        return time.time() - self.queued_at > self.ttl_seconds


class MockStoreForwardQueue:
    """Replica of StoreForwardQueue — per-peer FIFO with cap."""

    def __init__(self, max_depth: int = 1000):
        self._queues: dict[str, list[QueuedMessage]] = {}
        self.max_depth = max_depth

    def enqueue(self, dst: str, payload: dict, ttl_seconds: int = 604800) -> bool:
        """Returns False if queue full (caller should notify sender)."""
        queue = self._queues.setdefault(dst, [])
        if len(queue) >= self.max_depth:
            return False
        queue.append(QueuedMessage(payload=payload, ttl_seconds=ttl_seconds))
        return True

    def drain(self, dst: str, batch_size: int = 100) -> tuple[list[dict], int]:
        queue = self._queues.get(dst, [])
        batch = [m.payload for m in queue[:batch_size]]
        self._queues[dst] = queue[batch_size:]
        return batch, len(self._queues[dst])

    def depth(self, dst: str) -> int:
        return len(self._queues.get(dst, []))

    def total_depth(self) -> int:
        return sum(len(q) for q in self._queues.values())

    def clear(self, dst: str) -> None:
        self._queues.pop(dst, None)


class MockRouter:
    """Synchronous mock of MessageRouter for unit tests."""

    def __init__(self, connections: dict, queue: MockStoreForwardQueue):
        self._connections = connections
        self._queue = queue
        self.routing_log: list[dict] = []
        self.total_routed = 0

    def route(self, payload: dict, sender: str) -> dict:
        """Route a message synchronously. Returns status dict."""
        dst = payload.get("dst", "")
        self.total_routed += 1
        log_entry = {"dst": dst, "sender": sender, "ts": time.time(), "payload": payload}

        if dst in self._connections:
            self.routing_log.append({**log_entry, "result": "delivered"})
            return {"status": "delivered", "dst": dst}
        else:
            ok = self._queue.enqueue(dst, payload, payload.get("ttl", 604800))
            result = "queued" if ok else "queue_full"
            self.routing_log.append({**log_entry, "result": result})
            return {"status": result, "dst": dst}


@pytest.fixture
def hub_queue() -> MockStoreForwardQueue:
    """Empty StoreForwardQueue with default depth."""
    return MockStoreForwardQueue(max_depth=1000)


@pytest.fixture
def mock_connections() -> dict:
    """Simulated active connections dict: {clan_id: mock_ws}."""
    return {"jei": object(), "dani": object()}


@pytest.fixture
def hub_router(mock_connections, hub_queue) -> MockRouter:
    """MockRouter wired with mock connections and queue."""
    return MockRouter(connections=mock_connections, queue=hub_queue)
