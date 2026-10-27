"""Preview or import a reviewed scraper export: python -m backend.ingestion.cli."""

import argparse
import json
from pathlib import Path
import sys

from sqlalchemy.exc import SQLAlchemyError

from backend.db.session import create_db_engine
from backend.ingestion.importer import import_export
from backend.ingestion.validation import ImportError, load_export


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Cleaned schema_version 1 JSON export")
    parser.add_argument("--apply", action="store_true", help="Write the import; default is read-only preview")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--replace", action="store_true", help="Replace an existing tournament's metadata, catches, and waterbody links")
    mode.add_argument("--metadata-only", action="store_true", help="Patch only duration and weather coordinates on an existing tournament")
    args = parser.parse_args(argv)
    engine = None
    try:
        export = load_export(args.path)
        engine = create_db_engine()
        with engine.begin() as connection:
            plan = import_export(connection, export, apply=args.apply, replace=args.replace, metadata_only=args.metadata_only)
        print(json.dumps(plan, indent=2))
        if not args.apply:
            print("Preview only. Review the JSON, timestamps, and locations; rerun with --apply to import.")
        return 0
    except (ImportError, RuntimeError, ValueError) as exc:
        print(f"Import stopped: {exc}", file=sys.stderr)
        return 2
    except SQLAlchemyError:
        # Avoid exposing credentials or catch data from SQLAlchemy exception text.
        print("Database operation failed; transaction rolled back. Check connectivity, migrations, and constraints.", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
