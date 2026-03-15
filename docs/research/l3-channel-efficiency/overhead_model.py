#!/usr/bin/env python3
"""
L3 Channel Efficiency — Overhead Model
HERMES Research | ATR-G.711 supporting data

Compares per-message overhead across communication protocols
for the HERMES use case: short agent messages (≤120 chars payload).

Usage:
    python3 overhead_model.py
    python3 overhead_model.py --payload-size 60
    python3 overhead_model.py --csv > results.csv

References:
    - RFC 9113 (HTTP/2 HPACK compression)
    - RFC 9000 (QUIC header format)
    - MQTT v5.0 spec (Section 2.1)
    - gRPC over HTTP/2 spec
    - AMQP 1.0 OASIS spec (Section 2.8)
    - HERMES ARC-5322 (Message Format)
"""

import argparse
import json
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Protocol overhead components (bytes)
# All values represent MINIMUM overhead for a single short message.
# Sources documented per component.
# ---------------------------------------------------------------------------

@dataclass
class ProtocolOverhead:
    name: str
    description: str

    # Transport layer (below application)
    tcp_header: int = 0        # TCP: 20 bytes minimum (RFC 793)
    tls_record: int = 0        # TLS 1.3: 5-byte header + 1-byte type + 16-byte AEAD tag (RFC 8446)
    ip_header: int = 0         # IPv4: 20 bytes / IPv6: 40 bytes

    # Application layer
    http_request_line: int = 0  # "POST /bus/push HTTP/1.1\r\n"
    http_headers: int = 0       # Host, Content-Type, Authorization, Content-Length (min)
    http2_frame: int = 0        # HTTP/2 DATA frame header: 9 bytes (RFC 9113 §4.1)
    grpc_frame: int = 0         # gRPC Length-Prefixed Message: 5 bytes (compressed-flag + 4-byte len)
    mqtt_fixed: int = 0         # MQTT PUBLISH fixed header: 2 bytes minimum (MQTT 5.0 §2.1)
    mqtt_variable: int = 0      # MQTT variable header: topic len (2) + topic + packet id (2) + props
    amqp_frame: int = 0         # AMQP frame: 8-byte header + performative (Section 2.8)

    # Format overhead (JSON wrapper, newlines, etc.)
    format_wrapper: int = 0    # JSON key names, braces, quotes, commas

    # Extra notes
    notes: str = ""

    @property
    def transport_total(self) -> int:
        return self.tcp_header + self.tls_record + self.ip_header

    @property
    def application_total(self) -> int:
        return (self.http_request_line + self.http_headers + self.http2_frame +
                self.grpc_frame + self.mqtt_fixed + self.mqtt_variable +
                self.amqp_frame + self.format_wrapper)

    @property
    def total_overhead(self) -> int:
        return self.transport_total + self.application_total

    def overhead_ratio(self, payload_bytes: int) -> float:
        """Fraction of total bytes that is overhead (0.0 → 1.0)."""
        total = self.total_overhead + payload_bytes
        return self.total_overhead / total if total > 0 else 0.0

    def efficiency_ratio(self, payload_bytes: int) -> float:
        """Fraction of total bytes that is useful payload (0.0 → 1.0)."""
        return 1.0 - self.overhead_ratio(payload_bytes)


# ---------------------------------------------------------------------------
# Protocol definitions
# ---------------------------------------------------------------------------

