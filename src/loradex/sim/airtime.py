"""LoRa time-on-air, using the Semtech SX127x symbol formula.

The formula matches the SX1272/76 datasheet:

    T_sym = 2^SF / BW
    T_preamble = (N_preamble + 4.25) * T_sym
    N_payload = 8 + max(ceil((8*PL - 4*SF + 28 + 16*CRC - 20*IH) / (4*(SF - 2*DE))) * (CR + 4), 0)
    T_packet = T_preamble + N_payload * T_sym

``CR`` here is the Semtech integer 1..4 for coding rates 4/5..4/8. Callers pass
the coding-rate denominator (5..8), which is how Meshtastic stores it.

Low-data-rate optimization (``DE``) turns on when a symbol is longer than 16 ms,
unless the caller sets it explicitly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

# Meshtastic LongFast on sub-GHz radios: SF11, BW 250 kHz, CR 4/5, 16-symbol preamble.
# The 16-symbol figure is the firmware preamble. Semtech also adds 4.25 symbols.
LONG_FAST = "long_fast"


@dataclass(frozen=True, slots=True)
class LoRaParams:
    spreading_factor: int
    bandwidth_hz: int
    coding_rate_denominator: int = 5
    preamble_symbols: int = 8
    explicit_header: bool = True
    crc: bool = True
    low_data_rate_optimization: bool | None = None

    def __post_init__(self) -> None:
        if self.spreading_factor < 7 or self.spreading_factor > 12:
            raise ValueError("spreading factor must be 7..12")
        if self.bandwidth_hz <= 0:
            raise ValueError("bandwidth must be positive")
        if self.coding_rate_denominator < 5 or self.coding_rate_denominator > 8:
            raise ValueError("coding rate denominator must be 5..8")
        if self.preamble_symbols < 6:
            raise ValueError("preamble must be at least 6 symbols")


def long_fast() -> LoRaParams:
    """Meshtastic LongFast preset for sub-GHz hardware (US 915 MHz class)."""

    return LoRaParams(
        spreading_factor=11,
        bandwidth_hz=250_000,
        coding_rate_denominator=5,
        preamble_symbols=16,
    )


def symbol_duration(params: LoRaParams) -> Fraction:
    """Symbol duration in seconds."""

    return Fraction(1 << params.spreading_factor, params.bandwidth_hz)


def _de_flag(params: LoRaParams) -> int:
    if params.low_data_rate_optimization is None:
        return 1 if symbol_duration(params) > Fraction(16, 1000) else 0
    return 1 if params.low_data_rate_optimization else 0


def payload_symbols(params: LoRaParams, payload_bytes: int) -> int:
    if payload_bytes < 0:
        raise ValueError("payload length must be >= 0")
    sf = params.spreading_factor
    de = _de_flag(params)
    denom = 4 * (sf - 2 * de)
    if denom <= 0:
        raise ValueError("low-data-rate optimization leaves no payload bits")
    ih = 0 if params.explicit_header else 1
    crc = 1 if params.crc else 0
    numer = 8 * payload_bytes - 4 * sf + 28 + 16 * crc - 20 * ih
    cr = params.coding_rate_denominator - 4
    rounded = math.ceil(Fraction(numer, denom))
    return 8 + max(rounded * (cr + 4), 0)


def airtime(params: LoRaParams, payload_bytes: int) -> Fraction:
    """Packet time-on-air in seconds, as an exact fraction."""

    t_sym = symbol_duration(params)
    t_preamble = (params.preamble_symbols + Fraction(17, 4)) * t_sym
    return t_preamble + payload_symbols(params, payload_bytes) * t_sym


def airtime_us(params: LoRaParams, payload_bytes: int) -> int:
    """Packet time-on-air in microseconds, rounded half up."""

    micros = airtime(params, payload_bytes) * 1_000_000
    return int(micros + Fraction(1, 2))


def packets_per_hour(airtime_seconds: Fraction, duty_cycle: Fraction) -> int:
    """How many such packets fit in one hour at a duty-cycle cap.

    ``duty_cycle`` is a fraction of the hour the transmitter may be on
    (``1`` is continuous transmit, ``Fraction(1, 10)`` is ten percent).
    """

    if airtime_seconds <= 0:
        raise ValueError("airtime must be positive")
    if duty_cycle <= 0 or duty_cycle > 1:
        raise ValueError("duty cycle must be in (0, 1]")
    budget = duty_cycle * 3600
    return int(budget // airtime_seconds)


# Planning overhead for a Meshtastic encrypted frame around an app payload.
# This is an estimate for capacity math, not a field measurement.
MESHTASTIC_FRAMING_OVERHEAD_BYTES = 16
