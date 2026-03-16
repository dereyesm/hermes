#!/usr/bin/env python3
"""
L3 Channel Efficiency — Overhead Model
HERMES Research | ATR-G.711 supporting data

Compares per-message overhead across 5 communication protocols for the
HERMES use case: short agent-to-agent messages (<=120 chars payload) between
co-located or nearby agents.

Model methodology:
    For each protocol, we decompose the total cost of sending one message into:
    - Transport overhead: TCP (20B) + TLS 1.3 (22B) + IPv4 (20B) = 62B for network protocols
    - Application framing: HTTP request lines, headers, gRPC/MQTT framing
    - Format wrapper: JSON keys/structure, protobuf tags, etc.
    - Payload: the useful content (~120 bytes for a typical HERMES message)

    HERMES bus (file-based) has ZERO transport overhead because it operates via
    local file append — no network stack involved. This is the primary advantage
    for co-located agents (same host, same filesystem).

Assumptions (conservative, favoring alternatives where ambiguous):
    - HERMES format_wrapper measured from actual reference implementation output
      using Python json.dumps with default separators (spaces after : and ,),
      with typical 8-char namespace names (e.g., "momoshod", "nymyka")
    - HTTP/1.1: minimum realistic headers (Host, Content-Type, Authorization,
      Accept, Content-Length, User-Agent) — real APIs add X-Request-ID, CORS, etc.
    - HTTP/2 + gRPC: HPACK cold start shown (first request on connection).
      Subsequent requests amortize to ~20B headers via indexed references.
    - MQTT v5.0: QoS 1, topic "hermes/bus/momoshod" (~22 chars). Minimal properties.
    - TCP/TLS/IP overhead: 20 + 22 + 20 = 62 bytes per message (no connection reuse)
    - TLS 1.3: 5B record header + 1B content type + 16B AEAD tag = 22B (RFC 8446 S5.2)

Data sources:
    - ARC-5322 (HERMES Message Format) — actual JSON structure
    - RFC 9113 (HTTP/2), RFC 7540 (HPACK), RFC 8446 (TLS 1.3)
    - RFC 793 (TCP), RFC 791 (IPv4)
    - gRPC over HTTP/2 protocol spec (github.com/grpc/grpc/blob/master/doc/PROTOCOL-HTTP2.md)
    - MQTT v5.0 OASIS standard (Section 2.1, 3.3)

Usage:
    python3 overhead_model.py
    python3 overhead_model.py --payload-size 60
    python3 overhead_model.py --csv > results.csv
    python3 overhead_model.py --sweep
"""

import argparse
import json
import textwrap
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Actual HERMES message measurement
# ---------------------------------------------------------------------------

def measure_hermes_wrapper(payload_size: int = 120) -> int:
    """Measure the real wrapper overhead of a HERMES ARC-5322 message.

    Uses the reference implementation's serialization format (json.dumps with
    default separators) and typical namespace names.
    """
    msg = {
        "ts": "2026-03-15",
        "src": "momoshod",
        "dst": "nymyka",
        "type": "state",
        "msg": "x" * payload_size,
        "ttl": 7,
        "ack": [],
    }
    serialized = json.dumps(msg, ensure_ascii=False)
    return len(serialized) - payload_size  # wrapper = total - payload


# ---------------------------------------------------------------------------
# Protocol overhead model
# ---------------------------------------------------------------------------

@dataclass
class ProtocolModel:
    """Models the byte-level overhead of a single protocol."""
    name: str
    description: str

    # Transport layer (TCP + TLS + IP) — 0 for local file-based
    transport_bytes: int = 0

    # Application framing (HTTP request line, headers, MQTT headers, etc.)
    framing_bytes: int = 0

    # Format wrapper (JSON keys/structure, protobuf tags, etc.)
    format_wrapper_bytes: int = 0

    notes: str = ""

    @property
    def overhead_bytes(self) -> int:
        return self.transport_bytes + self.framing_bytes + self.format_wrapper_bytes

    def total_bytes(self, payload: int) -> int:
        return self.overhead_bytes + payload

    def overhead_pct(self, payload: int) -> float:
        t = self.total_bytes(payload)
        return (self.overhead_bytes / t * 100) if t > 0 else 0.0

    def efficiency_pct(self, payload: int) -> float:
        return 100.0 - self.overhead_pct(payload)


