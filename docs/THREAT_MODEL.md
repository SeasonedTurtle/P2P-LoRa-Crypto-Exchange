# Threat model

Phase 0. This is the model the later phases implement against. It names what the Gateway operator can do, because some of that power is a chosen default rather than a bug.

## Assets

- Traders' XMR and LTC locked in a swap.
- Prepaid order credits and fidelity bonds.
- Identity binding: node id, X25519 public key, LTC address.
- Adaptor scalars and spend keys. These are the assets that must not appear in logs, SQLite, or channel 1 plaintext.
- Availability of the trading channel. Airtime is the scarce resource.

## Actors

- **Trader.** Holds their own keys. May misbehave, disconnect, or race a timeout.
- **Casual listener.** Hears the mesh, does not have the channel 1 key.
- **Channel-1 holder.** Has the shared PSK. Can read and inject channel 1 frames. This includes every registered trader, and anyone they share the key with.
- **Gateway operator.** Runs listener, observer, and the SQLite file. Sees order flow. Holds the bond co-sign key and the prepaid-credit book.
- **Radio jammer.** Fills the channel. Cannot be told apart from a crowded mesh by the software alone.

## Trust assumptions that are part of the design

These are defaults D1, D2, and D7. They stay labeled as trust. The UI and docs describe them this way.

| Assumption | Cap | What the operator can do |
|---|---|---|
| Prepaid credits (D1) | Dust, one deposit at a time, debited at $0.05 per accepted order | Freeze or mis-account the credit balance. Cannot, by this mechanism, take the coins locked in a swap |
| Gateway-arbitrated slash (D2) | $10 bond, $1 slash | Refuse an early bond release, or pay the slash to the path the script allows. After the CLTV timeout the trader reclaims the bond alone |
| Single operator (D7) | The Gateway is a matching and availability point | Stop matching, censor a node, or go offline. In-flight swap refunds still have to complete from the chain rules and the traders' keys |

The traded coins follow the atomic swap in `docs/SWAP_DESIGN.md`. The fee balance and the slash do not.

## Channel 1 is not a private channel

The PSK stops a casual listener from reading orders and cuts down unauthenticated spam. Every holder of the key can read orders and inject commands and flags.

Controls:

- Swap keys, adaptor signatures, and the view key a counterparty must see are encrypted to that counterparty's registered X25519 key (DM types `Q` and `Z`).
- Commands under the D3 default carry an 11-character truncated MAC bound to the registered key. A forged node id fails the MAC.
- Flags stay short and unsigned. A matching or "funds locked" flag is a hint. The fund-moving message is the signed DM.
- Registration binds the observed node id to the public key and the LTC address. Later privileged commands use that binding. Raw node ids are spoofable on older Meshtastic firmware, so the node id alone is never the credential.

## Threats

**Spam and order flooding.** Two messages per minute, two active orders, a 60-minute TTL, and a strike counter that mutes the node. The $0.05 debit, once D1 is confirmed, is the economic half of the same control. Airtime pacing drops a non-critical packet after 30 seconds so a flood cannot pin the queue.

**Jamming and mesh collapse.** A jammer who occupies LongFast denies the market. The software cannot fix physics. The response is detection and a halt: the Gateway stops accepting new orders while in-flight swaps keep their refund timers. Flood routing makes this worse, which is why the radio sits behind `RadioAdapter` and the production path is directed MeshCore routing. Capacity numbers are in `docs/AIRTIME.md`. A full proof on the radio is itself a denial-of-service against the channel, which is why the default transport is the side channel.

**Sybil.** New node ids are cheap. The bond and the credit deposit are the costs that are not cheap. Until those tasks are built, a Sybil is limited only by the per-node message cap, and an attacker with many radios can still spend airtime. That gap is explicit while P1-5 and P1-6 are paused.

**Replay.** The Gateway stores `(node_id, mac)` for the order TTL and returns the original result on a repeat. Swap DM frames are accepted once per `(swap, step, seq)`. A replayed adaptor message or proof chunk must not advance state twice.

**Node-id spoofing.** Covered by the registration binding and the command MAC. Firmware PKC on DMs, if D3 is later switched to `firmware_pkc`, is an alternative control, not an additional one the MVP depends on.

**Malicious or crashed Gateway.** The operator can censor and can mishandle credits and slashes inside the caps above. They must not be able to spend both sides of a swap: the swap keys stay with the traders, and a crash mid-swap resumes from SQLite. Phase 1's recovery test and Phase 3's chaos tests are the checks. Secrets for that resume follow D5 (memory, plus an encrypted journal), and the journal key lives in the environment, not the database.

**Griefing and abandonment.** A matched trader who walks away triggers the refund path and, under D2, a slash inside the $10 cap. Timeouts include radio delay and Gateway downtime (`ltc_refund_delay_s`, default 6 hours). The refund path is tested as thoroughly as the happy path. A swap must not reach a state where both sides' locked coins are unrecoverable.

**Key leakage through the shared PSK.** Channel 1 plaintext is orders, flags, and the ticker. Proof blobs on the side channel are zero-knowledge statements bound by a radio hash; they are not scalars. Logs store payload hashes in `swap_steps`, never the payload, when that table is in use. Private keys, adaptor secrets, the channel PSK, and RPC passwords are not logged and not committed.

**Side-channel substitution.** The proof's SHA-256 is what the radio commits to. A different blob on the LAN fails the check. The commitment frame is authenticated the same way as the other signed DMs.

**Mainnet foot-gun.** Defaults are LTC testnet4 and XMR stagenet. Selecting mainnet without `--i-understand-this-is-real-money` raises `MainnetDisabled`. An environment variable by itself cannot satisfy the ack.
