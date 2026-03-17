# ATR-G.711: Payload Encoding and Wire Efficiency

| Field       | Value                                                              |
|-------------|--------------------------------------------------------------------|
| **Number**  | ATR-G.711                                                          |
| **Title**   | Payload Encoding and Wire Efficiency                               |
| **Lineage** | ITU-T G.711 — Pulse Code Modulation (PCM) of Voice Frequencies     |
| **Status**  | IMPLEMENTED                                                        |
| **Date**    | 2026-03-17                                                         |

---

## 1. Abstract

This document specifies the payload encoding strategy for HERMES messages
and provides a quantitative analysis of wire efficiency across communication
protocols. It formalizes the design decision to use JSON as the wire format
for all HERMES message layers, supported by empirical overhead measurements
from the reference implementation.

The analogy to ITU-T G.711 is deliberate: just as G.711 defined the baseline
encoding for voice traffic in the PSTN (8 kHz sampling, 8-bit μ-law/A-law,
64 kbit/s per channel), ATR-G.711 defines the baseline encoding for agent
messages in HERMES. G.711 chose simplicity and universality over compression
efficiency — and so does HERMES.

---

## 2. Scope

This recommendation:

- Specifies JSON (RFC 8259) as the NORMATIVE encoding for HERMES bus messages.
- Defines encoding constraints for the ARC-5322 message format.
- Provides a formal overhead model comparing HERMES to four alternative protocols.
- Documents the design tradeoff: **inspectability over wire compactness**.
- Establishes criteria for when compact encodings (CBOR, MessagePack) MAY be used.

This recommendation does NOT:

- Define new message types or fields (see ARC-5322).
- Specify compression at the transport layer (see future ARC-2818).
- Mandate encoding for gateway-to-gateway traffic (see ARC-3022).

---

## 3. Terminology

Key words "MUST", "SHOULD", "MAY", "MUST NOT", and "SHOULD NOT" are
defined in ARC-2119.

| Term | Definition |
|------|-----------|
| **Wire format** | The byte-level serialization of a message as written to the bus or transmitted over a link |
| **Overhead** | Total bytes minus payload bytes. Includes transport, framing, and format wrapper |
| **Efficiency** | Ratio of payload bytes to total bytes, expressed as a percentage |
| **Format wrapper** | Bytes added by the serialization format (JSON keys, braces, quotes, separators) |
| **Transport overhead** | Bytes from the network stack (TCP, TLS, IP headers) — zero for file-based bus |
| **Framing overhead** | Bytes from the application protocol (HTTP headers, MQTT headers, etc.) |
| **Inspectability** | The ability of a human operator to read and understand a message using only standard text tools |

---

## 4. Design Rationale — The G.711 Principle

### 4.1 Why G.711 Won

ITU-T G.711 (1972) is the most widely deployed audio codec in history. It is
not the most efficient — G.729 compresses 8x better, Opus compresses 16x
better. Yet G.711 remains the mandatory baseline codec in every VoIP system,
every PSTN interconnect, and every telecom standard published since 1972.

G.711 won because:

1. **Universal decode.** Every device on the PSTN can decode G.711 without
   negotiation. No capability exchange needed.
2. **Zero-computation decode.** μ-law/A-law expansion is a table lookup.
   No DSP required. Any 8-bit microcontroller can play G.711.
3. **Inspectability.** A telecom engineer can look at a G.711 bitstream with
   a hex editor and immediately identify sample boundaries, silence periods,
   and signal characteristics.
4. **Debuggability.** When something goes wrong, G.711 traces are trivially
   interpretable. Compressed codecs produce opaque bitstreams.

The price: 64 kbit/s per channel instead of 8 kbit/s (G.729) or 6 kbit/s
(Opus). For the PSTN's use case (reliable copper/fiber links with ample
bandwidth), the 8x bandwidth penalty was acceptable.

### 4.2 Why HERMES Chose JSON

HERMES applies the same principle to agent message encoding:

| G.711 Property | HERMES JSON Equivalent |
|---------------|----------------------|
| Universal decode | Every language, every tool, every OS has a JSON parser |
| Zero-computation decode | `json.loads()` — no schema compilation, no proto stubs |
| Inspectability | `cat bus.jsonl` — human-readable with any text editor |
| Debuggability | `grep "src.*momoshod" bus.jsonl` — standard Unix tools work |

The price: ~105 bytes of format wrapper per message instead of ~15 bytes
(protobuf) or ~40 bytes (CBOR). For HERMES's use case (file-based bus on
local storage with effectively unlimited bandwidth), the ~90 byte penalty
is acceptable.

