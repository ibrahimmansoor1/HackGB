"""Read-only check of the database in DATABASE_URL: is it ready for this code?

    python scripts/db_status.py

Reports the extensions, tables, and row counts, then compares the tables with
db/schema.sql (what core/db_pg.py reads and writes) and says what to run:

    READY                        nothing to do
    run: init_db.py              tables or columns are missing; creating them is safe
    run: init_db.py --reset      tables exist in an incompatible shape (for example
                                 from another schema version); --reset WIPES all rows

The connection is opened read-only, so this script cannot change anything.
Exit code 0 only when READY.
"""
import re
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core import config  # noqa: E402  (loads rehome/.env)

SCHEMA_SQL = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
EXTENSIONS = ("vector", "timescaledb", "vectorscale")
# Tables from other schema versions that this code never uses.
FOREIGN_TABLES = {"agent_events": "an older schema version (agent_events instead of events)"}


def expected_schema() -> dict[str, set[str]]:
    """Table -> columns, parsed from the CREATE TABLE blocks in db/schema.sql."""
    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    tables: dict[str, set[str]] = {}
    for name, body in re.findall(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", sql, re.S):
        cols = set()
        for line in body.splitlines():
            word = line.strip().split(" ", 1)[0].strip(",")
            if word and word.isidentifier() and word.upper() not in (
                    "PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "CONSTRAINT"):
                cols.add(word)
        tables[name] = cols
    for name, cols in re.findall(r"ALTER TABLE (\w+) ADD COLUMN IF NOT EXISTS (\w+)", sql):
        tables.setdefault(name, set()).add(cols)
    return tables


def main() -> int:
    if not config.DATABASE_URL:
        print("DATABASE_URL is not set (rehome/.env). The app is using the in-memory DB.")
        return 1
    expected = expected_schema()
    with psycopg.connect(config.DATABASE_URL, connect_timeout=15,
                         options="-c default_transaction_read_only=on") as conn:
        version = conn.execute("SHOW server_version").fetchone()[0]
        exts = {r[0]: r[1] for r in conn.execute(
            "SELECT extname, extversion FROM pg_extension")}
        # Real tables only: extension views (pg_stat_statements, pg_buffercache)
        # live in the same schema on Tiger Cloud and aren't ours.
        rows = conn.execute(
            "SELECT c.table_name, c.column_name FROM information_schema.columns c "
            "JOIN information_schema.tables t USING (table_schema, table_name) "
            "WHERE c.table_schema = current_schema() AND t.table_type = 'BASE TABLE'").fetchall()
        actual: dict[str, set[str]] = {}
        for table, column in rows:
            actual.setdefault(table, set()).add(column)
        counts = {}
        for table in sorted(actual):
            q = psycopg.sql.SQL("SELECT count(*) FROM {}").format(psycopg.sql.Identifier(table))
            counts[table] = conn.execute(q).fetchone()[0]
        views = {r[0] for r in conn.execute(
            "SELECT matviewname FROM pg_matviews WHERE schemaname = current_schema()")}

    print(f"Postgres {version}")
    print("Extensions: " + ", ".join(
        f"{e} {exts[e]}" if e in exts else f"{e} (missing)" for e in EXTENSIONS))
    print("\nTables (rows):")
    for table in sorted(actual):
        tag = "" if table in expected else (
            f"   <- not used by this code: {FOREIGN_TABLES.get(table, 'unknown table')}")
        print(f"  {table:<16} {counts[table]:>6}{tag}")
    if "impact_hourly" in views:
        print("  impact_hourly    (continuous aggregate)")

    missing_tables = [t for t in expected if t not in actual]
    missing_cols = {t: sorted(cols - actual[t]) for t, cols in expected.items()
                    if t in actual and cols - actual[t]}
    # init_db.py adds only the columns schema.sql ALTERs in; anything else needs --reset.
    alterable = {t: set(c for tt, c in re.findall(
        r"ALTER TABLE (\w+) ADD COLUMN IF NOT EXISTS (\w+)", SCHEMA_SQL.read_text(encoding="utf-8")) if tt == t)
        for t in expected}
    needs_reset = {t: [c for c in cols if c not in alterable[t]] for t, cols in missing_cols.items()}
    needs_reset = {t: c for t, c in needs_reset.items() if c}

    print()
    if "vector" not in exts and missing_tables:
        print("Note: the pgvector extension is not installed yet; init_db.py creates it.")
    if needs_reset:
        print("NOT COMPATIBLE: these tables exist with a different shape:")
        for t, cols in needs_reset.items():
            print(f"  {t}: missing {', '.join(cols)}")
        print("\nrun: python scripts/init_db.py --reset   (WIPES all rows, then recreates)")
        return 1
    if missing_tables or missing_cols:
        if missing_tables:
            print("Missing tables: " + ", ".join(missing_tables))
        for t, cols in missing_cols.items():
            print(f"Missing in {t}: {', '.join(cols)} (init_db.py adds these)")
        print("\nrun: python scripts/init_db.py   (safe: creates what's missing, keeps data)")
        return 1
    print("READY: every table and column this code uses is present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
