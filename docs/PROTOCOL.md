# LoRa-DEX wire protocol

Version 0. This file is the source of truth for bytes on the radio. The machine-readable copy of every example below is `docs/vectors/protocol_v0.json`. A change to a vector updates both files in the same commit.

Channel 1's shared key is a spam gate. It is not confidentiality. Swap material is encrypted to the counterparty's X25519 key at this layer. Status flags on channel 1 are hints. A flag is not authorization to move funds.

## Budgets

| Limit | Bytes | What happens past it |
|---|---:|---|
| Application payload (`MAX_PAYLOAD_BYTES`) | 140 | Frame is not sent |
| Channel 1 command | 64 | Gateway rejects it with `Rp` |
| Channel 0 ticker | 100 | Gateway does not transmit it |
| Typical command | 40 | Allowed, just no longer "short" |

140 bytes of base64 carry 105 raw bytes. DM frames spend 5 characters on the header, and each chunk's base64 is padded on its own, so one DM chunk carries **99 raw bytes**. See `loradex.sim.proof_size.raw_bytes_per_text_chunk`.

## Units

Quantities are XMR. Prices are LTC per 1 XMR. The wire format is decimal ASCII. Storage is integers.

| Field | Wire | Atomic unit | Quantum enforced on the wire |
|---|---|---|---|
| Quantity | at most 4 fractional digits | piconero (10⁻¹² XMR) | 0.0001 XMR = 10⁸ piconero |
| Price | at most 6 fractional digits | litoshis per 1 XMR (10⁻⁸ LTC) | 10⁻⁶ LTC per XMR = 100 litoshis |

`!b 1.5 0.0042` is 1.5 XMR at 0.0042 LTC per XMR, which is `qty_atomic = 1500000000000` and `px_atomic = 420000`. Leading zeros are rejected (`0.5` is valid, `00.5` is not). A trailing dot is rejected.

Order ids are 4 characters from `0-9a-z`, assigned by the Gateway, checked for collisions.

## Channel 1 commands

ASCII, space-separated. Under the D3 default (`truncated_mac`) a command ends with an 11-character unpadded base64url MAC over the command text that precedes the MAC. The MAC is the first 8 bytes of HMAC-SHA256(key, command), and the key is derived from the registered X25519 identity. The example MAC below is the test pattern `0x11` repeated, not a real tag.

| Command | Grammar | Example |
|---|---|---|
| Buy XMR | `!b <qty> <px> <mac>` | `!b 1.5 0.0042` |
| Buy, with the test MAC | same, MAC required by default | `!b 1.5 0.0042 ERERERERERE` |
| Sell XMR | `!s <qty> <px> <mac>` | `!s 0.8 0.0043` |
| Cancel | `!c <oid> <mac>` | `!c k7f2` |
| Take | `!t <oid> <mac>` | `!t k7f2` |
| Ping | `!p <mac>` | `!p` |

The examples without a MAC are the grammar illustration. With `command_auth=truncated_mac` the Gateway rejects a missing MAC as `Rp`.

The Gateway treats the pair `(node_id, mac)` as an idempotency key for the order TTL window. A second copy of the same frame produces the same flag and does not debit, match, or cancel again.

## Status flags

Gateway to trader, on channel 1.

With an order id: `<flag><oid>` and, only for `R`, a one-character reason after the id.

| Flag | Meaning | Example |
|---|---|---|
| `A` | Accepted | `Ak7f2` |
| `M` | Matched | |
| `X` | Cancelled or aborted | |
| `E` | Expired (60-minute TTL) | |
| `K` | Key-exchange step is due, details on a signed DM | |
| `L` | Funds locked | |
| `C` | Confirmed on-chain | |
| `D` | Swap done | |
| `S` | Counterparty slashed for abandonment | |
| `R` | Rejected | `Rk7f2r` |

Reason characters: `r` rate, `f` fee or credit, `b` bond, `p` parse, `l` limit.

