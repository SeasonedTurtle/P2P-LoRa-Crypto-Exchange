# P2P-LoRa-Crypto-Exchange

An off-grid exchange of XMR against LTC. Traders talk to a Python Gateway over LoRa. Settlement is an atomic swap. The implementation plan, including the agent rules and the phase gates, is [LORA_DEX_PLAN.md](LORA_DEX_PLAN.md).

Networks default to Litecoin testnet4 and Monero stagenet. Mainnet stays off unless the process is started with `NETWORK=mainnet` and `--i-understand-this-is-real-money`.

The cross-group proof that an XMR↔LTC swap needs is about 49 KB. That is hundreds of LoRa packets, so the default is to move the proof on a side channel and keep a hash on the radio. Channel 1's shared key is a spam gate, not confidentiality. The fee balance and the bond slash are trust assumptions with a small cap. Details are in `docs/SWAP_DESIGN.md` and `docs/THREAT_MODEL.md`.

Decisions D1–D7 are open in `docs/OPEN_QUESTIONS.md`. Fee and bond code waits on D1–D3.

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
mypy
```
