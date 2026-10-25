# Open questions

Paused here for a human. Phase 0 built the scaffold, the airtime model, the wire spec, the proof-size spike, and this list. It did not start the fee ledger (P1-5) or the bond ledger (P1-6).

The defaults below are already the values in `loradex.config.Settings`. They are the behavior if you confirm them. They are not a silent assumption.

Reply in this file, or in the pull request, with a yes or a change for each row.

## Decisions

| ID | Question | Default already behind a config flag | Blocks |
|---|---|---|---|
| D1 | How is the $0.05 spam fee paid? | `fee_mode=prepaid_credits`. One LTC deposit, then a SQLite debit per accepted order. This is dust-level custody and has to be described that way | P1-5 |
| D2 | How is the $10 bond held and the $1 slash taken? | `bond_mode=gateway_arbitrated_cltv`. Trader refunds alone after CLTV. Early release is 2-of-2. Slash is applied by the Gateway. Exposure cap $10 | P1-6 |
| D3 | How is a command authenticated? | `command_auth=truncated_mac`. 8-byte truncated MAC, 11 base64url characters, bound to the registered X25519 key. Flags stay unsigned hints | Spec is written for this. Say so if you want `firmware_pkc` instead |
| D4 | How does USD convert to LTC for the fee and the bond? | `price_mode=static_plus_optional_feed`. `static_ltc_usd_cents` is 10000, a placeholder $100 per LTC, not a market price. An optional feed with sanity bounds comes later | P1-5, once D1 is yes |
| D5 | Where do swap secrets live? | `secret_storage=memory_and_encrypted_journal`. Memory for the swap lifetime. Crash recovery uses a journal encrypted with `SWAP_JOURNAL_KEY` from the environment. SQLite stores hashes | Phase 3 swap execution |
| D6 | Partial fills? | `partial_fills=False`. MVP orders fill in full. Micro-chunking is a later flagged mode | None for Phase 1 if this stays |
| D7 | Who runs the Gateway? | One operator. Availability and the D1/D2 powers sit with that operator. Federation is out of scope | None for the MVP |

## Also confirm, from the Phase 0 spikes

1. **Proof transport.** Default `proof_transport=side_channel` (plan option B). The radio carries a SHA-256 commitment. The ~48,765-byte proof stays off the mesh. Chunking still gets built, and `radio_chunked` remains available. A pure-radio swap of both proofs is about 3.9 hours at a 10% duty cycle on LongFast (`docs/AIRTIME.md`, `docs/SWAP_DESIGN.md`).
2. **Litecoin signatures.** Taproot is active on Litecoin. Phase 3 should prefer a BIP340 adaptor signature over the 196-byte ECDSA verifiably-encrypted signature. This does not change D2.
3. **Short proofs.** eprint 2022/1593 is not selected. There is no audited secp256k1↔ed25519 instance to wrap. Option C waits on that library.
4. **Refund delay.** `ltc_refund_delay_s` is 6 hours, with 10 XMR confirmations and 6 LTC confirmations. Shrink it only after the refund tests exist.
5. **Unsigned flags.** Channel 1 flags can be injected by anyone with the PSK. The spec leaves them unsigned on purpose, and puts fund-moving steps in signed DMs. Say if you want a MAC on flags too.

## What proceeds after you answer

- Confirming D1–D3 unblocks P1-5 and P1-6.
- Phase 0's exit criteria also ask you to review D1–D5 before Phase 1 is treated as open. P1-1 through P1-4 and P1-7 through P1-10 do not move funds. They still wait on that review because the plan refuses to start a phase whose previous exit criteria are open.
- No radio work is required for Phase 1. `docs/HARDWARE_TODO.md` is the human checklist for Phase 2.