### 4.3 The Inspectability Theorem

> **For a file-based, audit-trail protocol where the bus IS the database,
> inspectability is not a convenience — it is a security property.**

A human operator MUST be able to:

1. Read any message on the bus without specialized tools.
2. Verify message integrity by visual inspection (field names, types, values).
3. Audit the bus history using `grep`, `jq`, `awk`, or any POSIX text tool.
4. Detect anomalies (malformed messages, unexpected senders) by scanning.

Binary encodings (protobuf, CBOR, MessagePack) require decoding tools that
may not be available in every environment where a HERMES bus operates. JSON
requires only a text editor.

---

## 5. Normative Encoding Requirements

### 5.1 Bus Messages (L1 Frame Layer)

1. Messages on the HERMES bus MUST be encoded as JSON (RFC 8259).
2. Each message MUST occupy exactly one line (JSONL format, per ARC-5322).
3. Messages MUST use UTF-8 encoding without BOM.
4. Implementations SHOULD use default JSON separators (`, ` and `: `) for
   readability. Compact separators (`,` and `:`) MAY be used when storage
   constraints require it, saving approximately 6 bytes per message.
5. Field order SHOULD follow ARC-5322 canonical order: `ts`, `src`, `dst`,
   `type`, `msg`, `ttl`, `ack`, then optional fields.
6. Numeric values MUST NOT be quoted (e.g., `"ttl": 7` not `"ttl": "7"`).
7. The `ack` array MUST use JSON array syntax, even when empty (`[]`).

### 5.2 Encrypted Envelopes (ARC-8446)

1. The outer envelope (containing `enc`, `sig`, `nonce`, `ciphertext`,
   and optionally `eph_pub`) MUST be JSON-encoded.
2. The inner plaintext (decrypted `ciphertext`) MUST be a valid JSON
   message conforming to §5.1.
3. Binary fields (`sig`, `nonce`, `ciphertext`, `eph_pub`) MUST be
   hex-encoded strings, per ARC-8446 §7.

### 5.3 Gateway Wire Format (ARC-3022)

1. Gateway-to-gateway messages transmitted over HTTP MUST use JSON
   encoding with `Content-Type: application/json`.
2. Gateways MAY negotiate compact encoding (CBOR, MessagePack) via the
   `Accept-Encoding` header for high-throughput inter-clan links, provided:
   a. Both gateways support the encoding.
   b. The compact message can be losslessly round-tripped to JSON.
   c. Messages are transcoded back to JSON before writing to the local bus.

---

## 6. Overhead Model

### 6.1 Methodology

The overhead model decomposes the total cost of sending one HERMES-equivalent
message into three components:

```
Total bytes = Transport + Framing + Format Wrapper + Payload
Overhead    = Transport + Framing + Format Wrapper
Efficiency  = Payload / Total bytes × 100%
```

**Measurement approach:**

- **HERMES format wrapper**: Measured from the reference implementation using
  `json.dumps()` with default separators and typical 8-character namespace
  names. Source: `overhead_model.py`.
- **Transport overhead**: TCP (20B, RFC 793) + TLS 1.3 (22B, RFC 8446 §5.2)
  + IPv4 (20B, RFC 791) = 62 bytes for all network protocols.
- **Framing overhead**: Protocol-specific headers measured from specification
  documents (see §6.5 for sources).

**Assumptions** (conservative, favoring alternatives):

- HTTP/1.1: Minimum realistic headers (6 headers, no cookies or tracing).
- HTTP/2: HPACK cold start (first request). Warm connections amortize to ~20B.
- gRPC: HTTP/2 + protobuf Length-Prefixed Message framing.
- MQTT v5.0: QoS 1, 22-character topic, minimal properties.
- All network protocols: No connection reuse (worst case per-message cost).

### 6.2 Per-Message Comparison (120-byte payload)

The reference payload size of 120 bytes represents a typical HERMES ARC-5322
`msg` field for state announcements and dispatch messages.

| Protocol | Transport | Framing | Format | **Overhead** | **Total** | **Efficiency** |
|----------|-----------|---------|--------|-------------|-----------|---------------|
| **HERMES compact (§14)** | 0 B | 1 B | 35 B | **36 B** | 156 B | **76.9%** |
| HERMES verbose | 0 B | 1 B | 105 B | **106 B** | 226 B | **53.1%** |
| MQTT v5.0 (TLS) | 62 B | 31 B | 40 B | **133 B** | 253 B | **47.4%** |
| gRPC (HTTP/2 + protobuf) | 62 B | 103 B | 15 B | **180 B** | 300 B | **40.0%** |
| HTTP/2 (HPACK, HTTPS) | 62 B | 109 B | 65 B | **236 B** | 356 B | **33.7%** |
| HTTP/1.1 REST (HTTPS) | 62 B | 350 B | 65 B | **477 B** | 597 B | **20.1%** |

