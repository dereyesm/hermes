"""Token telemetry — real-time monitoring of LLM token usage across providers.

Tracks input/output tokens, estimates cost, persists to JSONL, and produces
aggregated summaries by backend and model. Designed for integration with the
HERMES AdapterManager so every LLM call is automatically instrumented.

Usage::

    tracker = TokenTracker(file_path=Path("~/.hermes/telemetry.jsonl"))
    event = tracker.record(llm_response)
    summary = tracker.summary()
    print(f"Total: {summary.total_tokens} tokens, ${summary.total_cost_usd:.4f}")

The module ships with a ``COST_PER_MTOK`` table covering Claude, Gemini,
and OpenAI models.  Override or extend it via ``TokenTracker.cost_table``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .adapters import LLMResponse


# ---------------------------------------------------------------------------
# Cost table — USD per 1 million tokens (input / output)
# ---------------------------------------------------------------------------

COST_PER_MTOK: dict[str, dict[str, float]] = {
    # Claude (Anthropic)
    "claude-opus-4-6": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.00},
    # Gemini (Google)
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "o1": {"input": 15.00, "output": 60.00},
    "o3-mini": {"input": 1.10, "output": 4.40},
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TokenEvent:
    """A single LLM call with token counts and estimated cost."""

    timestamp: str
    backend: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    session_id: str | None = None
    correlation_id: str | None = None

    def to_dict(self) -> dict:
        """Compact dict for JSONL serialization."""
        d: dict = {
            "ts": self.timestamp,
            "backend": self.backend,
            "model": self.model,
            "in": self.input_tokens,
            "out": self.output_tokens,
            "total": self.total_tokens,
            "cost": round(self.cost_usd, 6),
        }
        if self.session_id:
            d["sid"] = self.session_id
        if self.correlation_id:
            d["cid"] = self.correlation_id
        return d

    def to_jsonl(self) -> str:
        """Single JSONL line (no trailing newline)."""
        return (
            json.dumps(self.to_dict, ensure_ascii=False)
            if False
            else json.dumps(self.to_dict(), ensure_ascii=False)
        )

    @classmethod
    def from_dict(cls, d: dict) -> TokenEvent:
        """Parse from compact dict."""
        return cls(
            timestamp=d.get("ts", ""),
            backend=d.get("backend", ""),
            model=d.get("model", ""),
            input_tokens=d.get("in", 0),
            output_tokens=d.get("out", 0),
            total_tokens=d.get("total", 0),
            cost_usd=d.get("cost", 0.0),
            session_id=d.get("sid"),
            correlation_id=d.get("cid"),
        )


@dataclass
class BackendUsage:
    """Aggregated usage for a single backend or model."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    event_count: int = 0


@dataclass
class TokenSummary:
    """Aggregated token usage summary across all events."""

    total_input: int = 0
    total_output: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    by_backend: dict[str, BackendUsage] = field(default_factory=dict)
    by_model: dict[str, BackendUsage] = field(default_factory=dict)
    event_count: int = 0
    first_event: str | None = None
    last_event: str | None = None


# ---------------------------------------------------------------------------
# Token Tracker
# ---------------------------------------------------------------------------


def estimate_cost(
    model: str, input_tokens: int, output_tokens: int, cost_table: dict | None = None
) -> float:
    """Estimate USD cost for a single LLM call.

    Looks up the model in the cost table. Returns 0.0 if model is unknown.
    """
    table = cost_table or COST_PER_MTOK
    rates = table.get(model)
    if rates is None:
        return 0.0
    input_cost = (input_tokens / 1_000_000) * rates.get("input", 0)
    output_cost = (output_tokens / 1_000_000) * rates.get("output", 0)
    return input_cost + output_cost