A rejection that happens before an id exists is `R` plus the reason and nothing else: `Rr`, `Rl`, `Rf`, `Rb`, `Rp`. Section 4 of the plan names `Rr` and `Rl` for the rate and active-order limits. Those short forms are the ones without an id.

Flags are unsigned. Anyone who knows the channel key can inject them. Traders treat them as hints and take fund-moving steps only from signed DM frames.

## Channel 0 ticker

One packet, at most 100 bytes, default period 60 seconds.

```
T|XMR/LTC|<last>|<bid>|<ask>|<24h vol>|<seq>
```

Golden vector, 49 bytes:

```
T|XMR/LTC|0.004200|0.004100|0.004300|12.5000|0001
```

`last`, `bid`, and `ask` are LTC per XMR with exactly 6 fractional digits and at most 4 integer digits. Volume is XMR with exactly 4 fractional digits and at most 7 integer digits. `seq` is 4 decimal digits and wraps at 9999. A ticker that would exceed 100 bytes is not sent.

## DM frames

```
<type 1><seq 2><total 2><base64 payload>
```

`seq` and `total` are lowercase base36, zero-padded to 2 characters. `seq` is the zero-based chunk index. `total` is the chunk count and is never `00`. The largest count that fits is `zz` (1295). A 48,765-byte proof at 99 raw bytes per chunk is 493 chunks, which is base36 `dp`. The last index of that transfer is 492, base36 `do`.

| Type | Payload |
|---|---|
| `G` | Registration |
| `H` | Bond-funding proof |
| `Q` | Swap public keys, encrypted to the counterparty |
| `Z` | Adaptor-signature message, encrypted to the counterparty |
| `P` | Proof chunk, or a one-chunk commitment when the proof itself is on the side channel |
| `N` | NACK bitmap |
| `Y` | ACK |

The header is counted inside the 140-byte budget. Payload base64 is standard base64 with padding.

Registration payload, version 0x01: `0x01 || x25519_pubkey (32) || ltc_address (utf-8)`. The golden pubkey is the byte pattern `0x00..0x1f`. It is a test pattern, not a key. The address `tltc1qexampleaddr` is a shape example, not a checksummed address.

```
G0001AQABAgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4fdGx0YzFxZXhhbXBsZWFkZHI=
```

That frame is 73 bytes. One reassembly context is open per peer per type.

Proof chunk of the two raw bytes `hi`, chunk 0 of 5:

```
P0005aGk=
```

NACK bitmap, one chunk. Bit `i` in the decoded payload is set when chunk `i` is missing. The low bit of the first byte is chunk 0. `0x05` means chunks 0 and 2 are missing:

```
N0001BQ==
```

ACK payload is a 2-byte big-endian count of the contiguous prefix received. A prefix of 5:

```
Y0001AAU=
```

Side-channel commitment. The radio carries SHA-256 of the proof bytes, and the proof bytes travel off-radio. The vector hashes the label `loradex-proof-vector`:

```
P0001utO/wHvkNF57LGzR34jtObSQTsa5srMN9BAMnc+/iBg=
```

The receiver accepts a side-channel proof only when its SHA-256 matches this commitment. The commitment is covered by the same application MAC as other signed DM frames once identity is bound.

## Gateway transmit queue

Priority, highest first: swap DM frames, match and status flags, order acknowledgements, ticker.

A queued packet older than 30 seconds is dropped and logged. Swap-critical DM frames (`Q`, `Z`, `P`, `N`, `Y`, `H`) are the exception: they are re-queued with backoff until the swap's own timeout. Pacing comes from `loradex.sim.airtime` so the Gateway stays inside its configured duty cycle.

## Limits

Per node id: 2 messages per minute on a sliding window, 2 active orders, 60-minute order TTL. A rate violation returns `Rr`. An active-order violation returns `Rl`. The third strike inside the configurable window sets `muted_until`.

The $0.05 fee and the bond check are specified in `docs/SWAP_DESIGN.md` and are not implemented until D1 and D2 are confirmed.