def build_protocols() -> list[ProtocolOverhead]:
    return [
        ProtocolOverhead(
            name="HERMES (file-based, local)",
            description="JSONL bus: one newline-terminated JSON line. No network stack.",
            # No TCP/TLS/IP for local file write
            tcp_header=0,
            tls_record=0,
            ip_header=0,
            # ARC-5322 field names: ts(2)+src(3)+dst(3)+type(4)+msg(3)+ttl(3)+ack(3) + quotes/colons = ~55 chars
            # But required: {"ts":"YYYY-MM-DD","src":"X","dst":"Y","type":"Z","msg":"<payload>","ttl":7,"ack":[]}\n
            format_wrapper=68,  # template overhead excluding payload value
            notes="Local intra-clan. No network. Just append to file.",
        ),
        ProtocolOverhead(
            name="HERMES (gateway, HTTPS)",
            description="JSONL over HTTPS POST to remote gateway (Render/cloud).",
            tcp_header=20,
            tls_record=21,   # 5-byte header + 16-byte AEAD tag (TLS 1.3, RFC 8446 §5.2)
            ip_header=20,
            http_request_line=26,  # "POST /bus/push HTTP/1.1\r\n"
            # Host(~35) + Content-Type(38) + X-Gateway-Key(32+32) + Content-Length(16) + CRLF(4)
            http_headers=160,
            format_wrapper=68,
            notes="Remote inter-clan. HTTPS POST. Same payload format as local.",
        ),
        ProtocolOverhead(
            name="HTTP/1.1 REST (HTTPS)",
            description="Typical REST API: POST with JSON body, auth header, CORS headers.",
            tcp_header=20,
            tls_record=21,
            ip_header=20,
            http_request_line=30,  # "POST /api/v1/messages HTTP/1.1\r\n"
            # Host + Content-Type + Authorization(Bearer token ~64) + Accept + Content-Length + CORS = ~320
            http_headers=320,
            # JSON envelope: {"message": {"from": "X", "to": "Y", "body": "<payload>", "timestamp": "Z"}}
            format_wrapper=65,
            notes="Standard REST. Minimum headers — real APIs add more (User-Agent, X-Request-ID...).",
        ),
        ProtocolOverhead(
            name="HTTP/2 + gRPC",
            description="gRPC unary RPC over HTTP/2 with HPACK-compressed headers.",
            tcp_header=20,
            tls_record=21,
            ip_header=20,
            http2_frame=9,   # DATA frame header (RFC 9113 §4.1)
            grpc_frame=5,    # Length-Prefixed Message (compressed-flag + 4-byte length)
            # HPACK-compressed headers (first request, cold): ~80 bytes after compression
            # Subsequent requests: ~20 bytes (indexed headers)
            http_headers=80,
            # Protobuf: field tags + varint lengths. For string fields: tag(1) + len(1) + value
            # For {"src": "X", "dst": "Y", "msg": "<payload>"}: ~15 bytes wrapper
            format_wrapper=15,
            notes="HPACK headers amortize over connection. Cold start shown here.",
        ),
        ProtocolOverhead(
            name="MQTT v5.0 (TLS)",
            description="MQTT PUBLISH QoS 1, typical IoT/agent message broker (Mosquitto, HiveMQ).",
            tcp_header=20,
            tls_record=21,
            ip_header=20,
            mqtt_fixed=2,    # Fixed header: 1-byte type+flags + 1-byte remaining length (MQTT 5.0 §2.1)
            # Variable header: topic(2+len) + packet-id(2) + properties-length(1) + properties(0 minimal)
            # Topic "hermes/bus/momoshod": 22 chars + 2 len bytes = 24
            mqtt_variable=29,
            # MQTT payload is raw bytes — minimal JSON wrapper
            format_wrapper=40,
            notes="QoS 1 requires PUBACK (+4 bytes round-trip overhead). Broker required.",
        ),
        ProtocolOverhead(
            name="AMQP 1.0 (TLS)",
            description="AMQP 1.0 message to a queue/topic. Enterprise message bus.",
            tcp_header=20,
            tls_record=21,
            ip_header=20,
            # AMQP frame: 4-byte size + 1-byte doff + 1-byte type + 2-byte channel = 8 bytes
            # Transfer performative (AMQP 1.0 §2.6.8): ~40 bytes minimum
            amqp_frame=48,
            # Message properties section + application-properties: ~60 bytes minimum
            http_headers=60,
            format_wrapper=40,
            notes="Broker required (RabbitMQ, ActiveMQ). Connection setup not included.",
        ),
    ]


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze(protocols: list[ProtocolOverhead], payload_bytes: int) -> list[dict]:
    results = []
    for p in protocols:
        total = p.total_overhead + payload_bytes
        results.append({
            "protocol": p.name,
            "payload_bytes": payload_bytes,
            "overhead_bytes": p.total_overhead,
            "total_bytes": total,
            "overhead_pct": round(p.overhead_ratio(payload_bytes) * 100, 1),
            "efficiency_pct": round(p.efficiency_ratio(payload_bytes) * 100, 1),
            "transport_overhead": p.transport_total,
            "app_overhead": p.application_total,
            "notes": p.notes,
        })
    return sorted(results, key=lambda x: x["overhead_pct"])


