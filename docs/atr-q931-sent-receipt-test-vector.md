# ATR-Q.931 §8.1 SENT Receipt — Test Vector

> Clan validation artifact for the first implemented stage of the
> ATR-Q.931 four-stage delivery receipt model.

**Status**: LIVE on `main` since commit [`4c67736`](https://github.com/dereyesm/amaru-protocol/commit/4c67736) (2026-04-06)
**Spec**: [ATR-Q.931 — Session Setup Signaling](../spec/ATR-Q931.md) — DRAFT, §8.1 IMPL
**Impl**: `reference/python/amaru/hub.py` — `MessageRouter._emit_sent_receipt()` (lines 513–562)
**Tests**: `reference/python/tests/test_hub.py` — `TestMessageRouterSentReceipt` (7 tests)

---

## 1. Purpose

Give any clan integrating against an Amaru hub the minimum they need to
verify that the hub emits `SENT` receipts correctly, without having to
read the full 945-line ATR-Q.931 spec. Copy-paste runnable.

Only the `SENT` stage is covered here. `DELIVERED`, `READ`, and
`PROCESSED` are specified in ATR-Q.931 §8.1–§8.2 but not yet
implemented in the reference hub — they are pending bilateral design
review.

---

## 2. Contract (summary)

A clan that wants a SENT receipt adds two fields to its outgoing
ARC-5322 envelope:

| Field     | Required                | Example                  |
|-----------|-------------------------|--------------------------|
| `ref`     | MUST (§8.3)             | `"jei-042"`              |
| `receipt` | MUST contain `"SENT"`   | `["SENT"]`               |

The hub, **before** dispatching the data envelope to its destination,
emits a signaling frame back to the sender's local connection(s). The
frame conforms to ATR-Q.931 §6.2 (signaling frame schema).

A clan that does NOT want receipts sends an envelope with no `receipt`
key. This is the default and is fully backward compatible — cero
existing clients break.

---

## 3. Input Envelope (what the sender sends)

```json
{
  "ts": "2026-04-06",
  "src": "jei",
  "dst": "amaru",
  "type": "dispatch",
  "msg": "QUEST-007 payload (opaque, possibly E2E encrypted)",
  "ttl": 7,
  "ack": [],
  "ref": "jei-042",
  "receipt": ["SENT"]
}
```

Notes:
- `msg` is **never** inspected by the hub. E2E crypto passthrough is
  preserved regardless of receipt state.
- `ref` MUST be unique within a 24-hour window per sender (§8.3).
- `receipt` is an opt-in array. Omitting it = fire-and-forget default.

---

## 4. Expected Output — SENT Signaling Frame

The hub emits this frame back to the sender on the same WebSocket
connection, wrapped in the hub's `sig` envelope type:

```json
{
  "type": "sig",
  "payload": {
    "channel": "sig",
    "type": "SENT",
    "src": "<hub-id>",
    "dst": "jei",
    "ref": "jei-042",
    "ts": "2026-04-06T18:23:11Z"
  }
}
```

Field-by-field (against ATR-Q.931 §6.2):

| Field     | Value                                   | Rule                                    |
|-----------|-----------------------------------------|-----------------------------------------|
| `channel` | `"sig"`                                 | §6.2 MUST — literal                     |
| `type`    | `"SENT"`                                | §8.1 — stage identifier                 |
| `src`     | hub identity (e.g. `amaru-hub-1`)       | §6.2 MUST                               |
| `dst`     | original sender's `clan_id`             | §6.2 MUST                               |
| `ref`     | copied from the input envelope          | §8.2 MUST                               |
| `ts`      | sub-second ISO-8601 instant, `Z` suffix | §6.2 MUST (distinct from ARC-5322 `ts`) |

> **Note on §8.2 abbreviated example.** The example in §8.2 of the
> spec shows only `channel`/`type`/`ref`/`ts` for readability. The
> authoritative schema is §6.2 — which mandates `src` and `dst` on
> every signaling frame. The reference impl follows §6.2 verbatim.

---

## 5. Error / No-op Cases

The following inputs MUST NOT produce a SENT frame. The hub still
routes the data envelope normally.

### 5.1 No `receipt` array → silent (backward compat)

```json
{"ts":"2026-04-06","src":"jei","dst":"amaru","type":"dispatch",
 "msg":"x","ttl":7,"ack":[],"ref":"jei-099"}
```

Expected: data envelope forwarded to `amaru`. Zero signaling frames.

### 5.2 `receipt` present but `SENT` absent → silent

```json
{"ts":"2026-04-06","src":"jei","dst":"amaru","type":"dispatch",
 "msg":"x","ttl":7,"ack":[],"ref":"jei-100",
 "receipt":["DELIVERED","READ"]}
```

Expected: no SENT frame. (DELIVERED/READ are not yet implemented; the
absence of a receipt for those stages is itself a signal — §8.4.)

### 5.3 `receipt: ["SENT"]` but missing `ref` → skip with warning

```json
{"ts":"2026-04-06","src":"jei","dst":"amaru","type":"dispatch",
 "msg":"x","ttl":7,"ack":[],"receipt":["SENT"]}
```

Expected: no SENT frame. Hub logs a WARNING mentioning `ref`. §8.3
requires `ref` for correlation — without it the receipt is useless.

### 5.4 Sender not locally connected (S2S-origin) → silent

If the originating peer reached the hub via S2S federation (ARC-4601
§17) rather than a direct WebSocket, the local hub does not emit the
SENT receipt. Per §8.4 peer-local semantics, the originating hub owns
the receipt path for its own peers.

---

## 6. Multicast / Broadcast

A broadcast envelope (`dst: "*"`) with `receipt: ["SENT"]` produces
**exactly one** SENT frame, addressed to the sender. The hub does not
emit one SENT per recipient for the SENT stage — that is reserved for
the `DELIVERED` stage (future work, will carry a `peer` field per §8.2).

---

## 7. Frame Size & Rate Limit

| Constraint             | Rule                    | Impl status                            |
|------------------------|-------------------------|----------------------------------------|
| Max signaling frame    | 512 bytes (§6.3)        | Current SENT frame ~140 bytes → OK     |
| Rate limit per dst     | 60 frames/min (§6.3)    | NOT enforced in this impl (Phase 2)    |

Clans consuming receipts SHOULD apply their own back-pressure until the
hub enforces §6.3 locally.

---

## 8. Pointers

- Spec: [`spec/ATR-Q931.md`](../spec/ATR-Q931.md) §6.2, §8.1, §8.2, §8.3, §8.4
- Impl:  [`reference/python/amaru/hub.py`](../reference/python/amaru/hub.py) — `MessageRouter._emit_sent_receipt()` (lines 513–562)
- Tests: [`reference/python/tests/test_hub.py`](../reference/python/tests/test_hub.py) — `TestMessageRouterSentReceipt` (7 test cases covering every row of §5 above plus E2E passthrough invariant)
- PR:    [`dereyesm/amaru-protocol#7`](https://github.com/dereyesm/amaru-protocol/pull/7)
- Commit on `main`: [`4c67736`](https://github.com/dereyesm/amaru-protocol/commit/4c67736)

## 9. Bilateral Validation Checklist (for external clans)

Copy this into an issue or your clan's test harness:

- [ ] Send an input envelope matching §3 above. Confirm the data
      message reaches `amaru`.
- [ ] Confirm a SENT signaling frame arrives back on the sender's
      WebSocket matching §4 above (fields and types).
- [ ] Confirm `ref` in the SENT frame equals the `ref` in the input
      envelope byte-for-byte.
- [ ] Confirm `ts` in the SENT frame is sub-second ISO-8601 with `Z`
      suffix.
- [ ] Confirm §5.1 — envelope without `receipt` produces zero signaling
      frames.
- [ ] Confirm §5.3 — `receipt:["SENT"]` without `ref` produces zero
      signaling frames and a WARNING log line on the hub.
- [ ] (Optional) Confirm §6 — broadcast envelope produces exactly one
      SENT frame.

Report any divergence as a GitHub issue tagged `atr-q931` — this is
the canonical feedback path before DRAFT → PROPOSED.
