"""Conformance test placeholders for ARC-1122 levels.

Each test class corresponds to one conformance level. Tests are structured
as TODOs matching the normative statement IDs in spec/ARC-1122.md.

To run: python -m pytest tests/test_conformance.py -v
"""

import pytest


# ---------------------------------------------------------------------------
# Level 1: Bus-Compatible (26 normative statements)
# ---------------------------------------------------------------------------


class TestLevel1BusCompatible:
    """ARC-1122 Level 1 — Bus-Compatible conformance.

    An implementation claiming Level 1 MUST satisfy all L1 requirements:
    message format (ARC-5322), bus read/write (ARC-0793), and ACK protocol.
    """

    @pytest.mark.skip(reason="TODO: implement L1-01 through L1-26 test vectors")
    def test_l1_placeholder(self):
        """Placeholder — replace with individual L1-XX test methods."""
        # TODO: L1-01 through L1-26 from spec/ARC-1122.md §5
        # Each test should verify one normative MUST/SHOULD/MAY statement
        # against the reference implementation.
        #
        # Example structure:
        #   def test_l1_01_seven_field_message(self):
        #       msg = create_message(ts=..., src=..., dst=..., ...)
        #       assert validate_message(msg) is True
        #
        #   def test_l1_05_ttl_positive_integer(self):
        #       with pytest.raises(ValidationError):
        #           create_message(ttl=-1, ...)
        pass


# ---------------------------------------------------------------------------
# Level 2: Clan-Ready (33 normative statements, includes L1)
# ---------------------------------------------------------------------------


class TestLevel2ClanReady:
    """ARC-1122 Level 2 — Clan-Ready conformance.

    An implementation claiming Level 2 MUST satisfy all L1 + L2 requirements:
    sessions (ARC-0793), namespaces (ARC-1918), gateway (ARC-3022),
    agent service platform (ARC-0369), and bus integrity (ARC-9001).
    """

    @pytest.mark.skip(reason="TODO: implement L2-01 through L2-33 test vectors")
    def test_l2_placeholder(self):
        """Placeholder — replace with individual L2-XX test methods."""
        # TODO: L2-01 through L2-33 from spec/ARC-1122.md §6
        pass


# ---------------------------------------------------------------------------
# Level 3: Network-Ready (39 normative statements, includes L1+L2)
# ---------------------------------------------------------------------------


class TestLevel3NetworkReady:
    """ARC-1122 Level 3 — Network-Ready conformance.

    An implementation claiming Level 3 MUST satisfy all L1 + L2 + L3 requirements:
    cryptography (ARC-8446), hub mode (ARC-4601), bridge (ARC-7231),
    and Agora discovery (ARC-1337).
    """

    @pytest.mark.skip(reason="TODO: implement L3-01 through L3-39 test vectors")
    def test_l3_placeholder(self):
        """Placeholder — replace with individual L3-XX test methods."""
        # TODO: L3-01 through L3-39 from spec/ARC-1122.md §7
        pass
