# LoRa-DEX: Implementation Plan for Cursor Agent

> **Goal:** An off-grid, zero-custody (where technically possible) decentralized exchange trading **XMR (base)** against **LTC (quote)** over low-bandwidth LoRa mesh networks, settled by atomic swaps, coordinated by a Python Gateway.
>
> **How to use this file:** Read Sections 0-3 fully before writing code. Then execute Phases in order. Do not start a phase until the previous phase's **Exit Criteria** all pass. Items marked **[DECISION]** must be resolved with the human (see Section 9) before the dependent task begins; until then, implement the stated default behind a config flag.

---

## 0. Agent Operating Rules (non-negotiable)

1. **Testnet only.** LTC `testnet4`/regtest, XMR `stagenet`/regtest. Mainnet code paths must be unreachable unless `NETWORK=mainnet` AND `--i-understand-this-is-real-money` are both set. Default everything to test networks.
2. **No secrets in the repo.** No keys, seeds, PSKs, RPC passwords committed. Use `.env` (gitignored) + `.env.example`. Never log private keys, adaptor secrets, or channel PSKs.
3. **Hardware is a human step.** When a task needs a physical radio, STOP and write a checklist for the human into `docs/HARDWARE_TODO.md`. Do not fake hardware results; use the mock radio for CI.
4. **Everything is tested before moving on.** Each module ships with unit tests. `pytest -q` and `ruff check` must pass before a task is marked done.
5. **Small, reviewable commits** per task, message format: `phase<N>/<task-id>: <summary>`.
6. **Spec first.** Wire formats live in `docs/PROTOCOL.md` and are the single source of truth; code follows the spec, and spec changes come in the same commit as code changes.
7. **Ask, don't guess,** on anything cryptographic or involving fund custody. Write the question in `docs/OPEN_QUESTIONS.md` and continue with other work.

---

## 1. Architecture Summary

```
 [Trader radio nodes]  <--LoRa-->  [Repeaters / Room Server]  <--LoRa-->  [Gateway radio]
                                                                               |
                                                                  Gateway host (Python)
                                                       ┌───────────────────────┴───────────────────────┐
                                                  listener.py                                    observer.py
                                          (radio RX/TX, parse, rate-limit,                 (watches LTC + XMR chains,
                                           order book, swap coordination)                  confirmations, timeouts)
                                                       └──────────── SQLite (WAL) ─────────────────────┘
                                                                               |
                                                              litecoind RPC  /  monero-wallet-rpc
```

### Channels
| Channel | Visibility | Purpose |
|---|---|---|
| 0, Public Ticker | Unencrypted | Gateway broadcasts market price/top-of-book |
| 1, Trading Floor | AES-256 PSK | Order commands (`!b`, `!s`, `!c`, `!t`) and short status flags |
| DM | Per-node E2E | Registration, key material, adaptor signatures |

> **Security note to encode in docs:** Channel 1's PSK is *shared*. Anyone holding it can read/inject. Treat it as an **anti-casual-eavesdropper + spam-gate**, not confidentiality. All swap secrets must additionally be encrypted application-side to the counterparty's public key (ECIES/X25519 + ChaCha20-Poly1305), not left to radio-layer DM encryption alone.

### Network evolution
- **MVP:** Meshtastic, ~5-mile range, flood routing.
- **Production:** MeshCore Star/Tree: Room Server + Repeaters, directed routing (avoids flood collapse).
- The radio layer **must** be behind an abstract interface (`RadioAdapter`) so Meshtastic ↔ MeshCore is a drop-in swap.

---

## 2. Hard Constraints and Known Technical Risks

Read these before designing anything. They drive the plan.

### R1: Packet size budget (verify in Phase 0)
- Meshtastic payload ≈ 233 bytes max; MeshCore text messages are typically smaller (~150-160 bytes). **Assume 140 usable bytes** as a config constant `MAX_PAYLOAD_BYTES=140` and validate empirically.
- Base64 inflates by 4/3. 140 bytes of Base64 carries only **~105 raw bytes**. All framing must be counted against this.

