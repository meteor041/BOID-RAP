from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from boid_rap.database import DEFAULT_DB_PATH, apply_migrations, list_applied_migrations


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply BOID-RAP database migrations.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to SQLite database file")
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show applied migrations without applying new ones",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if args.status:
        versions = list_applied_migrations(db_path)
        print(f"database={db_path}")
        if versions:
            for version in versions:
                print(version)
        else:
            print("no migrations applied")
        return

    applied = apply_migrations(db_path)
    print(f"database={db_path}")
    if applied:
        for version in applied:
            print(f"applied {version}")
    else:
        print("no pending migrations")


if __name__ == "__main__":
    main()