**Key findings:**

- **HERMES compact mode** achieves **76.9% efficiency** — the highest of any
  protocol measured — while remaining valid, human-readable JSON.
- HERMES compact is **4.9x less overhead** than gRPC and **3.6x less** than
  MQTT, despite using no binary encoding.
- HERMES bus has **zero transport overhead** — the primary advantage for
  co-located agents on the same filesystem.
- Even in verbose mode, HERMES is more efficient than all network alternatives.
- gRPC's compact protobuf encoding (15B wrapper vs HERMES compact's 35B) is
  dominated by its HTTP/2+HPACK framing overhead (103B), resulting in 4.9x
  more total overhead than HERMES compact.

### 6.3 Overhead Decomposition

```
Protocol                        Transport   Framing    Format     Total OH
──────────────────────────────────────────────────────────────────────────
HERMES compact (§14)                 0 B        1 B       35 B       36 B
HERMES verbose                       0 B        1 B      105 B      106 B
MQTT v5.0 (TLS)                    62 B       31 B       40 B      133 B
gRPC (HTTP/2 + protobuf)           62 B      103 B       15 B      180 B
HTTP/2 (HPACK, HTTPS)              62 B      109 B       65 B      236 B
HTTP/1.1 REST (HTTPS)              62 B      350 B       65 B      477 B
──────────────────────────────────────────────────────────────────────────
```

For network protocols, transport overhead (62B) is a fixed floor — TCP + TLS
+ IP headers are non-negotiable for secure communication. HERMES eliminates
this entirely by operating on the local filesystem.

### 6.4 Efficiency Across Payload Sizes

Efficiency varies with payload size. Smaller payloads amplify overhead;
larger payloads amortize it. The following table shows efficiency at 9
payload sizes from 20B to 500B:

| Payload | HERMES | MQTT v5.0 | gRPC | HTTP/2 | HTTP/1.1 |
|---------|--------|-----------|------|--------|----------|
| 20 B | 15.9% | 13.1% | 10.0% | 7.8% | 4.0% |
| 40 B | 27.4% | 23.1% | 18.2% | 14.5% | 7.7% |
| 60 B | 36.1% | 31.1% | 25.0% | 20.3% | 11.2% |
| 80 B | 43.0% | 37.6% | 30.8% | 25.3% | 14.4% |
| 100 B | 48.5% | 42.9% | 35.7% | 29.8% | 17.3% |
| **120 B** | **53.1%** | **47.4%** | **40.0%** | **33.7%** | **20.1%** |
| 200 B | 65.4% | 60.1% | 52.6% | 45.9% | 29.5% |
| 300 B | 73.9% | 69.3% | 62.5% | 56.0% | 38.6% |
| 500 B | 82.5% | 79.0% | 73.5% | 67.9% | 51.2% |

**Observations:**

1. HERMES maintains the highest efficiency at every payload size.
2. The gap narrows as payloads grow — at 500B, HERMES leads MQTT by only 3.5%.
3. At 20B (micro-messages like heartbeats), all protocols are inefficient,
   but HERMES is 4x more efficient than HTTP/1.1.
4. The crossover where all protocols exceed 50% efficiency: HERMES at ~120B,
   MQTT at ~140B, gRPC at ~200B, HTTP/2 at ~260B, HTTP/1.1 at ~500B.

### 6.5 Cumulative Impact

For systems exchanging many messages, overhead compounds:

| Messages | HERMES OH | MQTT OH | gRPC OH | HTTP/2 OH | HTTP/1.1 OH |
|----------|-----------|---------|---------|-----------|-------------|
| 1 | 106 B | 133 B | 180 B | 236 B | 477 B |
| 10 | 1.0 KB | 1.3 KB | 1.8 KB | 2.3 KB | 4.7 KB |
| 100 | 10.4 KB | 13.0 KB | 17.6 KB | 23.0 KB | 46.6 KB |
| 1,000 | 103.5 KB | 129.9 KB | 175.8 KB | 230.5 KB | 465.8 KB |