def print_table(results: list[dict], payload_bytes: int) -> None:
    print(f"\nL3 Channel Efficiency Model — HERMES vs alternatives")
    print(f"Payload size: {payload_bytes} bytes (HERMES ARC-5322 message content)")
    print(f"{'='*85}")
    print(f"{'Protocol':<35} {'Overhead':>10} {'Total':>8} {'Overhead%':>10} {'Efficiency%':>12}")
    print(f"{'-'*85}")
    for r in results:
        marker = " ◀" if "HERMES (file" in r["protocol"] else ""
        print(
            f"{r['protocol']:<35} "
            f"{r['overhead_bytes']:>7} B  "
            f"{r['total_bytes']:>5} B  "
            f"{r['overhead_pct']:>8.1f}%  "
            f"{r['efficiency_pct']:>9.1f}%"
            f"{marker}"
        )
    print(f"{'='*85}")

    # Key finding
    hermes_local = next(r for r in results if "file-based" in r["protocol"])
    worst = max(results, key=lambda x: x["overhead_pct"])
    print(f"\nKey finding:")
    print(f"  HERMES file-based: {hermes_local['overhead_pct']}% overhead")
    print(f"  {worst['protocol']}: {worst['overhead_pct']}% overhead")
    ratio = worst['overhead_pct'] / hermes_local['overhead_pct'] if hermes_local['overhead_pct'] > 0 else 0
    print(f"  HERMES is {ratio:.1f}x more efficient than {worst['protocol'].split('(')[0].strip()}")
    print(f"\nNote: Transport overhead (TCP/TLS/IP) not applicable to local file-based HERMES.")
    print(f"For remote gateway mode, HERMES overhead matches HTTP/1.1 REST (same transport stack).")
    print(f"The efficiency advantage is maximized for intra-clan (local) communication.\n")


def print_csv(results: list[dict]) -> None:
    keys = ["protocol", "payload_bytes", "overhead_bytes", "total_bytes",
            "overhead_pct", "efficiency_pct", "transport_overhead", "app_overhead"]
    print(",".join(keys))
    for r in results:
        print(",".join(str(r[k]) for k in keys))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="HERMES L3 Channel Efficiency Model")
    parser.add_argument("--payload-size", type=int, default=120,
                        help="Payload size in bytes (default: 120, HERMES max per ARC-5322)")
    parser.add_argument("--csv", action="store_true", help="Output as CSV")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--sweep", action="store_true",
                        help="Sweep payload sizes from 20 to 500 bytes")
    args = parser.parse_args()

    protocols = build_protocols()

    if args.sweep:
        print("payload_bytes,protocol,overhead_pct,efficiency_pct")
        for size in [20, 40, 60, 80, 100, 120, 200, 300, 500]:
            results = analyze(protocols, size)
            for r in results:
                print(f"{size},{r['protocol']},{r['overhead_pct']},{r['efficiency_pct']}")
        return

    results = analyze(protocols, args.payload_size)

    if args.csv:
        print_csv(results)
    elif args.json:
        print(json.dumps(results, indent=2))
    else:
        print_table(results, args.payload_size)


if __name__ == "__main__":
    main()
