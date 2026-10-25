"""Typed settings. Test networks are the default. Mainnet is a double opt-in.

An environment file cannot turn mainnet on by itself. ``NETWORK=mainnet`` (or a
per-chain mainnet value) does nothing unless the process argv also contains
``--i-understand-this-is-real-money``.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

MAINNET_ACK_FLAG = "--i-understand-this-is-real-money"


class MainnetDisabled(RuntimeError):
    """Raised when a mainnet network is selected without the explicit ack flag."""


class LtcNetwork(StrEnum):
    TESTNET4 = "testnet4"
    REGTEST = "regtest"
    MAINNET = "mainnet"


class XmrNetwork(StrEnum):
    STAGENET = "stagenet"
    REGTEST = "regtest"
    MAINNET = "mainnet"


class FeeMode(StrEnum):
    """D1 default: prepaid credits. Dust-level custody, documented as such."""

    PREPAID_CREDITS = "prepaid_credits"


class BondMode(StrEnum):
    """D2 default: CLTV-refundable bond, gateway-arbitrated slash, $10 cap."""

    GATEWAY_ARBITRATED_CLTV = "gateway_arbitrated_cltv"


class CommandAuth(StrEnum):
    """D3 default: truncated per-command MAC bound to the registered pubkey."""

    TRUNCATED_MAC = "truncated_mac"
    FIRMWARE_PKC = "firmware_pkc"


class PriceMode(StrEnum):
    """D4 default: static configured rate, optional feed added later."""

    STATIC_PLUS_OPTIONAL_FEED = "static_plus_optional_feed"


class SecretStorage(StrEnum):
    """D5 default: memory for the swap lifetime, plus an encrypted journal."""

    MEMORY_AND_ENCRYPTED_JOURNAL = "memory_and_encrypted_journal"


class ProofTransport(StrEnum):
    """P0-4 choice. Default is the side channel (plan option B)."""

    SIDE_CHANNEL = "side_channel"
    RADIO_CHUNKED = "radio_chunked"


@dataclass(frozen=True, slots=True)
class Settings:
    ltc_network: LtcNetwork = LtcNetwork.TESTNET4
    xmr_network: XmrNetwork = XmrNetwork.STAGENET
    mainnet_ack: bool = False
    max_payload_bytes: int = 140
    fee_mode: FeeMode = FeeMode.PREPAID_CREDITS
    bond_mode: BondMode = BondMode.GATEWAY_ARBITRATED_CLTV
    command_auth: CommandAuth = CommandAuth.TRUNCATED_MAC
    price_mode: PriceMode = PriceMode.STATIC_PLUS_OPTIONAL_FEED
    secret_storage: SecretStorage = SecretStorage.MEMORY_AND_ENCRYPTED_JOURNAL
    proof_transport: ProofTransport = ProofTransport.SIDE_CHANNEL
    partial_fills: bool = False
    order_ttl_s: int = 60 * 60
    msgs_per_minute: int = 2
    max_active_orders: int = 2
    tx_queue_ttl_s: int = 30
    # R6. Conservative until the refund path is tested. See docs/SWAP_DESIGN.md.
    ltc_confirmations: int = 6
    xmr_confirmations: int = 10
    ltc_refund_delay_s: int = 6 * 60 * 60
    # Policy amounts in integer US cents. Conversion to litoshis is a later task.
    order_fee_usd_cents: int = 5
    bond_cap_usd_cents: int = 1000
    slash_usd_cents: int = 100
    # Placeholder static rate for D4. This is not a market price.
    static_ltc_usd_cents: int = 10_000

    @property
    def uses_mainnet(self) -> bool:
        return (
            self.ltc_network is LtcNetwork.MAINNET or self.xmr_network is XmrNetwork.MAINNET
        )

    def assert_safe(self) -> None:
        if self.uses_mainnet and not self.mainnet_ack:
            raise MainnetDisabled(
                "mainnet requires NETWORK=mainnet and --i-understand-this-is-real-money"
            )


_E = TypeVar("_E", bound=StrEnum)


def _enum_value(enum_cls: type[_E], raw: str, name: str) -> _E:
    try:
        return enum_cls(raw)
    except ValueError as exc:
        allowed = ", ".join(member.value for member in enum_cls)
        raise ValueError(f"{name} must be one of: {allowed}") from exc


def load_settings(
    environ: Mapping[str, str] | None = None,
    argv: Sequence[str] | None = None,
) -> Settings:
    """Load settings and refuse mainnet unless the ack flag is present."""

    env = os.environ if environ is None else environ
    args = tuple(sys.argv if argv is None else argv)
    ltc_raw = env.get("LORADDEX_LTC_NETWORK", LtcNetwork.TESTNET4.value)
    xmr_raw = env.get("LORADDEX_XMR_NETWORK", XmrNetwork.STAGENET.value)
    if env.get("NETWORK") == "mainnet":
        ltc_raw = LtcNetwork.MAINNET.value
        xmr_raw = XmrNetwork.MAINNET.value
    settings = Settings(
        ltc_network=_enum_value(LtcNetwork, ltc_raw, "LORADDEX_LTC_NETWORK"),
        xmr_network=_enum_value(XmrNetwork, xmr_raw, "LORADDEX_XMR_NETWORK"),
        mainnet_ack=MAINNET_ACK_FLAG in args,
    )
    settings.assert_safe()
    return settings
