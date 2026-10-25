import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_draft_schema_applies() -> None:
    connection = sqlite3.connect(":memory:")
    connection.executescript((ROOT / "src" / "loradex" / "db" / "schema.sql").read_text())
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    names = {row[0] for row in rows}
    assert names == {
        "users",
        "bonds",
        "orders",
        "swaps",
        "swap_steps",
        "packets",
        "ratelimit_events",
        "chain_cursor",
    }
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(users)").fetchall()
    }
    assert "credits_sat" in columns
