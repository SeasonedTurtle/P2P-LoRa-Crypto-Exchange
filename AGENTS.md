# Agent rules

These rules are the working copy of Section 0 of `LORA_DEX_PLAN.md`. The plan is the source of truth. Read it before writing code.

1. **Testnet only.** LTC `testnet4` or regtest, XMR `stagenet` or regtest. Mainnet code paths stay unreachable unless `NETWORK=mainnet` and `--i-understand-this-is-real-money` are both set. Defaults are test networks.
2. **No secrets in the repo.** No keys, seeds, PSKs, or RPC passwords. Use `.env` (gitignored) and `.env.example`. Never log private keys, adaptor secrets, or channel PSKs.
3. **Hardware is a human step.** When a task needs a physical radio, stop and write a checklist in `docs/HARDWARE_TODO.md`. Do not fake hardware results. CI uses the mock radio.
4. **Tests before a task is done.** Each module ships with unit tests. `pytest -q` and `ruff check` pass before a task is marked done. `mypy` is part of the same bar.
5. **Small commits.** One task per commit: `phase<N>/<task-id>: <summary>`.
6. **Spec first.** Wire formats live in `docs/PROTOCOL.md`. Code follows the spec. Spec changes land in the same commit as the code they describe.
7. **Ask on custody and cryptography.** Record the question in `docs/OPEN_QUESTIONS.md` and continue with other work. Do not invent elliptic-curve or DLEQ primitives. Wrap audited libraries.

Phase gates from the plan:

- Do not start a phase until the previous phase's exit criteria all pass.
- Implement decision defaults behind config flags.
- Pause before Phase 1 tasks P1-5 (prepaid credits) and P1-6 (fidelity bonds) until a human settles D1–D3.
- Phase 0 exit still requires a human review of D1–D5. That review is open. See `docs/OPEN_QUESTIONS.md`.
