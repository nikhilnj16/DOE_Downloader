"""
main.py
========
Entry point for the Education Data Pipeline.

Usage examples
--------------
Run the full pipeline for both states and all categories:
    python main.py --state both --category all

Run only the Nevada test scores downloader:
    python main.py --state nevada --category test_scores

Run the Massachusetts financials downloader and skip cleaning:
    python main.py --state massachusetts --category financials --skip-clean

Skip downloading and only run the enrollment cleaner for Nevada:
    python main.py --state nevada --category enrollment --skip-download
"""

import argparse
import importlib
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on path for standalone execution
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import CATEGORIES, STATES
from scripts.utils.file_utils import create_dir_structure
from scripts.utils.logger import setup_logger

logger = setup_logger("pipeline.main")

# ---------------------------------------------------------------------------
# Registry: maps (state, category) → downloader class path + name
# ---------------------------------------------------------------------------
_DOWNLOADER_REGISTRY: dict[tuple[str, str], tuple[str, str]] = {
    ("nevada", "test_scores"):      ("scripts.downloaders.nevada.nv_test_scores",      "NevadaTestScoresDownloader"),
    ("nevada", "financials"):       ("scripts.downloaders.nevada.nv_financials",        "NevadaFinancialsDownloader"),
    ("nevada", "teacher_records"):  ("scripts.downloaders.nevada.nv_teacher_records",   "NevadaTeacherRecordsDownloader"),
    ("nevada", "enrollment"):       ("scripts.downloaders.nevada.nv_enrollment",         "NevadaEnrollmentDownloader"),
    ("nevada", "suspensions"):      ("scripts.downloaders.nevada.nv_suspensions",        "NevadaSuspensionsDownloader"),
    ("massachusetts", "test_scores"):      ("scripts.downloaders.massachusetts.ma_test_scores",      "MassachusettsTestScoresDownloader"),
    ("massachusetts", "financials"):       ("scripts.downloaders.massachusetts.ma_financials",        "MassachusettsFinancialsDownloader"),
    ("massachusetts", "teacher_records"):  ("scripts.downloaders.massachusetts.ma_teacher_records",   "MassachusettsTeacherRecordsDownloader"),
    ("massachusetts", "enrollment"):       ("scripts.downloaders.massachusetts.ma_enrollment",         "MassachusettsEnrollmentDownloader"),
    ("massachusetts", "suspensions"):      ("scripts.downloaders.massachusetts.ma_suspensions",        "MassachusettsSuspensionsDownloader"),
}

# Registry: maps category → cleaner module path + function name
_CLEANER_REGISTRY: dict[str, tuple[str, str]] = {
    "test_scores":     ("scripts.cleaners.clean_test_scores", "clean"),
    "financials":      ("scripts.cleaners.clean_financials",  "clean"),
    "teacher_records": ("scripts.cleaners.clean_teachers",    "clean"),
    "enrollment":      ("scripts.cleaners.clean_enrollment",  "clean"),
    "suspensions":     ("scripts.cleaners.clean_suspensions", "clean"),
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """
    Build and return the argparse CLI parser.

    Returns
    -------
    argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Education Data Pipeline — download and clean public DOE data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--state",
        choices=STATES + ["both"],
        default="both",
        help="Which state(s) to process. Use 'both' for all states. (default: both)",
    )
    parser.add_argument(
        "--category",
        choices=CATEGORIES + ["all"],
        default="all",
        help="Which data category to process. Use 'all' for every category. (default: all)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip the download step and go straight to cleaning.",
    )
    parser.add_argument(
        "--skip-clean",
        action="store_true",
        help="Skip the cleaning step (download only).",
    )
    return parser


# ---------------------------------------------------------------------------
# Orchestration helpers
# ---------------------------------------------------------------------------

def resolve_states(state_arg: str) -> list[str]:
    """
    Resolve the --state argument to a list of state identifiers.

    Parameters
    ----------
    state_arg : str  "both" or a single state name.

    Returns
    -------
    list[str]
    """
    return STATES if state_arg == "both" else [state_arg]


def resolve_categories(category_arg: str) -> list[str]:
    """
    Resolve the --category argument to a list of category identifiers.

    Parameters
    ----------
    category_arg : str  "all" or a single category name.

    Returns
    -------
    list[str]
    """
    return CATEGORIES if category_arg == "all" else [category_arg]


def run_downloader(state: str, category: str) -> None:
    """
    Dynamically import and execute the downloader for a given state + category.

    Parameters
    ----------
    state    : str  e.g. "nevada"
    category : str  e.g. "test_scores"
    """
    key = (state, category)
    if key not in _DOWNLOADER_REGISTRY:
        logger.error("No downloader registered for (%s, %s).", state, category)
        return

    module_path, class_name = _DOWNLOADER_REGISTRY[key]
    logger.info("Loading downloader: %s.%s", module_path, class_name)

    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        instance = cls()
        instance.download_all()
    except Exception as exc:
        logger.error(
            "Downloader %s failed: %s", class_name, exc, exc_info=True
        )


def run_cleaner(state: str, category: str) -> None:
    """
    Dynamically import and execute the cleaner for a given state + category.

    Parameters
    ----------
    state    : str  e.g. "nevada"
    category : str  e.g. "test_scores"
    """
    if category not in _CLEANER_REGISTRY:
        logger.error("No cleaner registered for category '%s'.", category)
        return

    module_path, func_name = _CLEANER_REGISTRY[category]
    logger.info("Loading cleaner: %s.%s(state=%s)", module_path, func_name, state)

    try:
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        func(state)
    except Exception as exc:
        logger.error(
            "Cleaner for (%s, %s) failed: %s", state, category, exc, exc_info=True
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Parse CLI arguments, create directory structure, then orchestrate
    downloaders and/or cleaners based on user flags.
    """
    parser = build_parser()
    args = parser.parse_args()

    start_time = time.time()
    logger.info("=" * 60)
    logger.info("Education Data Pipeline — starting run")
    logger.info("  State(s)  : %s", args.state)
    logger.info("  Category  : %s", args.category)
    logger.info("  Skip DL   : %s", args.skip_download)
    logger.info("  Skip Clean: %s", args.skip_clean)
    logger.info("=" * 60)

    # Always ensure the directory tree exists
    create_dir_structure()

    states = resolve_states(args.state)
    categories = resolve_categories(args.category)

    download_count = 0
    clean_count = 0

    for state in states:
        for category in categories:
            if not args.skip_download:
                logger.info("--- Download: %s / %s ---", state, category)
                run_downloader(state, category)
                download_count += 1

            if not args.skip_clean:
                logger.info("--- Clean:    %s / %s ---", state, category)
                run_cleaner(state, category)
                clean_count += 1

    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info("Pipeline complete.")
    logger.info("  Download tasks run : %d", download_count)
    logger.info("  Cleaner tasks run  : %d", clean_count)
    logger.info("  Total elapsed      : %.1f seconds", elapsed)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
