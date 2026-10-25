# Hardware checklist

Phase 0 does not use a radio. Nothing in `docs/AIRTIME.md` is a field measurement. The mock radio is what CI will run, once it exists (Phase 1, P1-7).

Do not check these boxes from a simulator.

## Phase 2, when a human has the radios (P2-7)

- [ ] Two trader radios and one Gateway radio, with firmware versions written down here.
- [ ] Channel 0 with no key. Channel 1 with an AES-256 PSK set on the devices, not committed to the repo.
- [ ] Region, frequency slot, modem preset (LongFast unless the operator chooses otherwise), and antenna noted.
- [ ] Register → credit (chain still mocked) → order → match → status flags, across the three radios.
- [ ] A chunked transfer of at least 4 KB through the mock radio at 30% loss, then the same blob on the real radios.
- [ ] Field logs of RTT, loss, and airtime per packet under `field_logs/`. Actual time on air within 25% of `docs/AIRTIME.md` for the same payload length.
- [ ] Confirm the on-air preamble (expected 16 symbols below 1 GHz) and the real Meshtastic framing overhead. Replace the 16-byte planning estimate if the capture disagrees.

US 915 MHz dwell and EU duty-cycle limits are the operator's to confirm. The warning in `docs/AIRTIME.md` is not legal advice.
