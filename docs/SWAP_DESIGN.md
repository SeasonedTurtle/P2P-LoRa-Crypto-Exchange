# XMR↔LTC swap design

Phase 0 spike for risk R2. No curve arithmetic is implemented here, and none should be written from scratch. Phase 3 wraps a maintained library.

## Why the proof is large

Monero has no scripting. An XMR↔LTC atomic swap cannot use an HTLC on the Monero side. The construction used by Farcaster / COMIT-style swaps is:

1. An adaptor signature on the Litecoin side, so that publishing the LTC claim reveals a secret.
2. A cross-group discrete-log equality proof between secp256k1 (Litecoin) and ed25519 (Monero), so each party can verify that the counterparty's two public keys share one scalar without seeing the scalar.

The shared scalar has to sit below the ed25519 group order, so the bit proof covers **252 bits**. The practical encoding commits to each bit on both curves and attaches a ring signature per bit (MRL-0010, with the borromean stack described in tecnovert's implementation notes of 2020-09-10).

## Measured sizes

`loradex.sim.proof_size.borromean_dleq_bytes` evaluates the tecnovert length formula `129 + 193 × n`.

| Object | Bytes | Source |
|---|---:|---|
| Borromean cross-group DLEQ, 252 bits | **48,765** | `129 + 193 × 252`. Same figure as Serai `CompromiseLinear` |
| Serai `ConciseLinear` (2 bits per ring layer) | 44,607 | Serai `crypto/dleq` README benchmark. Unaudited upstream |
| Serai `ClassicLinear` | 56,829 | same table |
| Serai `EfficientLinear` | 65,145 | same table |
| ECDSA verifiably-encrypted signature | 196 | tecnovert notes: two points, `s`, and a same-curve DLEQ |
| BIP340 Schnorr signature | 64 | signature size only; the cross-group proof is extra |

This repo did not generate a proof. The 48,765 figure is the encoding formula, and it matches a published benchmark of the same size. Serai's README says those linear proofs are experimental and not recommended. They are planning numbers, not a library choice.

Litecoin has activated Taproot (BIP341/342) and MWEB. Taproot makes a Schnorr adaptor signature a fit for the LTC side. It does not add covenants, so it does not make the fidelity-bond slash trustless. The 64-byte signature is not the bulk. The cross-group proof is.

### What a "small proof" paper does and does not say

eprint 2022/1593 gives a Σ-protocol whose short-witness examples are about 900–1,600 **bits** on Ristretto and BLS12-381, which is where the "about 118 bytes" remark comes from. That table excludes the range proof, and the short rows are not a 252-bit secp256k1↔ed25519 witness. The paper's own route for a large scalar is to split it and attach range proofs (Bulletproofs in one group are on the order of 700–800 bytes per group of ranges in their citation). Nobody has shipped an audited instance of that protocol for this swap. Option C is not available to implement under the plan's crypto rule.

## Radio cost of the proof we can actually name

DM text frames carry **99 raw bytes** each (`docs/PROTOCOL.md`). Base36 chunk counts fit: 493 is `dp`, and two characters count up to 1,295.

| Packing | Chunks per 48,765-byte proof |
|---|---:|
| Text frame, 99 raw bytes | **493** |
| Hypothetical binary 140-byte frame | 349 |
| Text frame, 44,607-byte ConciseLinear proof | 451 |

Each party sends one proof, so a swap is **986** text chunks before acknowledgements and retries. A missing-chunk bitmap for 493 chunks is 62 bytes and fits in one NACK.

On Meshtastic LongFast, a 156-byte frame (140 bytes of application data plus a 16-byte framing estimate) takes **1,419,264 µs**. The arithmetic is in `docs/AIRTIME.md`:

- about **700 seconds** of continuous transmit per proof
- about **23 minutes** of continuous transmit for both proofs
- about **3.9 hours** at a 10% duty cycle, with a quiet channel and no retries

Encoding is not the bottleneck. Dropping base64 still leaves a few hundred packets.

## Choice

**Option B is the default. Option A's chunking layer is still mandatory.**

`Settings.proof_transport` defaults to `side_channel`.

| Bytes | Where they go |
|---|---|
| Cross-group DLEQ proof (public, zero-knowledge) | Side channel: LAN, an optional internet path, or another link the two gateways already share |
| SHA-256 of that proof | One radio DM, type `P`, one chunk. The verifier accepts the blob only when the hash matches |
| Adaptor signatures, public keys, view key needed by the counterparty | Radio DM, types `Q` and `Z`, encrypted to the counterparty's X25519 key |
| Status flags | Channel 1, unsigned hints |

The side channel does not have to hide the proof. It does have to be bound to the radio commitment, or a substitute proof would verify against different keys. Spend keys and adaptor scalars stay off both channels. They are not stored in SQLite in the clear (`docs/OPEN_QUESTIONS.md`, D5).

`radio_chunked` remains a config value for a pure off-grid attempt. It uses the same chunk header, ACK prefix, NACK bitmap, resume, and reassembly timeout. It is not the default, because the airtime above does not leave room for a market.

Option C (fewer cut-and-choose rounds, or the 2022 short proof) waits on an audited implementation for secp256k1 and ed25519. Cutting the 252-bit proof down by dropping bits would assert equality of a shorter scalar than the curve order. That tradeoff is not taken.

## Timeout asymmetry

Monero has no script timelock. The deadline a human can point at is on Litecoin. The party who reveals second still needs time to broadcast a claim after the reveal, after radio loss, and after the Gateway has been offline.

Defaults in `loradex.config.Settings`, chosen to be conservative rather than tight:

| Setting | Default | Why this wide |
|---|---:|---|
| `xmr_confirmations` | 10 | About 20 minutes at a 2-minute block |
| `ltc_confirmations` | 6 | About 15 minutes at a 2.5-minute block |
| `ltc_refund_delay_s` | 21,600 (6 hours) | Covers those confirmations, a Gateway outage, and a slow side channel |

Phase 3 tests the refund path to the same bar as the happy path before anyone shrinks these. The pure-radio transport needs a longer refund delay than 6 hours, because the proof transfer itself can take hours. That is another reason it is not the default.

## Custody, stated plainly

The swap of the traded XMR and LTC is the atomic-swap path above. Two surrounding mechanisms are not trustless, and the software must not describe the whole system as zero-custody:

- **Order fee (D1 default).** One on-chain transaction per $0.05 order is a poor fit for 2.5-minute blocks. The default is a prepaid LTC balance the Gateway debits in SQLite. That balance is dust-level custody.
- **Fidelity bond (D2 default).** The bond is a 2-path Litecoin output: the trader alone after a CLTV timeout, or 2-of-2 (trader and Gateway) for an early release. A $1 slash in the MVP is applied by the Gateway. Exposure is capped at the $10 bond. A later design can replace that with pre-signed penalty transactions. Litecoin's lack of covenants is why the slash is not trustless. Taproot does not change that.

D1 and D2 are config flags today. The ledgers that would move those funds are not started until a human confirms the decisions.
