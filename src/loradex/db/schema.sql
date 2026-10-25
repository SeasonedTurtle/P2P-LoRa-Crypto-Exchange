-- Draft schema from LORA_DEX_PLAN.md Section 5.
-- Phase 1 task P1-2 owns migrations and the repository module.
-- Amounts are integers in atomic units. The connection turns WAL and foreign
-- keys on; those are connection settings, not table definitions.

PRAGMA foreign_keys = ON;

CREATE TABLE users (
    node_id TEXT PRIMARY KEY,
    pubkey BLOB NOT NULL,
    ltc_addr TEXT NOT NULL,
    deposit_addr TEXT,
    credits_sat INTEGER NOT NULL DEFAULT 0 CHECK (credits_sat >= 0),
    strikes INTEGER NOT NULL DEFAULT 0 CHECK (strikes >= 0),
    muted_until INTEGER,
    created_at INTEGER NOT NULL
);

CREATE TABLE bonds (
    id INTEGER PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES users (node_id),
    txid TEXT,
    vout INTEGER,
    amount_sat INTEGER NOT NULL CHECK (amount_sat >= 0),
    state TEXT NOT NULL,
    locktime INTEGER,
    created_at INTEGER NOT NULL,
    slashed_sat INTEGER NOT NULL DEFAULT 0 CHECK (slashed_sat >= 0)
);

CREATE TABLE orders (
    oid TEXT PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES users (node_id),
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    qty_atomic INTEGER NOT NULL CHECK (qty_atomic > 0),
    px_atomic INTEGER NOT NULL CHECK (px_atomic > 0),
    state TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);

CREATE TABLE swaps (
    id INTEGER PRIMARY KEY,
    buy_oid TEXT REFERENCES orders (oid),
    sell_oid TEXT REFERENCES orders (oid),
    state TEXT NOT NULL,
    ltc_txid TEXT,
    xmr_txid TEXT,
    timelock_ltc INTEGER,
    timelock_xmr INTEGER,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- Audit trail of swap steps. Payload hashes only; never secrets.
CREATE TABLE swap_steps (
    id INTEGER PRIMARY KEY,
    swap_id INTEGER NOT NULL REFERENCES swaps (id),
    step TEXT NOT NULL,
    direction TEXT NOT NULL,
    payload_hash BLOB NOT NULL,
    ts INTEGER NOT NULL
);

CREATE TABLE packets (
    id INTEGER PRIMARY KEY,
    ts INTEGER NOT NULL,
    channel TEXT NOT NULL,
    node_id TEXT,
    direction TEXT NOT NULL CHECK (direction IN ('rx', 'tx')),
    flag_or_cmd TEXT,
    size INTEGER NOT NULL CHECK (size >= 0),
    dropped INTEGER NOT NULL DEFAULT 0 CHECK (dropped IN (0, 1)),
    reason TEXT
);

CREATE TABLE ratelimit_events (
    node_id TEXT NOT NULL,
    ts INTEGER NOT NULL
);

CREATE TABLE chain_cursor (
    chain TEXT PRIMARY KEY,
    height INTEGER NOT NULL,
    hash TEXT NOT NULL
);