At 1,000 messages, HERMES saves **362 KB** compared to HTTP/1.1 REST.
For a busy clan exchanging ~100 messages per day, this amounts to
~10 MB/month of avoided overhead — negligible in absolute terms, but
the efficiency reflects a cleaner protocol design.

### 6.6 Data Sources

| Source | Reference | Used for |
|--------|-----------|----------|
| ARC-5322 | HERMES spec | JSON message structure, field sizes |
| RFC 793 | IETF | TCP header: 20 bytes minimum |
| RFC 791 | IETF | IPv4 header: 20 bytes minimum |
| RFC 8446 §5.2 | IETF | TLS 1.3 record: 5B header + 1B content type + 16B AEAD tag = 22B |
| RFC 9113 §4.1 | IETF | HTTP/2 frame header: 9 bytes |
| RFC 7541 | IETF | HPACK header compression |
| gRPC protocol | github.com/grpc | Length-Prefixed Message: 5 bytes |
| MQTT v5.0 §2-3 | OASIS | Fixed header, variable header, PUBLISH format |
| RFC 8949 | IETF | CBOR encoding (referenced for compact alternatives) |

### 6.7 Reproducibility

All overhead data is generated by:

```bash
# Install dependencies
cd reference/python && pip install -e .

# Default 120B payload
python -m hermes.overhead_model

# JSON output for programmatic use
python -m hermes.overhead_model --json

# Sweep across payload sizes
python -m hermes.overhead_model --sweep

# Custom payload size
python -m hermes.overhead_model --payload-size 60
```

Source: `docs/research/l3-channel-efficiency/overhead_model.py`

---

## 7. Latency Characteristics

Wire efficiency captures only byte overhead. Latency behavior differs
qualitatively across protocols:

| Protocol | Cold Start | Warm Message | Notes |
|----------|-----------|-------------|-------|
| HERMES bus | ~0.1 ms | ~0.1 ms | File append + fsync. No handshake. |
| MQTT v5.0 | ~30-150 ms | ~1 RTT | Requires broker. CONNECT/CONNACK setup. |
| gRPC | ~30-150 ms | sub-RTT | Persistent connection. Stream multiplexing. |
| HTTP/2 | ~30-150 ms | ~1 RTT | Same setup as gRPC. Header compression helps bandwidth, not latency. |
| HTTP/1.1 | ~30-150 ms | ~1 RTT | DNS + TCP + TLS = 3 RTTs cold. Keep-alive reduces to 1 RTT. |

For co-located agents (same host), HERMES bus latency is **10-100x lower**
than any network protocol because it eliminates the entire network stack.

At 100 messages/sec, HERMES bus adds ~10 ms total I/O time vs ~3,000 ms for
HTTP/1.1 cold starts (or ~100 ms warm with keep-alive).

---

## 8. Compact Encoding Extensions

### 8.1 When Compact Encoding MAY Be Used

Compact binary encodings (CBOR per RFC 8949, MessagePack) are permitted
only in the following contexts:

1. **Gateway-to-gateway links** (ARC-3022) where both endpoints negotiate
   the encoding and transcode back to JSON before local bus write.
2. **Archive compression** where historical bus data is stored in a compact
   format for long-term retention, with a JSON index for discoverability.
3. **Agent Node daemon** (ARC-4601) internal state, which is not part of
   the bus protocol.

### 8.2 When Compact Encoding MUST NOT Be Used

1. The local bus file (`bus.jsonl`) MUST always contain JSON.
2. Messages exchanged via the relay (bilateral or Agora) MUST be JSON.
3. Encrypted envelopes (ARC-8446) MUST use JSON for the outer structure.
4. Any message intended for human audit MUST be JSON.

### 8.3 Potential Savings

For reference, the format wrapper savings from compact encodings at 120B
payload:

| Encoding | Format Wrapper | Savings vs JSON | Total Efficiency |
|----------|---------------|----------------|-----------------|
| JSON (current) | 105 B | — | 53.1% |
| CBOR (RFC 8949) | ~60 B | ~45 B | 60.0% |
| MessagePack | ~55 B | ~50 B | 61.4% |
| Protobuf | ~15 B | ~90 B | 68.6% |

The maximum achievable improvement from switching to protobuf is **+15.5
percentage points** (53.1% → 68.6%). For a file-based protocol where
storage is effectively free, this does not justify the loss of
inspectability (§4.3).

---

## 9. Relationship to Other Specifications

