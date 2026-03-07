"""HERMES — Heterogeneous Event Routing for Multi-agent Ephemeral Sessions.

A lightweight, file-based communication protocol for multi-agent AI systems.
Inspired by TCP/IP. No servers, no databases — just files and convention.
"""

__version__ = "0.3.0-alpha"

from .message import (
    RELIABLE_TYPES,
    VALID_TYPES,
    Message,
    ValidationError,
    create_message,
    extract_cid,
    extract_re,
    transport_mode,
    validate_message,
)
from .bus import (
    ack_message,
    archive_expired,
    correlate,
    filter_for_namespace,
    find_expired,
    find_expired_unresolved,
    find_stale,
    find_unresolved,
    generate_escalation,
    read_bus,
    write_message,
)
from .sync import (
    FinAction,
    SynResult,
    fin,
    syn,
    syn_report,
)
from .config import (
    GatewayConfig,
    PeerConfig,
    init_clan,
    load_config,
    save_config,
)
from .agora import AgoraDirectory
from .dojo import (
    Dojo,
    Plane,
    Quest,
    QuestStatus,
    QuestType,
    SkillAvailability,
    SkillProfile,
)

__all__ = [
    # Core types
    "Message",
    "ValidationError",
    "SynResult",
    "FinAction",
    # Message operations
    "create_message",
    "validate_message",
    "transport_mode",
    "extract_cid",
    "extract_re",
    # Bus operations
    "read_bus",
    "write_message",
    "ack_message",
    "filter_for_namespace",
    "find_stale",
    "find_expired",
    "find_unresolved",
    "find_expired_unresolved",
    "correlate",
    "generate_escalation",
    "archive_expired",
    # Session operations
    "syn",
    "syn_report",
    "fin",
    # Constants
    "RELIABLE_TYPES",
    "VALID_TYPES",
    # Configuration
    "GatewayConfig",
    "PeerConfig",
    "init_clan",
    "load_config",
    "save_config",
    # Agora
    "AgoraDirectory",
    # Dojo (Orchestration Plane)
    "Dojo",
    "Plane",
    "Quest",
    "QuestStatus",
    "QuestType",
    "SkillAvailability",
    "SkillProfile",
]
