from fractions import Fraction

from hypothesis import given
from hypothesis import strategies as st

from loradex.sim.airtime import (
    LoRaParams,
    airtime,
    airtime_us,
    long_fast,
    packets_per_hour,
    payload_symbols,
    symbol_duration,
)


def test_semtech_worked_example_36ms() -> None:
    """SF7, BW125, CR 4/5, preamble 8, 8-byte payload, CRC, explicit header.

    This is the widely reproduced Semtech result of 36.096 ms.
    """

    params = LoRaParams(
        spreading_factor=7,
        bandwidth_hz=125_000,
        coding_rate_denominator=5,
        preamble_symbols=8,
    )
    assert airtime_us(params, 8) == 36_096
    assert payload_symbols(params, 8) == 23


def test_long_fast_full_frame_matches_the_capacity_doc() -> None:
    from pathlib import Path

    us = airtime_us(long_fast(), 156)
    assert us == 1_419_264
    doc = Path(__file__).resolve().parents[2].joinpath("docs", "AIRTIME.md").read_text()
    assert "1,419,264" in doc
    assert "36,096" in doc


def test_long_fast_symbol_is_8_192_us() -> None:
    params = long_fast()
    assert symbol_duration(params) == Fraction(8192, 1_000_000)
    # Firmware quotes the 16-symbol preamble alone (~131 ms). Semtech adds 4.25.
    preamble_only_us = int(16 * symbol_duration(params) * 1_000_000)
    assert preamble_only_us == 131_072


def test_low_data_rate_turns_on_for_slow_symbols() -> None:
    slow = LoRaParams(spreading_factor=12, bandwidth_hz=125_000, preamble_symbols=8)
    fast = LoRaParams(spreading_factor=7, bandwidth_hz=125_000, preamble_symbols=8)
    # Same short payload: SF12/BW125 must take longer, and DE must be active
    # or the symbol count would be computed with a wider denominator.
    assert symbol_duration(slow) > Fraction(16, 1000)
    assert symbol_duration(fast) < Fraction(16, 1000)
    assert airtime(slow, 20) > airtime(fast, 20)


def test_airtime_grows_with_payload() -> None:
    params = long_fast()
    assert airtime(params, 10) < airtime(params, 140)


def test_duty_cycle_caps_packets() -> None:
    params = long_fast()
    one = airtime(params, 140)
    assert packets_per_hour(one, Fraction(1, 1)) > packets_per_hour(one, Fraction(1, 10))


def test_rejects_bad_params() -> None:
    try:
        LoRaParams(spreading_factor=6, bandwidth_hz=125_000)
    except ValueError:
        return
    raise AssertionError("SF6 must be rejected")


@given(
    payload=st.integers(min_value=0, max_value=255),
    sf=st.integers(min_value=7, max_value=12),
)
def test_airtime_is_positive_and_monotonic(payload: int, sf: int) -> None:
    params = LoRaParams(spreading_factor=sf, bandwidth_hz=125_000, preamble_symbols=8)
    assert airtime(params, payload) > 0
    if payload < 255:
        assert airtime(params, payload) <= airtime(params, payload + 1)