### R2: Cross-curve atomic swap proof size (**biggest risk**)
- XMR has no scripting, so XMR↔LTC swaps use **adaptor signatures + a cross-group DLEQ proof** (secp256k1 ↔ ed25519), Farcaster/COMIT style.
- The cross-group DLEQ proof can be **tens of kilobytes**, which is hundreds of 100-byte radio packets, which is incompatible with a naive "exchange everything over LoRa" design at LoRa airtimes and duty cycles.
- **Phase 0 must measure this** and choose one of:
  - **(A)** Chunked, resumable, reassembled transfer over radio (slow but pure off-grid).
  - **(B)** Gateway-assisted: bulky proofs travel over an optional internet/LAN side-channel when available; the radio carries only hashes/commitments + signatures, with verification against the commitment.
  - **(C)** Reduce proof size via fewer cut-and-choose rounds, with a documented security-level tradeoff.
- Whatever is chosen, the protocol needs **chunking with sequence numbers, per-chunk ACK/NACK bitmap, resume-after-loss, and a total reassembly timeout**.

### R3: "Zero-custody" vs. fidelity bonds and fee prepayment
- **Spam fee ($0.05 LTC/order):** one on-chain LTC tx per order is too slow (2.5 min blocks) and fee-inefficient. **[DECISION D1]** Default: **prepaid order credits** (user deposits LTC to a per-user deposit address once; Gateway debits $0.05 per order in SQLite). This is *dust-level custodial*, so document it explicitly as a deliberate exception to zero-custody.
- **$10 LTC fidelity bond with $1 slash:** Litecoin has no covenants, so a fully trustless slash is not possible. **[DECISION D2]** Default for MVP: bond locked in a **2-path script**, which the trader can reclaim alone after a CLTV timeout, or 2-of-2 (trader + gateway) for early release. Slashing in MVP is gateway-arbitrated (documented trust assumption, capped at $10 exposure). Later phase: pre-signed per-swap penalty transactions to remove the trust.
- Never describe the system as fully zero-custody in docs/UI; describe precisely what is and isn't trusted.

### R4: Identity & spoofing
- Raw Node IDs can be spoofed on older Meshtastic firmware. Registration (DM) must bind **Node ID ↔ public key ↔ LTC address**, and all subsequent privileged commands should carry a short signature/MAC (truncated, e.g. 8 bytes) or rely on firmware PKC-verified DMs. **[DECISION D3]**: choose per-command MAC vs. firmware PKC reliance.

### R5: Airtime is the real currency
- Build an **airtime calculator** (LoRa SF/BW/CR/preamble → ms per packet) in Phase 0 and use it in the simulator to predict capacity: orders/hour, swaps/hour, per node and per network.
- US 915 MHz ISM duty cycle/power rules apply to the human's deployment; surface warnings in docs (not legal advice).

### R6: Atomic swap timeout asymmetry
- Monero has ~2 min blocks / 10-confirmation unlock; LTC ~2.5 min blocks. Refund timelocks must be sized so the party who reveals second always has time to act, **accounting for radio latency and the Gateway being offline**. Encode timeouts as config with conservative defaults and test the refund path as thoroughly as the happy path.

---

## 3. Repository Layout (create in Phase 0)

