from loradex.sim.proof_size import (
    BORROMEAN_BYTES_PER_BIT,
    BORROMEAN_FIXED_BYTES,
    ED25519_PROOF_BITS,
    SERAI_PUBLISHED_BYTES,
    borromean_dleq_bytes,
    chunks_for,
    planning_transfer,
    raw_bytes_per_text_chunk,
)


def test_borromean_formula_matches_serai_compromise_linear() -> None:
    size = borromean_dleq_bytes(ED25519_PROOF_BITS)
    assert size == BORROMEAN_FIXED_BYTES + BORROMEAN_BYTES_PER_BIT * 252
    assert size == 48_765
    assert size == SERAI_PUBLISHED_BYTES["CompromiseLinear"]


def test_text_chunk_carries_99_raw_bytes() -> None:
    assert raw_bytes_per_text_chunk(140, header_chars=5) == 99


def test_swap_design_quotes_the_same_size() -> None:
    from pathlib import Path

    doc = Path(__file__).resolve().parents[2].joinpath("docs", "SWAP_DESIGN.md").read_text()
    assert "48,765" in doc
    assert "493" in doc


def test_one_proof_needs_hundreds_of_chunks() -> None:
    transfer = planning_transfer()
    assert transfer.chunks_per_proof == chunks_for(48_765, 99)
    assert transfer.chunks_per_proof == 493
    assert transfer.chunks_per_swap == 986


def test_smallest_published_linear_proof_is_still_hundreds_of_chunks() -> None:
    raw = raw_bytes_per_text_chunk()
    assert chunks_for(SERAI_PUBLISHED_BYTES["ConciseLinear"], raw) == 451
