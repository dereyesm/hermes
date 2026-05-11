"""Master conftest — QUEST-CROSS-002 bilateral test fixtures.

Imports and re-exports all fixtures for use in test_*.py files.
Session-scoped keypairs + function-scoped sessions and frames.
"""

import uuid

import pytest

from .crypto_fixtures import (  # noqa: F401
    HKDF_INFO,
    ed25519_keypair_dani,
    ed25519_keypair_jei,
    old_session_key,
    session_key,
    shared_secret_bilateral,
    sign_test_frame,
    verify_test_frame,
    x25519_keypair_dani,
    x25519_keypair_jei,
)
from .hub_fixtures import (  # noqa: F401
    MockRouter,
    MockStoreForwardQueue,
    hub_queue,
    hub_router,
    mock_connections,
)
from .message_fixtures import (  # noqa: F401
    frame_auth,
    frame_auth_ok,
    frame_challenge,
    frame_delivered_receipt,
    frame_fake_sender,
    frame_hello,
    frame_message,
    frame_offline_queue,
    frame_queued_receipt,
    frame_replay,
    frame_sent_receipt,
    frame_unknown_channel,
)
from .session_fixtures import (  # noqa: F401
    MockSession,
    SessionState,
    active_session,
    fresh_session,
    mock_session_table,
)


@pytest.fixture(scope="function")
def bilateral_session_id() -> str:
    """Unique session ID for each test function."""
    return str(uuid.uuid4())


@pytest.fixture(scope="function")
def bilateral_session(active_session, mock_connections, hub_queue):  # noqa: F811
    """Pre-established bilateral session in ACTIVE state with router wired."""
    router = MockRouter(connections=mock_connections, queue=hub_queue)
    return {
        "session": active_session,
        "session_id": active_session.session_id,
        "router": router,
        "queue": hub_queue,
        "connections": mock_connections,
    }