```
lora-dex/
├── README.md
├── LORA_DEX_PLAN.md              # this file
├── AGENTS.md                     # copy of Section 0 rules for Cursor
├── .cursor/rules/loradex.mdc     # short rules: testnet-only, spec-first, test-first
├── pyproject.toml                # python>=3.11, ruff, pytest, hypothesis, mypy
├── .env.example
├── docs/
│   ├── PROTOCOL.md               # wire formats, flags, state machines (source of truth)
│   ├── THREAT_MODEL.md
│   ├── AIRTIME.md                # capacity math
│   ├── SWAP_DESIGN.md            # adaptor-sig flow, message sizes, timelocks
│   ├── HARDWARE_TODO.md          # human checklist
│   └── OPEN_QUESTIONS.md
├── src/loradex/
│   ├── config.py                 # typed settings; testnet defaults; mainnet guard
│   ├── protocol/
│   │   ├── codec.py              # encode/decode commands, base64, framing
│   │   ├── commands.py           # !b !s !c !t parsing -> dataclasses
│   │   ├── flags.py              # 1-char status flag enum
│   │   └── chunking.py           # fragmenter/reassembler w/ ack bitmap + resume
│   ├── engine/
│   │   ├── orderbook.py          # price-time priority, TTL expiry
│   │   ├── matcher.py
│   │   ├── ratelimit.py          # per-node msg + active-order limits
│   │   ├── credits.py            # prepaid order-fee ledger
│   │   └── bonds.py              # fidelity bond state machine
│   ├── db/
│   │   ├── schema.sql
│   │   ├── migrations/
│   │   └── repo.py               # all SQL lives here; no SQL elsewhere
│   ├── radio/
│   │   ├── base.py               # RadioAdapter ABC (send, recv, channel mgmt)
│   │   ├── mock.py               # in-process lossy/latent simulated mesh
│   │   ├── meshtastic_adapter.py
│   │   ├── meshcore_adapter.py
│   │   └── txqueue.py            # priority queue + 30s TTL drop + pacing
│   ├── chain/
│   │   ├── base.py               # ChainClient ABC
│   │   ├── ltc.py                # litecoind RPC (testnet/regtest)
│   │   ├── xmr.py                # monero-wallet-rpc (stagenet/regtest)
│   │   └── mock.py               # deterministic fake chains for tests
│   ├── swap/
│   │   ├── state_machine.py      # explicit states + transitions + persistence
│   │   ├── adaptor.py            # adaptor sig primitives (wrap vetted libs only)
│   │   ├── timelocks.py
│   │   └── microchunk.py         # secondary mode (see Phase 3)
│   ├── gateway/
│   │   ├── listener.py           # entrypoint: radio RX loop -> engine
│   │   ├── observer.py           # entrypoint: chain watcher -> swap advances
│   │   └── ticker.py             # Channel 0 price broadcaster
│   ├── sim/
│   │   ├── airtime.py            # LoRa airtime calculator
│   │   └── network_sim.py        # many-node load simulation
│   └── cli/
│       └── mockdex.py            # terminal mock engine (Phase 1)
└── tests/
    ├── unit/  property/  integration/  e2e/
```

> **Crypto rule:** Do **not** implement elliptic-curve or DLEQ primitives from scratch. Wrap audited libraries (e.g. `coincurve`/libsecp256k1, `PyNaCl`, and a maintained implementation of the Farcaster/COMIT cross-group DLEQ or `monero-serialize`-style tooling). If no suitable Python library exists, write a thin subprocess/FFI wrapper and file the question in `OPEN_QUESTIONS.md`.

---

## 4. Wire Protocol (draft; finalize in Phase 0 task P0-3)

### 4.1 Channel 1 commands (Trader → Gateway)
Plain ASCII, space-separated, ≤ 40 bytes typical. Quantities in XMR, prices in LTC per XMR.

| Cmd | Format | Example | Meaning |
|---|---|---|---|
| `!b` | `!b <qty> <px>` | `!b 1.5 0.0042` | Buy XMR |
| `!s` | `!s <qty> <px>` | `!s 0.8 0.0043` | Sell XMR |
| `!c` | `!c <oid>` | `!c k7f2` | Cancel order |
| `!t` | `!t <oid>` | `!t k7f2` | Take an order |
| `!p` | `!p` | `!p` | Ping/status |

- `oid`: 4-char base36, Gateway-assigned, collision-checked.
- Decimal precision limits defined in spec (e.g. qty to 1e-4 XMR, px to 1e-6 LTC) so parsing is unambiguous.
- Optional trailing 8-byte truncated MAC per **[D3]**.

### 4.2 One-character status flags (Gateway → Trader)
Format: `<flag><oid>[<arg>]`, e.g. `Ak7f2`. Proposed set (finalize in spec):

| Flag | Meaning | Flag | Meaning |
|---|---|---|---|
| `A` | Order accepted | `K` | Key-exchange step due (details via DM) |
| `R` | Rejected (+1-char reason: `r` rate, `f` fee/credit, `b` bond, `p` parse, `l` limit) | `L` | Funds locked |
| `M` | Matched | `C` | Confirmed on-chain |
| `X` | Cancelled/aborted | `D` | Swap done |
| `E` | Expired (60-min TTL) | `S` | Slashed counterparty abandonment |

### 4.3 Channel 0 ticker (Gateway → all)
Single packet, ≤ 100 bytes, every 60 s (configurable):
`T|XMR/LTC|<last>|<bid>|<ask>|<24h vol>|<seq>`