class TokenTracker:
    """Tracks token usage across LLM calls with optional JSONL persistence.

    Args:
        file_path: Path to append telemetry events as JSONL. None = memory only.
        cost_table: Override cost-per-million-tokens table.
        session_id: Tag all events with this session identifier.
        auto_flush: If True (default), append to file immediately on record().
    """

    def __init__(
        self,
        file_path: Path | None = None,
        cost_table: dict[str, dict[str, float]] | None = None,
        session_id: str | None = None,
        auto_flush: bool = True,
    ) -> None:
        self.file_path = file_path
        self.cost_table = cost_table or COST_PER_MTOK
        self.session_id = session_id
        self.auto_flush = auto_flush
        self._events: list[TokenEvent] = []
        self._buffer: list[TokenEvent] = []  # unflushed events

    def record(self, response: LLMResponse, correlation_id: str | None = None) -> TokenEvent:
        """Record token usage from an LLMResponse.

        Returns the created TokenEvent.
        """
        usage = response.usage or {}
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total = input_tokens + output_tokens
        cost = estimate_cost(response.model, input_tokens, output_tokens, self.cost_table)

        event = TokenEvent(
            timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
            backend=response.backend,
            model=response.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            cost_usd=cost,
            session_id=self.session_id,
            correlation_id=correlation_id,
        )

        self._events.append(event)

        if self.auto_flush and self.file_path:
            self._append_to_file(event)
        elif self.file_path:
            self._buffer.append(event)

        return event

    def flush(self) -> int:
        """Write buffered events to file. Returns count of flushed events."""
        if not self.file_path or not self._buffer:
            return 0
        count = len(self._buffer)
        for event in self._buffer:
            self._append_to_file(event)
        self._buffer.clear()
        return count

    def summary(self, backend: str | None = None, since: str | None = None) -> TokenSummary:
        """Aggregate token usage from recorded events.

        Args:
            backend: Filter to a specific backend (e.g. "claude", "gemini").
            since: ISO date string — only include events on or after this date.
        """
        events = self._get_filtered_events(backend, since)

        s = TokenSummary()
        for e in events:
            s.total_input += e.input_tokens
            s.total_output += e.output_tokens
            s.total_tokens += e.total_tokens
            s.total_cost_usd += e.cost_usd
            s.event_count += 1

            # By backend
            bu = s.by_backend.setdefault(e.backend, BackendUsage())
            bu.input_tokens += e.input_tokens
            bu.output_tokens += e.output_tokens
            bu.total_tokens += e.total_tokens
            bu.cost_usd += e.cost_usd
            bu.event_count += 1

            # By model
            mu = s.by_model.setdefault(e.model, BackendUsage())
            mu.input_tokens += e.input_tokens
            mu.output_tokens += e.output_tokens
            mu.total_tokens += e.total_tokens
            mu.cost_usd += e.cost_usd
            mu.event_count += 1

        if events:
            s.first_event = events[0].timestamp
            s.last_event = events[-1].timestamp

        return s

    def load_from_file(self, path: Path | None = None) -> int:
        """Load historical events from a JSONL file. Returns count loaded."""
        target = path or self.file_path
        if target is None or not target.exists():
            return 0

        count = 0
        for line in target.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                self._events.append(TokenEvent.from_dict(d))
                count += 1
            except (json.JSONDecodeError, KeyError):
                continue
        return count

    def reset(self) -> None:
        """Clear all in-memory events and buffer."""
        self._events.clear()
        self._buffer.clear()

    def reset_file(self) -> None:
        """Clear the telemetry file on disk."""
        if self.file_path and self.file_path.exists():
            self.file_path.write_text("", encoding="utf-8")

    @property
    def events(self) -> list[TokenEvent]:
        """All recorded events (read-only view)."""
        return list(self._events)

    def _get_filtered_events(self, backend: str | None, since: str | None) -> list[TokenEvent]:
        events = self._events
        if backend:
            events = [e for e in events if e.backend == backend]
        if since:
            events = [e for e in events if e.timestamp >= since]
        return events

    def _append_to_file(self, event: TokenEvent) -> None:
        assert self.file_path is not None
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with self.file_path.open("a", encoding="utf-8") as f:
            f.write(event.to_jsonl() + "\n")
