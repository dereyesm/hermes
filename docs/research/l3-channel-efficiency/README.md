# L3 Channel Efficiency — Research

> HERMES Research Line L3 | Supporting data for ATR-G.711

## Objective

Quantify the per-message overhead of HERMES compared to dominant alternatives
(HTTP/REST, gRPC, MQTT, AMQP) for the HERMES use case: short agent messages (≤120 chars payload).

## Files

| File | Description |
|------|-------------|
| `overhead_model.py` | Analytical model: overhead breakdown by protocol and payload size |
| `results/` | Pre-computed outputs for standard payload sizes |

## Quick Start

```bash
# Default: 120-byte payload (HERMES ARC-5322 maximum)
python3 overhead_model.py

# Custom payload size
python3 overhead_model.py --payload-size 60

# Sweep across payload sizes (for chart generation)
python3 overhead_model.py --sweep > results/sweep.csv

# JSON output (for programmatic use)
python3 overhead_model.py --json > results/120b.json
```

## Key Finding (preliminary)

At 120-byte payload:

| Protocol | Overhead | Efficiency |
|----------|----------|------------|
| **HERMES (local)** | ~36% | ~64% |
| MQTT v5.0 | ~48% | ~52% |
| HTTP/2 + gRPC | ~55% | ~45% |
| HTTP/1.1 REST | ~74% | ~26% |
| AMQP 1.0 | ~76% | ~24% |

HERMES local (file-based) eliminates the transport stack entirely for intra-clan messages.
At 120 bytes, this is **2-3x more efficient** than REST and gRPC per message.

## Model Assumptions

- All byte counts are **minimums** — real implementations add more headers
- TCP/TLS/IP overhead assumed for all network protocols (20+21+20 = 61 bytes)
- HERMES file-based: zero transport overhead (local file append)
- HERMES gateway: same transport stack as HTTP/1.1 REST (inter-clan only)
- gRPC: HPACK cold start shown (subsequent requests amortize header cost)
- MQTT: QoS 1, topic `hermes/bus/<clan-id>` (~22 chars)

## Data Sources

| Source | URL | Used for |
|--------|-----|---------|
| RFC 9113 | datatracker.ietf.org/doc/html/rfc9113 | HTTP/2 frame format |
| RFC 9000 | datatracker.ietf.org/doc/html/rfc9000 | QUIC (future L3 work) |
| MQTT 5.0 | docs.oasis-open.org/mqtt/mqtt/v5.0 | MQTT header format |
| RFC 8446 | datatracker.ietf.org/doc/html/rfc8446 | TLS 1.3 record overhead |
| gRPC spec | github.com/grpc/grpc/blob/master/doc/PROTOCOL-HTTP2.md | gRPC framing |
| AMQP 1.0 | docs.oasis-open.org/amqp/core/v1.0 | AMQP frame format |

## Next Steps

1. **Empirical validation**: Capture real Wireshark traces for each protocol, compare to model
2. **M-Lab data**: Pull latency distribution from BigQuery → model effective throughput under jitter
3. **Energy model**: Estimate joules/message using CPU cycle counts from published benchmarks
4. **ATR-G.711 appendix**: Incorporate results as §Appendix A of the spec

## Status

- [x] Analytical model (overhead_model.py)
- [ ] Wireshark empirical capture
- [ ] M-Lab latency integration
- [ ] Energy per message model
- [ ] ATR-G.711 appendix
