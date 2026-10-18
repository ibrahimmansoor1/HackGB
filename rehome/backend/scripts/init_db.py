"""Create the Tiger Data tables (db/schema.sql). Safe to re-run.

    python scripts/init_db.py            # create anything missing
    python scripts/init_db.py --reset    # drop everything first (wipes all data)

Reads DATABASE_URL and EMBED_DIM from the repo-root .env.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg  # noqa: E402
from app.core import config  # noqa: E402

SCHEMA = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
RESET = """
DROP MATERIALIZED VIEW IF EXISTS impact_hourly CASCADE;
DROP TABLE IF EXISTS listings, matches, requests, items, events CASCADE;
DROP SEQUENCE IF EXISTS item_seq, request_seq, match_seq, listing_seq;
"""


def statements(sql: str) -> list[str]:
    """Split on lines ending in ';' (the schema has no semicolons inside strings)."""
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    out, cur = [], []
    for ln in lines:
        cur.append(ln)
        if ln.rstrip().endswith(";"):
            out.append("\n".join(cur).strip())
            cur = []
    return [s for s in out if s.strip(";").strip()]


def main() -> None:
    if not config.DATABASE_URL:
        sys.exit("DATABASE_URL is not set in .env")
    sql = SCHEMA.read_text().replace("{EMBED_DIM}", str(config.EMBED_DIM))
    with psycopg.connect(config.DATABASE_URL, autocommit=True) as conn:
        if "--reset" in sys.argv:
            for stmt in statements(RESET):
                conn.execute(stmt)
            print("Dropped existing tables.")
        for stmt in statements(sql):
            conn.execute(stmt)
    print(f"Schema ready (embedding dimension {config.EMBED_DIM}).")


if __name__ == "__main__":
    main()
