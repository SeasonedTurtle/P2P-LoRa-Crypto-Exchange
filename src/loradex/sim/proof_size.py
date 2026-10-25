"""Sizes of the cross-group DLEQ proofs an XMR↔LTC swap has to move.

The byte count ``129 + 193 * n`` is the borromean encoding written down in
tecnovert's Bitcoin–Monero swap implementation notes (2020-09-10), for ``n``
proved bits. For the ed25519 order that ``n`` is 252, which evaluates to
48,765 bytes. Serai's published ``CompromiseLinear`` benchmark is the same
48,765 bytes. This module evaluates that formula. It does not generate a proof.
"""

from __future__ import annotations

from dataclasses import dataclass

# Bits required to represent a scalar strictly below the ed25519 group order.
ED25519_PROOF_BITS = 252

# tecnovert, "Bitcoin–Monero Cross-chain Atomic Swap Implementation notes", v0.2 draft.
BORROMEAN_FIXED_BYTES = 129
BORROMEAN_BYTES_PER_BIT = 193

# Serai cross-group DLEq README, k256 / curve25519-dalek benchmarks.
# These constructions are unaudited upstream. The sizes are planning inputs.
SERAI_PUBLISHED_BYTES: dict[str, int] = {
    "ClassicLinear": 56_829,
    "ConciseLinear": 44_607,
    "EfficientLinear": 65_145,
    "CompromiseLinear": 48_765,
}

# Same-curve ECDSA verifiably-encrypted signature from those same notes:
# R1 (33) + R2 (33) + s (32) + DLEQ(K1 33, K2 33, r 32) = 196.
ECDSA_VES_BYTES = 33 + 33 + 32 + 33 + 33 + 32

# BIP340 Schnorr signature size. A Taproot adaptor signature is this class of
# object; the cross-group proof is separate and dominates.
SCHNORR_SIGNATURE_BYTES = 64


def borromean_dleq_bytes(n_bits: int = ED25519_PROOF_BITS) -> int:
    if n_bits < 1:
        raise ValueError("bit count must be positive")
    return BORROMEAN_FIXED_BYTES + BORROMEAN_BYTES_PER_BIT * n_bits


def raw_bytes_per_text_chunk(max_payload_bytes: int = 140, header_chars: int = 5) -> int:
    """Raw bytes carried by one DM text frame.

    The frame is ``type`` (1) + base36 ``seq`` (2) + base36 ``total`` (2) +
    base64 payload. Each chunk's base64 is padded independently, so its length
    is a multiple of 4.
    """

    room = max_payload_bytes - header_chars
    if room < 4:
        raise ValueError("payload budget cannot hold a base64 chunk")
    b64_chars = room - (room % 4)
    return (b64_chars // 4) * 3


def chunks_for(total_bytes: int, raw_per_chunk: int) -> int:
    if total_bytes < 0:
        raise ValueError("byte count must be >= 0")
    if raw_per_chunk <= 0:
        raise ValueError("chunk size must be positive")
    if total_bytes == 0:
        return 0
    return (total_bytes + raw_per_chunk - 1) // raw_per_chunk


@dataclass(frozen=True, slots=True)
class ProofTransfer:
    proof_bytes: int
    proofs_per_swap: int
    raw_per_chunk: int

    @property
    def chunks_per_proof(self) -> int:
        return chunks_for(self.proof_bytes, self.raw_per_chunk)

    @property
    def chunks_per_swap(self) -> int:
        return self.chunks_per_proof * self.proofs_per_swap


def planning_transfer(max_payload_bytes: int = 140) -> ProofTransfer:
    """One borromean proof from each party, packed into the text-frame budget."""

    return ProofTransfer(
        proof_bytes=borromean_dleq_bytes(),
        proofs_per_swap=2,
        raw_per_chunk=raw_bytes_per_text_chunk(max_payload_bytes),
    )
