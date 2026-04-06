"""Tests for token telemetry — real-time LLM usage monitoring."""

from __future__ import annotations

import json

import pytest

from amaru.llm.adapters import LLMResponse
from amaru.llm.telemetry import (
    COST_PER_MTOK,
    BackendUsage,
    TokenEvent,
    TokenSummary,
    TokenTracker,
    estimate_cost,
)

# ─── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def response_claude():
    return LLMResponse(
        text="Hello",
        backend="claude",
        model="claude-sonnet-4-6",
        usage={"input_tokens": 1000, "output_tokens": 500},
    )


@pytest.fixture
def response_gemini():
    return LLMResponse(
        text="Hi",
        backend="gemini",
        model="gemini-2.5-flash",
        usage={"input_tokens": 2000, "output_tokens": 800},
    )


@pytest.fixture
def response_no_usage():
    return LLMResponse(text="Nope", backend="claude", model="claude-haiku-4-5", usage=None)


@pytest.fixture
def tracker(tmp_path):
    return TokenTracker(file_path=tmp_path / "telemetry.jsonl", session_id="test-session")


# ─── Cost estimation ─────────────────────────────────────────────


class TestEstimateCost:
    def test_known_model(self):
        cost = estimate_cost("claude-sonnet-4-6", 1_000_000, 1_000_000)
        assert cost == pytest.approx(3.0 + 15.0)

    def test_unknown_model_returns_zero(self):
        assert estimate_cost("unknown-model-99", 1000, 500) == 0.0

    def test_zero_tokens(self):
        assert estimate_cost("claude-sonnet-4-6", 0, 0) == 0.0

    def test_custom_cost_table(self):
        custom = {"my-model": {"input": 10.0, "output": 20.0}}
        cost = estimate_cost("my-model", 1_000_000, 1_000_000, cost_table=custom)
        assert cost == pytest.approx(30.0)

    def test_gemini_flash_cheap(self):
        cost = estimate_cost("gemini-2.5-flash", 100_000, 50_000)
        assert cost < 0.05  # very cheap model


# ─── TokenEvent ──────────────────────────────────────────────────


class TestTokenEvent:
    def test_to_dict(self, response_claude, tracker):
        event = tracker.record(response_claude)
        d = event.to_dict()
        assert d["backend"] == "claude"
        assert d["model"] == "claude-sonnet-4-6"
        assert d["in"] == 1000
        assert d["out"] == 500
        assert d["total"] == 1500
        assert d["cost"] > 0
        assert d["sid"] == "test-session"

    def test_to_jsonl(self, response_claude, tracker):
        event = tracker.record(response_claude)
        line = event.to_jsonl()
        parsed = json.loads(line)
        assert parsed["backend"] == "claude"
        assert parsed["in"] == 1000

    def test_from_dict_roundtrip(self, response_claude, tracker):
        event = tracker.record(response_claude)
        d = event.to_dict()
        restored = TokenEvent.from_dict(d)
        assert restored.backend == event.backend
        assert restored.input_tokens == event.input_tokens
        assert restored.output_tokens == event.output_tokens
        assert restored.total_tokens == event.total_tokens

    def test_optional_fields_omitted(self):
        event = TokenEvent(
            timestamp="2026-04-01T00:00:00+00:00",
            backend="gemini",
            model="gemini-2.5-flash",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
        )
        d = event.to_dict()
        assert "sid" not in d
        assert "cid" not in d


# ─── TokenTracker record ─────────────────────────────────────────


class TestTokenTrackerRecord:
    def test_record_creates_event(self, tracker, response_claude):
        event = tracker.record(response_claude)
        assert event.backend == "claude"
        assert event.input_tokens == 1000
        assert event.output_tokens == 500
        assert event.total_tokens == 1500
        assert event.cost_usd > 0

    def test_record_no_usage(self, tracker, response_no_usage):
        event = tracker.record(response_no_usage)
        assert event.input_tokens == 0
        assert event.output_tokens == 0
        assert event.total_tokens == 0
        assert event.cost_usd == 0.0

    def test_record_with_correlation_id(self, tracker, response_claude):
        event = tracker.record(response_claude, correlation_id="req-42")
        assert event.correlation_id == "req-42"

    def test_events_accumulate(self, tracker, response_claude, response_gemini):
        tracker.record(response_claude)
        tracker.record(response_gemini)
        assert len(tracker.events) == 2

    def test_session_id_attached(self, tracker, response_claude):
        event = tracker.record(response_claude)
        assert event.session_id == "test-session"


# ─── TokenTracker persistence ────────────────────────────────────


