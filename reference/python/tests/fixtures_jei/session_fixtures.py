"""Session state machine fixtures — QUEST-CROSS-002 bilateral tests."""

import time
import uuid
from enum import Enum, auto

import pytest


class SessionState(Enum):
    HELLO_SENT = auto()
    CHALLENGED = auto()
    AUTH_OK = auto()
    ACTIVE = auto()
    CLOSED = auto()


_VALID_TRANSITIONS = {
    SessionState.HELLO_SENT: [SessionState.CHALLENGED],
    SessionState.CHALLENGED: [SessionState.AUTH_OK],
    SessionState.AUTH_OK: [SessionState.ACTIVE],
    SessionState.ACTIVE: [SessionState.CLOSED],
    SessionState.CLOSED: [],
}


class MockSession:
    """Simulated session with state machine and timestamps."""

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.state = SessionState.HELLO_SENT
        self.established_at: float | None = None
        self.last_activity_at: float = time.time()
        self.peers: dict[str, str] = {}

    def transition(self, new_state: SessionState) -> None:
        allowed = _VALID_TRANSITIONS.get(self.state, [])
        if new_state not in allowed:
            raise ValueError(f"Invalid transition: {self.state} → {new_state}")
        self.state = new_state
        self.last_activity_at = time.time()
        if new_state == SessionState.ACTIVE:
            self.established_at = time.time()

    def is_active(self) -> bool:
        return self.state == SessionState.ACTIVE

    def touch(self) -> None:
        self.last_activity_at = time.time()


@pytest.fixture
def mock_session_table() -> dict[str, MockSession]:
    """Empty session table."""
    return {}


@pytest.fixture
def fresh_session() -> MockSession:
    """New session in HELLO_SENT state."""
    return MockSession()


@pytest.fixture
def active_session() -> MockSession:
    """Session fast-forwarded to ACTIVE state."""
    s = MockSession()
    s.transition(SessionState.CHALLENGED)
    s.transition(SessionState.AUTH_OK)
    s.transition(SessionState.ACTIVE)
    return s
