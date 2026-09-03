"""Seed the SQLite database from the sample CSV and train the ML model."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .ingest import parse_transactions_csv_path, replace_all_from_dataframe


DATASETS_DIR = Path(__file__).resolve().parent.parent / "datasets"
DEFAULT_CSV = DATASETS_DIR / "sample_transactions.csv"


def clear_and_seed(db: Session, csv_path: Path = DEFAULT_CSV) -> dict:
    df = parse_transactions_csv_path(csv_path)
    return replace_all_from_dataframe(db, df)


def run_seed() -> dict:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        return clear_and_seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    print(run_seed())