### 4.4 DM frames
`<type 1ch><seq 2ch><total 2ch><b64 payload>` with chunk header counted in the budget. Types: `G` register, `H` bond proof, `Q` swap-key msg, `Z` adaptor-sig msg, `P` proof chunk, `N` NACK bitmap, `Y` ACK.

### 4.5 Gateway TX queue
- Priority: swap DM frames > match/status flags > order acks > ticker.
- **30-second TTL**: any queued packet older than 30 s is dropped (and logged), except swap-critical frames, which are re-queued with backoff up to the swap's own timeout. Document this exception.
- Pacing from `airtime.py` so Gateway never exceeds configured duty cycle.

### 4.6 Limits
- Per Node ID: **2 msgs/min** (sliding window), **2 active orders**; orders carry implicit **60-min TTL**. Violations return `Rr`/`Rl` and increment a penalty counter (3 strikes → temporary mute, configurable).
- Fee: **$0.05 LTC-equivalent** debited per accepted order (see R3/D1). Price source for USD↔LTC conversion: configurable static rate + optional feed; **[DECISION D4]**.

---

## 5. Data Model (SQLite, WAL mode, foreign keys ON)

```sql
users(node_id PK, pubkey, ltc_addr, deposit_addr, credits_sat, strikes, muted_until, created_at)
bonds(id PK, node_id FK, txid, vout, amount_sat, state, locktime, created_at, slashed_sat)
orders(oid PK, node_id FK, side, qty_atomic, px_atomic, state, created_at, expires_at)
swaps(id PK, buy_oid FK, sell_oid FK, state, ltc_txid, xmr_txid, timelock_ltc, timelock_xmr,
      created_at, updated_at)
swap_steps(id PK, swap_id FK, step, direction, payload_hash, ts)   -- audit trail, no secrets
packets(id PK, ts, channel, node_id, direction, flag_or_cmd, size, dropped, reason)
ratelimit_events(node_id, ts)
chain_cursor(chain PK, height, hash)
```

