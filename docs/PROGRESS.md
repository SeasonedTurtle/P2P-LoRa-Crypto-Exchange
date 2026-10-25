# Progress

## Phase 0

- [x] P0-1 Scaffold, tooling, CI, testnet guard, draft SQLite schema. `pytest`, `ruff`, and `mypy` are green on an empty exchange.
- [x] P0-2 `loradex.sim.airtime` and `docs/AIRTIME.md`. Semtech 36,096 µs check is locked. LongFast full-frame estimate is 1,419,264 µs.
- [x] P0-3 `docs/PROTOCOL.md` and `docs/vectors/protocol_v0.json`. Seq/total are base36 because a 493-chunk proof does not fit in two decimal digits.
- [x] P0-4 `docs/SWAP_DESIGN.md`. Planning size 48,765 bytes per cross-group proof. Default transport is the side channel, with chunking still required.
- [x] P0-5 `docs/THREAT_MODEL.md`.
- [x] P0-6 `docs/OPEN_QUESTIONS.md`. D1–D7 are waiting on a human. Defaults sit in `loradex.config`.

Phase 0 exit is not met yet. The spec, the airtime tests, and the A/B/C choice are in place. A human still has to review D1–D5.

## Not started

- P1-5 credits and P1-6 bonds stay paused until D1–D3 are confirmed.
- Phase 1 as a whole stays closed until the Phase 0 exit review is done.
- No hardware results. See `docs/HARDWARE_TODO.md`.
