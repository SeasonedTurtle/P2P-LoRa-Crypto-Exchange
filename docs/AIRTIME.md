# Airtime and capacity

`loradex.sim.airtime` implements the Semtech SX127x time-on-air formula. Times below are microseconds from that function. They are PHY estimates. They are not a field measurement. `docs/HARDWARE_TODO.md` is where a radio check gets recorded, and Phase 2 compares these numbers with logs.

Symbol duration is `2^SF / BW`. The preamble on air is `N_preamble + 4.25` symbols. Payload symbols use the datasheet ceiling formula with an explicit header and a CRC. Low-data-rate optimization turns on when a symbol is longer than 16 ms. That is why SF11 at 125 kHz is more than twice SF11 at 250 kHz in the table: the slower setting crosses the 16 ms line.

A known datasheet point is locked in tests: SF7, 125 kHz, coding rate 4/5, 8-symbol preamble, 8-byte payload, CRC on, explicit header. Time on air is **36,096 µs**.

## Meshtastic LongFast

Sub-GHz LongFast, from the Meshtastic preset table and firmware: SF11, 250 kHz, coding rate 4/5, **16-symbol** preamble. The firmware's 16 symbols alone are **131,072 µs**. Semtech adds 4.25 symbols on top of that, and the calculator includes them.

`MESHTASTIC_FRAMING_OVERHEAD_BYTES` is **16**. That is a planning estimate for the encrypted frame around an application payload, to be replaced by a field measurement. It is not a packet capture.

| LoRa payload | Time on air | Packets per hour, continuous | Packets per hour at 10% |
|---:|---:|---:|---:|
| 49 B | 600,064 µs | 5,999 | 599 |
| 100 B | 1,009,664 µs | 3,565 | 356 |
| 140 B | 1,296,384 µs | 2,776 | 277 |
| 156 B (140 + 16) | 1,419,264 µs | 2,536 | 253 |
| 233 B | 1,992,704 µs | 1,806 | 180 |

A full application frame of 140 bytes plus the 16-byte estimate occupies the channel for about **1.42 seconds** on LongFast.

## Spreading factor and bandwidth

140-byte payload, 8-symbol preamble, coding rate 4/5, CRC, explicit header. Preamble 8 is the comparison grid from the plan (SF7–SF12, 125 and 250 kHz). LongFast itself uses preamble 16, so it is not a cell in this grid.

| SF | 125 kHz | 250 kHz |
|---:|---:|---:|
| 7 | 230,656 µs | 115,328 µs |
| 8 | 410,112 µs | 205,056 µs |
| 9 | 738,304 µs | 369,152 µs |
| 10 | 1,353,728 µs | 676,864 µs |
| 11 | 2,953,216 µs | 1,230,848 µs |
| 12 | 5,251,072 µs | 2,625,536 µs |

## What this means for the exchange

The per-node cap is 2 messages per minute. Fifty nodes at that cap offer 6,000 messages an hour. One LongFast transmitter at a 10% duty cycle carries about **253** full-size frames an hour. The airtime cap binds before the per-node cap once the mesh is busy. The 2-per-minute rule is a spam limit, not a capacity claim.

A cross-group proof of 48,765 bytes is **493** text chunks (see `docs/SWAP_DESIGN.md`). At 1,419,264 µs for a 156-byte frame:

- One proof, continuous transmit: 493 × 1,419,264 µs = **699.7 s**
- Both parties' proofs, continuous transmit: **1,399.4 s** (about 23.3 minutes)
- Both proofs at a 10% duty cycle: about **3.9 hours** of gateway airtime, with no retries and no other traffic

That is the number behind the Phase 0 transport choice.

## Regulatory warning

This is not legal advice. A deployment has to follow the rules of its band.

US 902–928 MHz digital-modulation and frequency-hopping rules include a per-channel dwell limit on the order of 0.4 seconds when a device is operating as a hopper with enough channels. A single LongFast frame of 156 bytes is already about 1.42 seconds, so a hopper interpretation and a long frame do not fit in that dwell. EU 868 MHz duty cycles are commonly 1% or 10% depending on the sub-band. The Gateway's duty-cycle setting exists so an operator can cap airtime. The operator confirms which cap applies.