Rules: amounts stored as **integers in atomic units** (never floats). All state transitions in a single transaction. Secrets/adaptor scalars are **never** stored in plaintext (encrypt at rest with a key from env, or keep in memory only for the swap's lifetime; **[DECISION D5]**: choose).

---

## 6. Phased Roadmap

### Phase 0: Spec lock and risk spikes (pre-work)
| ID | Task | Output |
|---|---|---|
| P0-1 | Scaffold repo per Section 3, tooling (ruff, mypy, pytest, hypothesis), CI config | Green empty test run |
| P0-2 | Write `sim/airtime.py` + `docs/AIRTIME.md` (SF7-SF12, BW125/250, LongFast preset); compute capacity tables | Tested calculator |
| P0-3 | Finalize `docs/PROTOCOL.md` from Section 4 with byte-exact examples and golden test vectors | Spec + vectors |
| P0-4 | **Spike R2:** research & document cross-group DLEQ/adaptor-signature message sizes for XMR↔LTC; recommend A/B/C | `docs/SWAP_DESIGN.md` with a measured size table |
| P0-5 | Threat model: spam, DDoS/jamming, Sybil, replay, node-ID spoofing, malicious Gateway, griefing, key-material leakage via shared PSK | `docs/THREAT_MODEL.md` |
| P0-6 | Compile `docs/OPEN_QUESTIONS.md` with decisions D1-D5 and recommended defaults | Human sign-off list |

**Exit criteria:** spec has golden vectors; airtime tests pass; swap design states a concrete choice (A/B/C) with numbers; human has reviewed D1-D5.

---

### Phase 1: Terminal mock engine (no radio, no chains)
Goal: prove the exchange logic, limits, and economics in-process.

| ID | Task |
|---|---|
| P1-1 | `protocol/codec.py` + `commands.py`: parse/encode all commands; reject malformed input safely. **Property tests (hypothesis):** `decode(encode(x)) == x`, parser never raises on arbitrary bytes. |
| P1-2 | `db/schema.sql`, migrations, `repo.py` with integer-atomic amounts |
| P1-3 | `engine/orderbook.py` + `matcher.py`: price-time priority, partial fills policy (**default: no partial fills in MVP**, documented), TTL expiry sweep |
| P1-4 | `engine/ratelimit.py`: 2 msg/min sliding window, 2 active orders, strike/mute logic |
| P1-5 | `engine/credits.py`: $0.05 fee debit, insufficient-credit rejection, idempotent (a replayed packet must not double-charge) |
| P1-6 | `engine/bonds.py`: bond states (`none → posted → active → slashed/released`), $1 slash accounting, mock proofs |
| P1-7 | `radio/mock.py`: simulated mesh with configurable loss %, latency, duplication, reordering, duty-cycle accounting; `radio/txqueue.py` with 30 s TTL |
| P1-8 | `cli/mockdex.py`: interactive terminal where you act as N traders (`as alice: !b 1 0.004`) against the Gateway; prints the radio-level view (bytes, airtime) alongside the logical view |
| P1-9 | `swap/state_machine.py` with **mock chains**: full happy path, counterparty abandon → refund + slash, timeout paths, Gateway restart mid-swap (state recovered from SQLite) |
| P1-10 | `sim/network_sim.py`: 50-200 simulated nodes; report orders/hr, drop rate, queue depth, airtime utilization |

**Exit criteria:**
- ≥ 90% line coverage on `protocol/` and `engine/`.
- Property tests pass 10k examples.
- Scripted scenarios pass: happy swap, double-submit (idempotent), rate-limit trip, abandonment slash, restart recovery.
- Simulation shows queue stays stable at the target load, with documented capacity ceiling.

---

### Phase 2: Radio integration (Meshtastic MVP, ~5 mi)
| ID | Task |
|---|---|
| P2-1 | `RadioAdapter` ABC finalized; `meshtastic_adapter.py` using the official `meshtastic` Python library (serial/TCP); channel config for Ch0 (open) / Ch1 (AES-256 PSK) via env |
| P2-2 | `gateway/listener.py`: RX loop → codec → engine → TX queue; graceful shutdown; reconnect on serial loss |
| P2-3 | `gateway/ticker.py`: Ch0 broadcaster with pacing |
| P2-4 | DM registration flow: node sends `G` frame with pubkey + LTC address; Gateway binds identity, replies with deposit address + bond instructions |
| P2-5 | `protocol/chunking.py` wired to real radio: fragmentation, ACK/NACK bitmap, resume. **Test with `radio/mock.py` at 30% loss first.** |
| P2-6 | Field-test harness: logs RTT, loss, airtime per packet to `field_logs/`; script to summarize |
| P2-7 | Write `docs/HARDWARE_TODO.md`: radios, firmware versions, channel/PSK setup, antenna notes, field-test procedure *(human performs)* |

**Exit criteria:** Two real nodes + one Gateway node complete register → deposit-credit (mocked chain) → order → match → status flags end-to-end; chunked transfer of a ≥ 4 KB blob survives 30% simulated loss and a real-radio test; field-test logs show actual vs. predicted airtime within 25%.

---

### Phase 3: Testnet atomic swaps
| ID | Task |
|---|---|
| P3-1 | `chain/ltc.py`: regtest/testnet RPC client (address gen, UTXO watch, tx build/broadcast, CLTV scripts) |
| P3-2 | `chain/xmr.py`: stagenet/regtest `monero-wallet-rpc` client (lock tx to shared key, view-key sweep, confirmation tracking) |
| P3-3 | `swap/adaptor.py` + `timelocks.py`: implement the approved design from `SWAP_DESIGN.md` using vetted libraries. Include **negative tests**: invalid adaptor sig rejected, wrong DLEQ rejected, replayed message rejected |
| P3-4 | `gateway/observer.py`: watches both chains, advances swap state at required confirmations, triggers refund paths at timelock expiry |
| P3-5 | Fidelity bond on LTC testnet per D2 (script, funding proof verification, release, $1 slash payout) |
| P3-6 | Prepaid credits: deposit address per user, confirmation threshold, credit accounting reconciliation |
| P3-7 | Radio-coordinated swap end-to-end on testnet, over real/mock radio |
| P3-8 | `swap/microchunk.py` **secondary mode**: split a large trade into N small swaps (each within bond cap) to limit loss exposure; N and min size configurable. Document that it multiplies airtime use, and gate behind a flag. |
| P3-9 | Chaos tests: kill Gateway mid-swap, drop 50% of packets, delay a party past the timelock, double-spend attempt on the LTC side; **every one must end in refund or completion, never stuck/lost funds** |

**Exit criteria:** 20 consecutive successful testnet swaps; every failure-injection scenario resolves safely; independent re-read of refund-path logic documented by the agent in `docs/REFUND_AUDIT.md`; human reviews crypto code before Phase 4.

---

### Phase 4: MeshCore production deployment
| ID | Task |
|---|---|
| P4-1 | `meshcore_adapter.py` implementing `RadioAdapter`; confirm payload limit and adjust `MAX_PAYLOAD_BYTES` |
| P4-2 | Topology docs: Room Server + Repeater placement for city-wide Star/Tree; coverage planning checklist *(human)* |
| P4-3 | Re-run `network_sim` with directed routing assumptions; compare against flood-routing baseline; update capacity numbers |
| P4-4 | Ops hardening: systemd units for `listener`/`observer`, log rotation, SQLite backups, metrics (queue depth, drops, airtime %), alerting on observer lag |
| P4-5 | Security pass: dependency audit, fuzz the codec, review THREAT_MODEL against final implementation, rotate/derive PSK procedure |
| P4-6 | Staged rollout plan: closed beta with capped bonds/credits, kill-switch (`HALT` file/flag stops new orders but continues settling in-flight swaps) |
| P4-7 | Legal/compliance checklist doc for the operator (radio regulations, exchange/money-transmission questions by jurisdiction). Informational only, flag for human legal review |

**Exit criteria:** Closed-beta runbook approved by human; all prior exit criteria still green in CI; kill-switch tested.

---

## 7. Testing Strategy (applies to all phases)

| Layer | Tooling | Must cover |
|---|---|---|
| Unit | pytest | codec, ratelimit, credits, bonds, orderbook |
| Property | hypothesis | codec round-trip, parser totality, ledger conservation (credits never created/destroyed unexpectedly) |
| Integration | pytest + mock radio/chain | listener↔engine↔db, restart recovery |
| Simulation | `sim/network_sim.py` | congestion, TTL drops, airtime ceiling |
| Chaos | fault-injection hooks | loss, dup, reorder, partition, crash, clock skew |
| E2E testnet | scripts | full swaps, refund paths |

Invariants to assert continuously: no float money; no state transition outside the allowed table; a swap is never in a state with both parties' funds unrecoverable; same packet processed twice has the same effect as once.

---

## 8. Definition of Done (per task)
- [ ] Code + tests + docs updated
- [ ] `ruff`, `mypy`, `pytest -q` green
- [ ] Spec (`PROTOCOL.md`/`SWAP_DESIGN.md`) matches the code
- [ ] No secrets logged; testnet-only guard intact
- [ ] Task checked off in `docs/PROGRESS.md` with a one-line note

---

## 9. Decisions Needing Human Input

| ID | Question | Recommended default |
|---|---|---|
| D1 | How is the $0.05 spam fee paid? | Prepaid credits via one-time LTC deposit (dust-level custodial, documented) |
| D2 | How is the $10 bond held and slashed? | CLTV-refundable bond with gateway-arbitrated $1 slash in MVP; pre-signed penalty txs later |
| D3 | Command authentication | Truncated per-command MAC bound to the registered pubkey |
| D4 | USD↔LTC pricing for fees/bonds | Static configurable rate + optional external feed with sanity bounds |
| D5 | Swap secret storage | Memory-only for swap lifetime + encrypted-at-rest journal for crash recovery |
| D6 | Partial fills | Not in MVP (use micro-chunking mode instead) |
| D7 | Who runs the Gateway? | Single operator for MVP (acknowledged trust/availability point); federation is a later phase |

---

## 10. First Actions for the Agent
1. Create `AGENTS.md` and `.cursor/rules/loradex.mdc` from Section 0.
2. Scaffold the repo (P0-1) and open `docs/PROGRESS.md`.
3. Do P0-2 (airtime calculator) and P0-4 (swap proof-size spike) **first**, since their results can reshape Phases 2-3.
4. Produce `docs/OPEN_QUESTIONS.md` (P0-6) and pause for human answers on D1-D3 before starting Phase 1 tasks P1-5 and P1-6.
5. Proceed through Phase 1 without waiting on hardware.
