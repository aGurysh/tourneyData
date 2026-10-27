"""One-command tournament ingestion. Run with App/.venv/bin/python ingest.py --help."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "App"))
from backend.ingestion.batch import main

if __name__ == "__main__":
    raise SystemExit(main())