def build_protocols() -> list[ProtocolModel]:
    """Build the 5 protocol models with documented byte counts."""

    hermes_wrapper = measure_hermes_wrapper(120)  # ~105 bytes measured

    return [
        # 1. HERMES bus (local file append)
        ProtocolModel(
            name="HERMES bus (JSONL file)",
            description="Append one JSON line + newline to local bus file. No network.",
            transport_bytes=0,      # No network stack
            framing_bytes=1,        # The trailing newline character
            format_wrapper_bytes=hermes_wrapper,  # Measured: ~105B for typical namespaces
            notes=(
                f"Measured wrapper: {hermes_wrapper}B (json.dumps default separators, "
                f"8-char namespaces). Compact separators would save ~6B. "
                f"Zero transport overhead — pure file I/O."
            ),
        ),

        # 2. HTTP/1.1 REST (typical JSON API over HTTPS)
        ProtocolModel(
            name="HTTP/1.1 REST (HTTPS)",
            description="POST /api/v1/messages with JSON body, bearer auth, standard headers.",
            transport_bytes=62,     # TCP(20) + TLS1.3(22) + IPv4(20)
            framing_bytes=350,      # Request line + headers (see breakdown below)
            format_wrapper_bytes=65,  # JSON envelope: {"from":"X","to":"Y","body":"...","ts":"Z"}
            notes=(
                "Request line: 'POST /api/v1/messages HTTP/1.1\\r\\n' = 36B. "
                "Headers: Host(~30B) + Content-Type(32B) + Authorization(~80B) + "
                "Accept(26B) + Content-Length(20B) + User-Agent(~40B) + "
                "Connection(24B) + CRLFs(~62B) = ~314B. "
                "Real APIs add X-Request-ID, X-Trace-ID, CORS → even more overhead."
            ),
        ),

        # 3. HTTP/2 (HPACK compressed headers, no gRPC)
        ProtocolModel(
            name="HTTP/2 (HPACK, HTTPS)",
            description="HTTP/2 POST with HPACK-compressed headers. Cold start (first request).",
            transport_bytes=62,     # TCP(20) + TLS1.3(22) + IPv4(20)
            framing_bytes=109,      # HEADERS frame(9) + HPACK cold(~80) + DATA frame(9) + end(2)
            format_wrapper_bytes=65,  # Same JSON envelope as HTTP/1.1
            notes=(
                "HEADERS frame: 9B (RFC 9113 S4.1). "
                "HPACK cold start: ~80B (literal header fields with indexing). "
                "Subsequent requests: ~20B (indexed references — amortized). "
                "DATA frame: 9B header. "
                "For warm connections, total framing drops to ~40B."
            ),
        ),

        # 4. gRPC (HTTP/2 + protobuf + Length-Prefixed Message)
        ProtocolModel(
            name="gRPC (HTTP/2 + protobuf)",
            description="gRPC unary RPC: HTTP/2 + HPACK + protobuf framing. Cold start.",
            transport_bytes=62,     # TCP(20) + TLS1.3(22) + IPv4(20)
            framing_bytes=103,      # HEADERS(9) + HPACK(80) + DATA(9) + gRPC-LPM(5)
            format_wrapper_bytes=15,  # Protobuf: field tags(1B each) + varint lengths for ~5 fields
            notes=(
                "gRPC Length-Prefixed Message: 1B compressed-flag + 4B length = 5B. "
                "Protobuf wrapper: ~15B for 5 string fields (tag+len per field). "
                "Protobuf is more compact than JSON — but HTTP/2+HPACK overhead dominates. "
                "Warm connection amortizes HPACK to ~20B → total framing ~43B."
            ),
        ),

        # 5. MQTT v5.0 (lightweight pub/sub over TLS)
        ProtocolModel(
            name="MQTT v5.0 (TLS)",
            description="MQTT PUBLISH QoS 1. Topic: hermes/bus/momoshod. Broker required.",
            transport_bytes=62,     # TCP(20) + TLS1.3(22) + IPv4(20)
            framing_bytes=31,       # Fixed header(2) + variable header(29)
            format_wrapper_bytes=40,  # Minimal JSON or raw payload with metadata
            notes=(
                "Fixed header: 1B type+flags + 1B remaining length = 2B. "
                "Variable header: topic length(2B) + topic 'hermes/bus/momoshod'(22B) + "
                "packet ID(2B) + properties length(1B) + props(2B) = 29B. "
                "QoS 1 requires PUBACK from broker (+4B return). "
                "MQTT is the closest competitor for short messages — but requires a broker."
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Analysis engine
# ---------------------------------------------------------------------------

def analyze_single(protocols: list[ProtocolModel], payload: int) -> list[dict]:
    """Analyze all protocols for a given payload size."""
    results = []
    for p in protocols:
        results.append({
            "protocol": p.name,
            "payload_bytes": payload,
            "overhead_bytes": p.overhead_bytes,
            "total_bytes": p.total_bytes(payload),
            "overhead_pct": round(p.overhead_pct(payload), 1),
            "efficiency_pct": round(p.efficiency_pct(payload), 1),
            "transport": p.transport_bytes,
            "framing": p.framing_bytes,
            "format_wrapper": p.format_wrapper_bytes,
            "notes": p.notes,
        })
    return sorted(results, key=lambda x: x["overhead_pct"])


def analyze_cumulative(protocols: list[ProtocolModel], payload: int,
                       counts: list[int]) -> list[dict]:
    """Model cumulative overhead for N messages."""
    rows = []
    for n in counts:
        for p in protocols:
            total = p.total_bytes(payload) * n
            overhead = p.overhead_bytes * n
            useful = payload * n
            rows.append({
                "n": n,
                "protocol": p.name,
                "total_bytes": total,
                "overhead_bytes": overhead,
                "useful_bytes": useful,
                "overhead_pct": round(overhead / total * 100, 1) if total > 0 else 0,
                "wasted_kb": round(overhead / 1024, 1),
            })
    return rows


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def print_single_table(results: list[dict], payload: int) -> None:
    """Print the per-message comparison table."""
    w = 90
    print()
    print("=" * w)
    print("  L3 CHANNEL EFFICIENCY MODEL — HERMES vs Alternatives")
    print(f"  Payload: {payload} bytes (HERMES ARC-5322 message content)")
    print("=" * w)
    print()

    hdr = (f"  {'Protocol':<30} {'Overhead':>10} {'Total':>8} "
           f"{'Overhead%':>10} {'Efficiency':>11}")
    print(hdr)
    print("  " + "-" * (w - 4))

    for r in results:
        marker = " <<" if "HERMES bus" in r["protocol"] else ""
        print(
            f"  {r['protocol']:<30} "
            f"{r['overhead_bytes']:>7} B  "
            f"{r['total_bytes']:>5} B  "
            f"{r['overhead_pct']:>8.1f}%  "
            f"{r['efficiency_pct']:>9.1f}%"
            f"{marker}"
        )

    print("  " + "-" * (w - 4))
    print()

    # Key finding
    hermes = next(r for r in results if "HERMES bus" in r["protocol"])
    worst = max(results, key=lambda x: x["overhead_pct"])
    best_net = min(
        (r for r in results if "HERMES bus" not in r["protocol"]),
        key=lambda x: x["overhead_pct"],
    )

    print(f"  Key findings:")
    print(f"    HERMES bus (local):  {hermes['efficiency_pct']}% efficient "
          f"({hermes['overhead_bytes']}B overhead)")
    print(f"    Best network alt:    {best_net['protocol']} at "
          f"{best_net['efficiency_pct']}% efficient")
    print(f"    Worst:               {worst['protocol']} at "
          f"{worst['efficiency_pct']}% efficient")

    if hermes["overhead_pct"] > 0:
        ratio = worst["overhead_bytes"] / hermes["overhead_bytes"]
        print(f"    HERMES saves {ratio:.1f}x less overhead than "
              f"{worst['protocol'].split('(')[0].strip()}")
    print()


def print_cumulative_table(rows: list[dict], payload: int) -> None:
    """Print the N-message cumulative overhead table."""
    w = 90
    print("=" * w)
    print("  CUMULATIVE OVERHEAD — N messages at {0} bytes payload".format(payload))
    print("=" * w)
    print()

    counts = sorted(set(r["n"] for r in rows))
    protocols = []
    seen = set()
    for r in rows:
        if r["protocol"] not in seen:
            protocols.append(r["protocol"])
            seen.add(r["protocol"])

    # Header
    col_w = 14
    hdr = f"  {'Protocol':<30}"
    for n in counts:
        hdr += f" {'N=' + str(n):>{col_w}}"
    print(hdr)
    print("  " + "-" * (w - 4))

    # One row per protocol: show overhead bytes
    for pname in protocols:
        prows = {r["n"]: r for r in rows if r["protocol"] == pname}
        line = f"  {pname:<30}"
        for n in counts:
            r = prows[n]
            if r["overhead_bytes"] >= 1024:
                val = f"{r['overhead_bytes']/1024:.1f} KB"
            else:
                val = f"{r['overhead_bytes']} B"
            line += f" {val:>{col_w}}"
        print(line)

    print("  " + "-" * (w - 4))

    # Show efficiency percentage row per protocol
    print()
    print(f"  {'Efficiency %':<30}", end="")
    for n in counts:
        print(f" {'N=' + str(n):>{col_w}}", end="")
    print()
    print("  " + "-" * (w - 4))
    for pname in protocols:
        prows = {r["n"]: r for r in rows if r["protocol"] == pname}
        line = f"  {pname:<30}"
        for n in counts:
            r = prows[n]
            line += f" {str(r['overhead_pct']) + '%':>{col_w}}"
        print(line)

    print("  " + "-" * (w - 4))

    # Cumulative waste comparison at N=1000
    if 1000 in counts:
        print()
        hermes_row = next(r for r in rows
                          if r["n"] == 1000 and "HERMES bus" in r["protocol"])
        print(f"  At 1,000 messages:")
        for pname in protocols:
            r = next(r for r in rows if r["n"] == 1000 and r["protocol"] == pname)
            saved = r["overhead_bytes"] - hermes_row["overhead_bytes"]
            if saved > 0:
                print(f"    {pname:<30} wastes {saved/1024:.1f} KB more than HERMES bus")
            else:
                print(f"    {pname:<30} (baseline)")
    print()


def print_latency_notes() -> None:
    """Print qualitative latency analysis."""
    w = 90
    print("=" * w)
    print("  LATENCY CHARACTERISTICS — Qualitative Analysis")
    print("=" * w)

    text = """
  HERMES bus (local file append):
    - Latency: ~0.01-0.1 ms (file system write + fsync)
    - No connection setup. No handshake. No DNS resolution.
    - Bounded by storage I/O: NVMe SSD ~10 us, SATA SSD ~50 us, HDD ~1-5 ms
    - Readers poll the file (or use kqueue/inotify for push notification)
    - Reader latency: ~0.1-1 ms for file read + JSON parse
    - Total end-to-end (write → read): ~0.1-2 ms on modern hardware

  HTTP/1.1 REST (HTTPS):
    - Cold: DNS (~5-50 ms) + TCP handshake (~1 RTT) + TLS 1.3 (~1 RTT) + request (~1 RTT)
    - Minimum cold start: ~3 RTTs. At 10ms RTT (LAN): ~30 ms. At 50ms RTT (cloud): ~150 ms.
    - Warm (keep-alive): ~1 RTT per request. But connection can be closed by server.
    - Connection pool management adds complexity.

  HTTP/2 (HPACK):
    - Same cold start as HTTP/1.1 (DNS + TCP + TLS)
    - Multiplexed streams: multiple requests over one connection without head-of-line blocking
    - Warm: sub-RTT for pipelined requests (stream interleaving)
    - Header compression (HPACK) reduces bytes but not latency

  gRPC (HTTP/2 + protobuf):
    - Same transport latency as HTTP/2 (it IS HTTP/2 underneath)
    - Protobuf serialization: ~1-10 us (negligible vs network)
    - Designed for persistent connections — cold start amortized over many RPCs
    - Streaming RPCs can reduce per-message latency to near-zero application overhead

  MQTT v5.0:
    - Requires persistent connection to broker (cold start: TCP + TLS + CONNECT/CONNACK)
    - Once connected: ~1 RTT per PUBLISH + PUBACK (QoS 1)
    - Broker adds store-and-forward latency: ~0.1-5 ms depending on implementation
    - Optimized for high-frequency small messages — closest to HERMES in design intent

  Summary:
    For co-located agents (same host), HERMES bus latency is 10-100x lower than
    any network protocol, because it eliminates the entire network stack. Even on
    a LAN (1ms RTT), HTTP/1.1 cold start is ~30ms vs HERMES ~0.1ms.

    For remote agents, HERMES gateway mode uses HTTPS (same as REST) — the
    efficiency advantage shifts from latency to bandwidth (smaller wire format).

    The latency advantage compounds with message frequency: at 100 msg/sec,
    HERMES bus adds ~10ms total I/O time vs ~3,000ms for HTTP/1.1 cold starts.
"""
    print(text)


def print_overhead_breakdown(protocols: list[ProtocolModel]) -> None:
    """Print a detailed overhead breakdown per protocol."""
    w = 90
    print("=" * w)
    print("  OVERHEAD BREAKDOWN — Where the bytes go")
    print("=" * w)
    print()
    print(f"  {'Protocol':<30} {'Transport':>10} {'Framing':>10} "
          f"{'Format':>10} {'Total OH':>10}")
    print("  " + "-" * (w - 4))

    for p in protocols:
        print(
            f"  {p.name:<30} "
            f"{p.transport_bytes:>7} B  "
            f"{p.framing_bytes:>7} B  "
            f"{p.format_wrapper_bytes:>7} B  "
            f"{p.overhead_bytes:>7} B"
        )

    print("  " + "-" * (w - 4))
    print()
    print("  Transport = TCP(20B) + TLS 1.3(22B) + IPv4(20B) = 62B for network protocols")
    print("  HERMES bus: 0B transport (local file I/O, no network stack)")
    print()


def print_csv(results: list[dict]) -> None:
    """Output single-message results as CSV."""
    keys = ["protocol", "payload_bytes", "overhead_bytes", "total_bytes",
            "overhead_pct", "efficiency_pct", "transport", "framing",
            "format_wrapper"]
    print(",".join(keys))
    for r in results:
        print(",".join(str(r[k]) for k in keys))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="HERMES L3 Channel Efficiency — Overhead Model",
        epilog="Part of HERMES Research Line L3. See ATR-G.711 for context.",
    )
    parser.add_argument(
        "--payload-size", type=int, default=120,
        help="Payload size in bytes (default: 120, HERMES max per ARC-5322)",
    )
    parser.add_argument("--csv", action="store_true", help="Output as CSV")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--sweep", action="store_true",
        help="Sweep payload sizes from 20 to 500 bytes (CSV output)",
    )
    args = parser.parse_args()

    protocols = build_protocols()
    payload = args.payload_size

    if args.sweep:
        print("payload_bytes,protocol,overhead_pct,efficiency_pct")
        for size in [20, 40, 60, 80, 100, 120, 200, 300, 500]:
            results = analyze_single(protocols, size)
            for r in results:
                print(f"{size},{r['protocol']},{r['overhead_pct']},"
                      f"{r['efficiency_pct']}")
        return

    results = analyze_single(protocols, payload)

    if args.csv:
        print_csv(results)
        return
    elif args.json:
        print(json.dumps(results, indent=2))
        return

    # Full report
    print_single_table(results, payload)
    print_overhead_breakdown(protocols)

    # Cumulative analysis
    cum_rows = analyze_cumulative(protocols, payload, [1, 10, 100, 1000])
    print_cumulative_table(cum_rows, payload)

    # Latency characteristics
    print_latency_notes()

    # Methodology note
    w = 90
    print("=" * w)
    print("  METHODOLOGY NOTES")
    print("=" * w)
    print(textwrap.dedent("""
    1. HERMES wrapper measured from actual reference implementation output:
       json.dumps(msg, ensure_ascii=False) with default separators.
       Namespaces: 'momoshod'/'nymyka' (8/6 chars — typical HERMES deployment).

    2. All network protocols include TCP + TLS 1.3 + IPv4 overhead (62B).
       This is the minimum — IPv6 adds 20B more (40B header vs 20B).

    3. HTTP header sizes are conservative minimums. Production APIs typically
       include cookies, tracing headers, and CORS — adding 200-500B more.

    4. gRPC and HTTP/2 amortize connection setup and HPACK state across
       messages on the same connection. The cold-start numbers shown here
       represent the worst case (first message on a new connection).
       For warm connections, gRPC framing drops to ~43B (from 103B).

    5. MQTT is the closest network competitor. Its fixed header (2B) is
       remarkably compact. The overhead comes from the topic name and
       the mandatory broker infrastructure.

    6. This model counts BYTES ONLY. It does not measure CPU cycles,
       memory allocation, serialization cost, or energy consumption.
       Those are planned for future L3 research phases.

    7. Connection setup costs (TCP 3-way handshake, TLS handshake) are
       NOT included in per-message byte counts. They are addressed in the
       latency characteristics section as they affect time, not wire bytes.
    """))


if __name__ == "__main__":
    main()
