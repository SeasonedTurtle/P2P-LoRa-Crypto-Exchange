import pytest

from loradex.config import (
    MAINNET_ACK_FLAG,
    LtcNetwork,
    MainnetDisabled,
    ProofTransport,
    XmrNetwork,
    load_settings,
)


def test_defaults_are_test_networks() -> None:
    settings = load_settings(environ={}, argv=[])
    assert settings.ltc_network is LtcNetwork.TESTNET4
    assert settings.xmr_network is XmrNetwork.STAGENET
    assert settings.uses_mainnet is False
    assert settings.proof_transport is ProofTransport.SIDE_CHANNEL
    assert settings.partial_fills is False
    assert settings.order_fee_usd_cents == 5
    assert settings.bond_cap_usd_cents == 1000
    assert settings.slash_usd_cents == 100


def test_mainnet_without_ack_is_rejected() -> None:
    with pytest.raises(MainnetDisabled):
        load_settings(environ={"NETWORK": "mainnet"}, argv=["gateway"])


def test_per_chain_mainnet_without_ack_is_rejected() -> None:
    with pytest.raises(MainnetDisabled):
        load_settings(environ={"LORADDEX_LTC_NETWORK": "mainnet"}, argv=[])


def test_mainnet_with_ack_flag_loads() -> None:
    settings = load_settings(
        environ={"NETWORK": "mainnet"},
        argv=["gateway", MAINNET_ACK_FLAG],
    )
    assert settings.ltc_network is LtcNetwork.MAINNET
    assert settings.xmr_network is XmrNetwork.MAINNET
    assert settings.mainnet_ack is True


def test_ack_flag_does_not_select_mainnet_by_itself() -> None:
    settings = load_settings(environ={}, argv=[MAINNET_ACK_FLAG])
    assert settings.uses_mainnet is False


def test_ack_environment_variable_is_not_enough() -> None:
    with pytest.raises(MainnetDisabled):
        load_settings(
            environ={
                "NETWORK": "mainnet",
                "I_UNDERSTAND_THIS_IS_REAL_MONEY": "1",
            },
            argv=["gateway"],
        )


def test_unknown_network_is_rejected() -> None:
    with pytest.raises(ValueError, match="LORADDEX_LTC_NETWORK"):
        load_settings(environ={"LORADDEX_LTC_NETWORK": "signet"}, argv=[])