| Spec | Relationship |
|------|-------------|
| ARC-5322 | Defines the message format that this spec encodes |
| ARC-8446 | Defines the encryption envelope format (JSON outer, binary inner fields hex-encoded) |
| ARC-3022 | Gateway protocol where compact encoding MAY be negotiated |
| ARC-4601 | Agent Node daemon where internal state MAY use compact encoding |
| ATR-X.200 | Reference model — this spec operates at L1 (Frame Layer) |
| ATR-Q.700 | Design philosophy — inspectability as a signaling system property |
| AES-2040 | Visualization standard — JSON enables direct rendering of bus data |

---

## 10. Security Considerations

1. **JSON injection**: Implementations MUST validate that bus messages parse
   as valid JSON before processing. Malformed lines MUST be logged and skipped.
2. **Unicode normalization**: String comparison for field matching (e.g., `src`,
   `dst`) SHOULD use NFC normalization to prevent homograph attacks.
3. **Size limits**: Implementations SHOULD enforce a maximum message size
   (RECOMMENDED: 64 KB) to prevent resource exhaustion from oversized messages.
4. **Number precision**: JSON numbers MUST NOT exceed IEEE 754 double-precision
   range. The `ttl` field uses integer values well within this range.

---

## 11. Implementation Notes

### 11.1 Reference Implementation

The Python reference implementation (`hermes/message.py`) uses `json.dumps()`
with default separators and `ensure_ascii=False` for UTF-8 output:

```python
import json

def serialize(msg: dict) -> str:
    return json.dumps(msg, ensure_ascii=False)

def deserialize(line: str) -> dict:
    return json.loads(line.strip())
```

### 11.2 Performance Characteristics

Measured on the reference implementation (Python 3.14, Apple M-series):

- Serialization: ~2 μs per message (json.dumps)
- Deserialization: ~3 μs per message (json.loads)
- Full bus scan (1,000 messages): ~5 ms
- These times are negligible compared to LLM inference (seconds to minutes)

### 11.3 Interoperability

JSON parsers exist in every programming language and runtime environment.
A HERMES bus can be read by:

- Python: `json.loads()`
- JavaScript/Node.js: `JSON.parse()`
- Go: `encoding/json`
- Rust: `serde_json`
- Shell: `jq`
- Any text editor (visual inspection)

This universality is the primary motivation for choosing JSON over more
efficient alternatives.

---

## Appendix A: Overhead Model Source

The complete overhead model is available at:

```
docs/research/l3-channel-efficiency/overhead_model.py
```

Usage:

```bash
python3 overhead_model.py                    # Full report (120B payload)
python3 overhead_model.py --payload-size 60  # Custom payload
python3 overhead_model.py --sweep            # CSV across 9 payload sizes
python3 overhead_model.py --json             # Machine-readable output
python3 overhead_model.py --csv              # Single-size CSV output
```

The model is deterministic and fully reproducible. All byte counts are
derived from protocol specifications (RFCs, OASIS standards) and verified
against the HERMES reference implementation.

---

## Appendix B: The G.711 Analogy — Full Mapping

| G.711 (Voice) | ATR-G.711 (Agent Messages) |
|---------------|---------------------------|
| PCM μ-law encoding | JSON (RFC 8259) encoding |
| 64 kbit/s per channel | ~106 B overhead per message |
| G.729 (8 kbit/s, 8x compression) | Protobuf (~15 B wrapper, 7x compression) |
| Universal PSTN decode | Universal JSON parse |
| Hex editor inspection | `cat bus.jsonl` inspection |
| No DSP required | No schema compilation required |
| Mandatory baseline codec | Mandatory baseline encoding |
| Narrowband (300-3400 Hz) | Short messages (≤500 B payload) |
| Wideband codecs optional (G.722) | Compact codecs optional (CBOR, §8) |

---

## Appendix C: Glossary of Telecom Terms

| Term | Origin | Meaning in Context |
|------|--------|-------------------|
| **G.711** | ITU-T 1972 | Pulse Code Modulation — the baseline voice codec at 64 kbit/s |
| **μ-law** | Bell System | Logarithmic companding used in North American PSTN |
| **A-law** | ITU-T | Logarithmic companding used in European PSTN |
| **CBOR** | RFC 8949 | Concise Binary Object Representation — binary superset of JSON |
| **HPACK** | RFC 7541 | Header compression for HTTP/2 |
| **QoS** | ISO 8802 | Quality of Service — message delivery guarantees |
| **AEAD** | RFC 5116 | Authenticated Encryption with Associated Data (used in TLS 1.3, ARC-8446) |

---

*ATR-G.711 — HERMES Project — MIT License*
*Generated from overhead_model.py v1.0 data (2026-03-17)*
