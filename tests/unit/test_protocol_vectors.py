"""Golden vectors for docs/PROTOCOL.md. The JSON file is normative."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VECTORS = json.loads((ROOT / "docs" / "vectors" / "protocol_v0.json").read_text())
SPEC = (ROOT / "docs" / "PROTOCOL.md").read_text()


def _by_id(vector_id: str) -> dict[str, object]:
    for vector in VECTORS["vectors"]:
        if vector["id"] == vector_id:
            return vector
    raise AssertionError(vector_id)


def test_every_vector_matches_its_declared_length_and_the_spec() -> None:
    assert VECTORS["version"] == 0
    for vector in VECTORS["vectors"]:
        text = vector["text"]
        assert isinstance(text, str)
        assert len(text.encode()) == vector["byte_len"]
        assert text in SPEC
        if vector["kind"] == "command":
            assert vector["byte_len"] <= VECTORS["command_max_bytes"]
        elif vector["kind"] == "ticker":
            assert vector["byte_len"] <= VECTORS["ticker_max_bytes"]
        elif vector["kind"] == "dm":
            assert vector["byte_len"] <= VECTORS["payload_max_bytes"]
            assert text[0] in "GHQZPNY"


def test_registration_frame_is_the_documented_layout() -> None:
    raw = bytes([0x01]) + bytes(range(32)) + b"tltc1qexampleaddr"
    frame = "G0001" + base64.b64encode(raw).decode()
    vector = _by_id("register")
    assert vector["text"] == frame
    assert len(raw) == 50


def test_commitment_frame_is_sha256_of_the_vector_label() -> None:
    digest = hashlib.sha256(b"loradex-proof-vector").digest()
    frame = "P0001" + base64.b64encode(digest).decode()
    assert _by_id("proof-commitment")["text"] == frame
    assert len(digest) == 32


def test_nack_bitmap_marks_chunks_0_and_2() -> None:
    text = str(_by_id("nack-bitmap")["text"])
    payload = base64.b64decode(text[5:])
    assert payload == bytes([0b00000101])


def test_ack_prefix_count_is_five() -> None:
    text = str(_by_id("ack-prefix")["text"])
    payload = base64.b64decode(text[5:])
    assert int.from_bytes(payload, "big") == 5


def test_documented_chunk_total_for_a_full_proof_fits_in_base36() -> None:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    total = 493

    def encode(value: int) -> str:
        return alphabet[value // 36] + alphabet[value % 36]

    assert encode(total) == "dp"
    assert encode(total - 1) == "do"
    assert total <= 36**2 - 1
    assert "`dp`" in SPEC
    assert "base36 `do`" in SPEC