class TestTokenTrackerPersistence:
    def test_auto_flush_writes_file(self, tracker, response_claude):
        tracker.record(response_claude)
        assert tracker.file_path.exists()
        lines = tracker.file_path.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["backend"] == "claude"

    def test_multiple_records_append(self, tracker, response_claude, response_gemini):
        tracker.record(response_claude)
        tracker.record(response_gemini)
        lines = tracker.file_path.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_manual_flush(self, tmp_path, response_claude):
        tracker = TokenTracker(
            file_path=tmp_path / "manual.jsonl",
            auto_flush=False,
        )
        tracker.record(response_claude)
        assert not (tmp_path / "manual.jsonl").exists()
        flushed = tracker.flush()
        assert flushed == 1
        assert (tmp_path / "manual.jsonl").exists()

    def test_load_from_file(self, tracker, response_claude, response_gemini):
        tracker.record(response_claude)
        tracker.record(response_gemini)

        # Create new tracker and load from same file
        tracker2 = TokenTracker(file_path=tracker.file_path)
        loaded = tracker2.load_from_file()
        assert loaded == 2
        assert len(tracker2.events) == 2
        assert tracker2.events[0].backend == "claude"
        assert tracker2.events[1].backend == "gemini"

    def test_load_skips_bad_lines(self, tmp_path):
        log = tmp_path / "bad.jsonl"
        log.write_text(
            '{"ts":"x","backend":"y","model":"z","in":1,"out":2,"total":3,"cost":0}\n{bad json}\n'
        )
        tracker = TokenTracker(file_path=log)
        loaded = tracker.load_from_file()
        assert loaded == 1

    def test_memory_only_tracker(self, response_claude):
        tracker = TokenTracker()  # no file_path
        event = tracker.record(response_claude)
        assert event.backend == "claude"
        assert len(tracker.events) == 1

    def test_reset_clears_events(self, tracker, response_claude):
        tracker.record(response_claude)
        assert len(tracker.events) == 1
        tracker.reset()
        assert len(tracker.events) == 0

    def test_reset_file(self, tracker, response_claude):
        tracker.record(response_claude)
        assert tracker.file_path.exists()
        tracker.reset_file()
        assert tracker.file_path.read_text() == ""


# ─── TokenTracker summary ────────────────────────────────────────


class TestTokenTrackerSummary:
    def test_summary_basic(self, tracker, response_claude, response_gemini):
        tracker.record(response_claude)
        tracker.record(response_gemini)
        s = tracker.summary()
        assert s.total_input == 3000
        assert s.total_output == 1300
        assert s.total_tokens == 4300
        assert s.event_count == 2
        assert s.total_cost_usd > 0

    def test_summary_by_backend(self, tracker, response_claude, response_gemini):
        tracker.record(response_claude)
        tracker.record(response_gemini)
        s = tracker.summary()
        assert "claude" in s.by_backend
        assert "gemini" in s.by_backend
        assert s.by_backend["claude"].input_tokens == 1000
        assert s.by_backend["gemini"].input_tokens == 2000

    def test_summary_by_model(self, tracker, response_claude, response_gemini):
        tracker.record(response_claude)
        tracker.record(response_gemini)
        s = tracker.summary()
        assert "claude-sonnet-4-6" in s.by_model
        assert "gemini-2.5-flash" in s.by_model

    def test_summary_filter_backend(self, tracker, response_claude, response_gemini):
        tracker.record(response_claude)
        tracker.record(response_gemini)
        s = tracker.summary(backend="claude")
        assert s.event_count == 1
        assert s.total_input == 1000

    def test_summary_filter_since(self, tracker, response_claude):
        tracker.record(response_claude)
        # Filter with future date — should get 0 events
        s = tracker.summary(since="2099-01-01")
        assert s.event_count == 0

    def test_summary_empty(self, tracker):
        s = tracker.summary()
        assert s.event_count == 0
        assert s.total_tokens == 0
        assert s.first_event is None
        assert s.last_event is None

    def test_summary_timestamps(self, tracker, response_claude, response_gemini):
        tracker.record(response_claude)
        tracker.record(response_gemini)
        s = tracker.summary()
        assert s.first_event is not None
        assert s.last_event is not None


# ─── COST_PER_MTOK table ─────────────────────────────────────────


class TestCostTable:
    def test_has_major_models(self):
        assert "claude-opus-4-6" in COST_PER_MTOK
        assert "claude-sonnet-4-6" in COST_PER_MTOK
        assert "claude-haiku-4-5" in COST_PER_MTOK
        assert "gemini-2.5-pro" in COST_PER_MTOK
        assert "gemini-2.5-flash" in COST_PER_MTOK
        assert "gpt-4o" in COST_PER_MTOK
        assert "gpt-4o-mini" in COST_PER_MTOK

    def test_all_have_input_output(self):
        for model, rates in COST_PER_MTOK.items():
            assert "input" in rates, f"{model} missing input rate"
            assert "output" in rates, f"{model} missing output rate"
            assert rates["input"] >= 0
            assert rates["output"] >= 0

    def test_opus_most_expensive(self):
        opus = COST_PER_MTOK["claude-opus-4-6"]
        for model, rates in COST_PER_MTOK.items():
            if model != "claude-opus-4-6" and model != "o1":
                assert rates["output"] <= opus["output"]


# ─── BackendUsage / TokenSummary dataclasses ──────────────────────


class TestDataclasses:
    def test_backend_usage_defaults(self):
        bu = BackendUsage()
        assert bu.input_tokens == 0
        assert bu.cost_usd == 0.0
        assert bu.event_count == 0

    def test_token_summary_defaults(self):
        ts = TokenSummary()
        assert ts.total_tokens == 0
        assert ts.by_backend == {}
        assert ts.by_model == {}
