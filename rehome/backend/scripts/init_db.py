"""Set up or inspect the Tiger Data database.

Run from backend/ with DATABASE_URL in the repo .env:

    python scripts/init_db.py            # create extensions, tables, indexes (safe to repeat)
    python scripts/init_db.py --check    # show what's there: extensions, index type, row counts
    python scripts/init_db.py --clear    # delete all rows, keep tables (fresh demo)
    python scripts/init_db.py --reset    # drop and recreate everything (after changing EMBED_DIM)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import config  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="only report the current state")
    g.add_argument("--clear", action="store_true", help="delete all rows, keep the tables")
    g.add_argument("--reset", action="store_true", help="drop and recreate all tables")
    args = ap.parse_args()

    if not config.DATABASE_URL:
        sys.exit("DATABASE_URL is empty. Put your Tiger Cloud connection string in the "
                 "repo .env first (see docs/08-database.md).")

    from app.core import db_tiger as db

    if args.reset:
        if input("This deletes every Rehome table and row. Type 'reset' to continue: ") != "reset":
            sys.exit("Cancelled.")
        db.drop_all()
        print("Dropped all tables.")
    if not args.check:
        db.init_schema()
        print(f"Schema ready (vector size {config.EMBED_DIM}).")
    if args.clear:
        db.reset()
        print("Deleted all rows; ids restart at 0001.")

    print(json.dumps(db.info(), indent=2, default=str))
    db.close()


if __name__ == "__main__":
    main()
