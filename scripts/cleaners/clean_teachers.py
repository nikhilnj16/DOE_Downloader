"""
scripts/cleaners/clean_teachers.py
====================================
Cleaner for teacher / educator records — works for both Nevada and Massachusetts.

Reads every file in data/{state}/raw/teacher_records/, normalises the data,
and saves cleaned CSVs to data/{state}/cleaned/teacher_records/.

Supported input formats: .xlsx, .xls, .csv, .pdf

Cleaning steps applied
----------------------
1. Read file into a pandas DataFrame.
2. Standardise column names: lowercase, underscores, strip whitespace.
3. Drop fully-empty rows and columns.
4. Normalise license status values (strip whitespace, title-case).
5. Add metadata columns: ``state`` and ``source_file``.
6. Save as UTF-8 CSV.
"""

import sys
from pathlib import Path

import pandas as pd
import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config import STATES, raw_dir, cleaned_dir
from scripts.utils.logger import setup_logger

logger = setup_logger("cleaner.teachers")

CATEGORY = "teacher_records"


def _standardise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise column names to snake_case."""
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(r"[\s\-]+", "_", regex=True)
        .str.replace(r"_+", "_", regex=True)
        .str.strip("_")
    )
    return df


def _normalise_license_status(df: pd.DataFrame) -> pd.DataFrame:
    """
    If a 'license_status' or 'status' column exists, normalise its values
    to Title Case with stripped whitespace.
    """
    for col in ("license_status", "status", "licensure_status"):
        if col in df.columns:
            df[col] = df[col].str.strip().str.title()
    return df


def _read_file(path: Path) -> pd.DataFrame:
    """Load a raw teacher records file into a DataFrame."""
    suffix = path.suffix.lower()

    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype=str)

    if suffix == ".csv":
        return pd.read_csv(path, dtype=str, encoding="utf-8", encoding_errors="replace")

    if suffix == ".pdf":
        frames: list[pd.DataFrame] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    header, *rows = table
                    frames.append(pd.DataFrame(rows, columns=header))
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    raise ValueError(f"Unsupported file type: {suffix}")


def _clean_dataframe(df: pd.DataFrame, state: str, source_file: str) -> pd.DataFrame:
    """Apply standard cleaning transformations to a teacher records DataFrame."""
    df = _standardise_columns(df)
    df = df.dropna(how="all").dropna(axis=1, how="all")
    df = _normalise_license_status(df)
    df["state"] = state
    df["source_file"] = source_file
    return df.reset_index(drop=True)


def clean(state: str) -> None:
    """
    Clean all raw teacher record files for the given state.

    Parameters
    ----------
    state : str  e.g. "nevada" or "massachusetts"
    """
    if state not in STATES:
        raise ValueError(f"Unknown state '{state}'. Expected one of {STATES}.")

    raw_path = raw_dir(state, CATEGORY)
    out_path = cleaned_dir(state, CATEGORY)
    out_path.mkdir(parents=True, exist_ok=True)

    raw_files = [
        f for f in raw_path.iterdir()
        if f.is_file() and f.suffix.lower() in {".xlsx", ".xls", ".csv", ".pdf"}
    ]

    if not raw_files:
        logger.warning("No raw teacher record files found for %s in %s", state, raw_path)
        return

    logger.info(
        "Cleaning %d teacher record file(s) for %s → %s",
        len(raw_files), state, out_path,
    )

    for raw_file in raw_files:
        logger.debug("Processing: %s", raw_file.name)
        try:
            df = _read_file(raw_file)
            if df.empty:
                logger.warning("No data extracted from %s — skipping.", raw_file.name)
                continue
            df = _clean_dataframe(df, state, raw_file.name)
            out_file = out_path / (raw_file.stem + "_cleaned.csv")
            df.to_csv(out_file, index=False, encoding="utf-8")
            logger.info("Saved cleaned file: %s (%d rows)", out_file.name, len(df))
        except Exception as exc:
            logger.error("Failed to clean %s: %s", raw_file.name, exc)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Clean raw teacher record files for a given state."
    )
    parser.add_argument("--state", choices=STATES, required=True)
    args = parser.parse_args()
    clean(args.state)
