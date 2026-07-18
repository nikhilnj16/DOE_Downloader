"""
main.py
========
Entry point for the Education Data Pipeline.

Usage examples
--------------
Run downloads for all states and all categories (cleaning disabled by default):
    python main.py --state both --category all

Run only the Nevada assessment/by_race subcategory:
    python main.py --state nevada --category assessments --subcategory by_race

Run Massachusetts financials and upload to Drive afterwards:
    python main.py --state massachusetts --category financials --upload

Run all states and categories, upload to Drive:
    python main.py --state both --category all --upload

Run Nevada financials only:
    python main.py --state nevada --category financials
"""

import argparse
import importlib
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on path for standalone execution
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import CATEGORIES, STATES, ASSESSMENT_SUBCATEGORIES, SKIP_CLEANING, ENABLE_DRIVE_UPLOAD, DRIVE_ROOT_FOLDER_ID
from scripts.utils.file_utils import create_dir_structure
from scripts.utils.logger import setup_logger

logger = setup_logger("pipeline.main")

# ---------------------------------------------------------------------------
# Registry: maps (state, category, subcategory) → downloader module + class
#
# subcategory is "" for non-assessment categories.
# For assessments, subcategory can be "overall", "by_race", etc., or "all".
# ---------------------------------------------------------------------------
_DOWNLOADER_REGISTRY: dict[tuple[str, str, str], tuple[str, str, str | None]] = {
    # ---- Nevada: assessments (per subcategory) ----
    ("nevada", "assessments", "overall"):    ("scripts.downloaders.nevada.nv_test_scores",      "NevadaTestScoresDownloader",    "download_all"),
    ("nevada", "assessments", "by_race"):    ("scripts.downloaders.nevada.nv_test_scores",      "NevadaTestScoresDownloader",    "download_by_race"),
    ("nevada", "assessments", "by_gender"):  ("scripts.downloaders.nevada.nv_test_scores",      "NevadaTestScoresDownloader",    "download_by_gender"),
    ("nevada", "assessments", "by_iep_504"): ("scripts.downloaders.nevada.nv_test_scores",      "NevadaTestScoresDownloader",    "download_by_iep"),
    ("nevada", "assessments", "by_ell"):     ("scripts.downloaders.nevada.nv_test_scores",      "NevadaTestScoresDownloader",    "download_by_ell"),
    ("nevada", "assessments", "all"):        ("scripts.downloaders.nevada.nv_test_scores",      "NevadaTestScoresDownloader",    "download_all_assessments"),

    # ---- Nevada: other categories ----
    ("nevada", "financials", ""):            ("scripts.downloaders.nevada.nv_financials",       "NevadaFinancialsDownloader",    "download_all"),
    ("nevada", "teacher_staff", ""):         ("scripts.downloaders.nevada.nv_teacher_records",  "NevadaTeacherRecordsDownloader","download_all"),
    ("nevada", "enrollment_attendance", ""): ("scripts.downloaders.nevada.nv_enrollment",       "NevadaEnrollmentDownloader",    "download_all"),

    # ---- Massachusetts: assessments (per subcategory) ----
    ("massachusetts", "assessments", "overall"):    ("scripts.downloaders.massachusetts.ma_test_scores", "MassachusettsAssessmentsDownloader", "download_overall"),
    ("massachusetts", "assessments", "by_race"):    ("scripts.downloaders.massachusetts.ma_test_scores", "MassachusettsAssessmentsDownloader", "download_by_race"),
    ("massachusetts", "assessments", "by_gender"):  ("scripts.downloaders.massachusetts.ma_test_scores", "MassachusettsAssessmentsDownloader", "download_by_gender"),
    ("massachusetts", "assessments", "by_iep_504"): ("scripts.downloaders.massachusetts.ma_test_scores", "MassachusettsAssessmentsDownloader", "download_by_iep"),
    ("massachusetts", "assessments", "by_ell"):     ("scripts.downloaders.massachusetts.ma_test_scores", "MassachusettsAssessmentsDownloader", "download_by_ell"),
    ("massachusetts", "assessments", "all"):        ("scripts.downloaders.massachusetts.ma_test_scores", "MassachusettsAssessmentsDownloader", "download_all_assessments"),

    ("massachusetts", "financials", ""):            ("scripts.downloaders.massachusetts.ma_financials",        "MassachusettsFinancialsDownloader",    "download_all"),
    ("massachusetts", "teacher_staff", ""):         ("scripts.downloaders.massachusetts.ma_teacher_records",   "MassachusettsTeacherRecordsDownloader","download_all"),
    ("massachusetts", "enrollment_attendance", ""): ("scripts.downloaders.massachusetts.ma_enrollment",         "MassachusettsEnrollmentDownloader",    "download_all"),

    # ---- Alaska: assessments (per subcategory) ----
    ("alaska", "assessments", "overall"):    ("scripts.downloaders.alaska.ak_downloader", "AlaskaDownloader", "download_overall"),
    ("alaska", "assessments", "by_race"):    ("scripts.downloaders.alaska.ak_downloader", "AlaskaDownloader", "download_by_race"),
    ("alaska", "assessments", "by_gender"):  ("scripts.downloaders.alaska.ak_downloader", "AlaskaDownloader", "download_by_gender"),
    ("alaska", "assessments", "by_iep_504"): ("scripts.downloaders.alaska.ak_downloader", "AlaskaDownloader", "download_by_iep"),
    ("alaska", "assessments", "by_ell"):     ("scripts.downloaders.alaska.ak_downloader", "AlaskaDownloader", "download_by_ell"),
    ("alaska", "assessments", "all"):        ("scripts.downloaders.alaska.ak_downloader", "AlaskaDownloader", "download_all"),

    # ---- Alaska: other categories ----
    ("alaska", "financials", ""):            ("scripts.downloaders.alaska.ak_downloader", "AlaskaDownloader", "download_financials"),
    ("alaska", "teacher_staff", ""):         ("scripts.downloaders.alaska.ak_downloader", "AlaskaDownloader", "download_teacher_staff"),
    ("alaska", "enrollment_attendance", ""): ("scripts.downloaders.alaska.ak_downloader", "AlaskaDownloader", "download_enrollment_attendance"),

    # ---- Ohio: assessments ----
    ("ohio", "assessments", "overall"):    ("scripts.downloaders.ohio.oh_downloader", "OhioDownloader", "download_assessments"),
    ("ohio", "assessments", "by_race"):    ("scripts.downloaders.ohio.oh_downloader", "OhioDownloader", "download_assessments"),
    ("ohio", "assessments", "by_gender"):  ("scripts.downloaders.ohio.oh_downloader", "OhioDownloader", "download_assessments"),
    ("ohio", "assessments", "by_iep_504"): ("scripts.downloaders.ohio.oh_downloader", "OhioDownloader", "download_assessments"),
    ("ohio", "assessments", "by_ell"):     ("scripts.downloaders.ohio.oh_downloader", "OhioDownloader", "download_assessments"),
    ("ohio", "assessments", "all"):        ("scripts.downloaders.ohio.oh_downloader", "OhioDownloader", "download_assessments"),

    # ---- Ohio: other categories ----
    ("ohio", "financials", ""):            ("scripts.downloaders.ohio.oh_downloader", "OhioDownloader", "download_financials"),
    ("ohio", "teacher_staff", ""):         ("scripts.downloaders.ohio.oh_downloader", "OhioDownloader", "download_teacher_staff"),
    ("ohio", "enrollment_attendance", ""): ("scripts.downloaders.ohio.oh_downloader", "OhioDownloader", "download_enrollment_attendance"),

    # ---- New Jersey: assessments (per subcategory) ----
    ("new_jersey", "assessments", "overall"):    ("scripts.downloaders.new_jersey.nj_downloader", "NewJerseyDownloader", "download_assessments"),
    ("new_jersey", "assessments", "by_race"):    ("scripts.downloaders.new_jersey.nj_downloader", "NewJerseyDownloader", "download_assessments"),
    ("new_jersey", "assessments", "by_gender"):  ("scripts.downloaders.new_jersey.nj_downloader", "NewJerseyDownloader", "download_assessments"),
    ("new_jersey", "assessments", "by_iep_504"): ("scripts.downloaders.new_jersey.nj_downloader", "NewJerseyDownloader", "download_assessments"),
    ("new_jersey", "assessments", "by_ell"):     ("scripts.downloaders.new_jersey.nj_downloader", "NewJerseyDownloader", "download_assessments"),
    ("new_jersey", "assessments", "all"):        ("scripts.downloaders.new_jersey.nj_downloader", "NewJerseyDownloader", "download_assessments"),

    # ---- New Jersey: other categories ----
    ("new_jersey", "financials", ""):            ("scripts.downloaders.new_jersey.nj_downloader", "NewJerseyDownloader", "download_financials"),
    ("new_jersey", "teacher_staff", ""):         ("scripts.downloaders.new_jersey.nj_downloader", "NewJerseyDownloader", "download_teacher_staff"),
    ("new_jersey", "enrollment_attendance", ""): ("scripts.downloaders.new_jersey.nj_downloader", "NewJerseyDownloader", "download_enrollment_attendance"),

    # ---- Tennessee: assessments (per subcategory) ----
    ("tennessee", "assessments", "overall"):    ("scripts.downloaders.tennessee.tn_downloader", "TennesseeDownloader", "download_assessments"),
    ("tennessee", "assessments", "by_race"):    ("scripts.downloaders.tennessee.tn_downloader", "TennesseeDownloader", "download_assessments"),
    ("tennessee", "assessments", "by_gender"):  ("scripts.downloaders.tennessee.tn_downloader", "TennesseeDownloader", "download_assessments"),
    ("tennessee", "assessments", "by_iep_504"): ("scripts.downloaders.tennessee.tn_downloader", "TennesseeDownloader", "download_assessments"),
    ("tennessee", "assessments", "by_ell"):     ("scripts.downloaders.tennessee.tn_downloader", "TennesseeDownloader", "download_assessments"),
    ("tennessee", "assessments", "all"):        ("scripts.downloaders.tennessee.tn_downloader", "TennesseeDownloader", "download_assessments"),

    # ---- Tennessee: other categories ----
    ("tennessee", "financials", ""):            ("scripts.downloaders.tennessee.tn_downloader", "TennesseeDownloader", "download_financials"),
    ("tennessee", "teacher_staff", ""):         ("scripts.downloaders.tennessee.tn_downloader", "TennesseeDownloader", "download_teacher_staff"),
    ("tennessee", "enrollment_attendance", ""): ("scripts.downloaders.tennessee.tn_downloader", "TennesseeDownloader", "download_enrollment_attendance"),
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
        description="Education Data Pipeline — download DOE data for Nevada and Massachusetts.",
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
        "--subcategory",
        choices=list(ASSESSMENT_SUBCATEGORIES.keys()) + ["all"],
        default="all",
        help=(
            "Only applies when --category assessments. "
            "Choices: overall, by_race, by_gender, by_iep_504, by_ell, all. (default: all)"
        ),
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload downloaded files to Google Drive after all downloads complete.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        default=True,
        help="Skip all cleaning steps (this is the default; cleaning is disabled).",
    )
    # Backward-compat flags from the previous main.py
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip the download step entirely.",
    )
    parser.add_argument(
        "--skip-clean",
        action="store_true",
        default=True,
        help="Skip the cleaning step (default: True; cleaning is disabled).",
    )
    return parser


# ---------------------------------------------------------------------------
# Orchestration helpers
# ---------------------------------------------------------------------------

def resolve_states(state_arg: str) -> list[str]:
    """
    Resolve --state argument to a list of state identifiers.

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
    Resolve --category argument to a list of category identifiers.

    Parameters
    ----------
    category_arg : str  "all" or a single category name.

    Returns
    -------
    list[str]
    """
    return CATEGORIES if category_arg == "all" else [category_arg]


def resolve_subcategories(subcategory_arg: str) -> list[str]:
    """
    Resolve --subcategory argument to a list of assessment subcategory keys.

    Parameters
    ----------
    subcategory_arg : str  "all" or a specific subcategory key.

    Returns
    -------
    list[str]
    """
    if subcategory_arg == "all":
        return list(ASSESSMENT_SUBCATEGORIES.keys())
    return [subcategory_arg]


def run_downloader(state: str, category: str, subcategory: str = "") -> dict:
    """
    Dynamically import and execute the downloader for a given state + category (+subcategory).

    Parameters
    ----------
    state       : str  e.g. "nevada"
    category    : str  e.g. "assessments"
    subcategory : str  e.g. "by_race" (empty string for non-assessment categories)

    Returns
    -------
    dict  Summary with keys "downloaded", "skipped", "failed" (best-effort counts).
    """
    summary = {"downloaded": 0, "skipped": 0, "failed": 0}
    key = (state, category, subcategory)

    if key not in _DOWNLOADER_REGISTRY:
        logger.error("No downloader registered for (%s, %s, '%s').", state, category, subcategory)
        summary["failed"] += 1
        return summary

    module_path, class_name, method_name = _DOWNLOADER_REGISTRY[key]
    logger.info(
        "Loading downloader: %s.%s.%s()",
        module_path, class_name, method_name or "download_all",
    )

    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        instance = cls()

        # Snapshot file count in output dirs BEFORE running
        from config import DATA_DIR
        if category == "assessments" and subcategory and subcategory != "all":
            out_dirs = [DATA_DIR / state / category / subcategory]
        elif category == "assessments":
            out_dirs = [DATA_DIR / state / category / sub for sub in ASSESSMENT_SUBCATEGORIES]
        else:
            out_dirs = [DATA_DIR / state / category]
        files_before = sum(
            len([f for f in d.glob("*") if f.is_file()])
            for d in out_dirs if d.exists()
        )

        if method_name and hasattr(instance, method_name):
            getattr(instance, method_name)()
        else:
            instance.download_all()

        # Snapshot AFTER and compute delta
        files_after = sum(
            len([f for f in d.glob("*") if f.is_file()])
            for d in out_dirs if d.exists()
        )
        summary["downloaded"] = max(0, files_after - files_before)

    except Exception as exc:
        logger.error(
            "Downloader %s.%s failed: %s", class_name, method_name, exc, exc_info=True
        )
        summary["failed"] += 1

    return summary


def run_drive_upload(state: str) -> None:
    """
    Mirror local state data folder to Google Drive.

    Parameters
    ----------
    state : str  e.g. "nevada"
    """
    if not ENABLE_DRIVE_UPLOAD:
        logger.info("Drive upload is disabled in config. Set ENABLE_DRIVE_UPLOAD = True to enable.")
        return

    if not DRIVE_ROOT_FOLDER_ID:
        logger.warning(
            "DRIVE_ROOT_FOLDER_ID is empty in config.py — skipping Drive upload for %s. "
            "Fill in the folder ID and re-run with --upload.",
            state,
        )
        return

    try:
        from scripts.utils.drive_upload import upload_state_folder
        from config import DATA_DIR
        local_path = DATA_DIR / state
        logger.info("Uploading %s to Drive folder %s ...", local_path, DRIVE_ROOT_FOLDER_ID)
        result = upload_state_folder(local_path, DRIVE_ROOT_FOLDER_ID)
        logger.info(
            "Drive upload for %s: %d uploaded, %d skipped, %d failed",
            state, result["uploaded"], result["skipped"], result["failed"],
        )
    except Exception as exc:
        logger.error("Drive upload failed for %s: %s", state, exc)


def _print_summary_table(rows: list[dict]) -> None:
    """
    Print a formatted summary table to stdout.

    Parameters
    ----------
    rows : list[dict]
        Each dict: state, category, subcategory, downloaded, skipped, failed.
    """
    col_widths = {
        "state":       15,
        "category":    22,
        "subcategory": 14,
        "downloaded":  12,
        "skipped":     9,
        "failed":      8,
    }
    header = (
        f"{'State':<{col_widths['state']}}"
        f"{'Category':<{col_widths['category']}}"
        f"{'Subcategory':<{col_widths['subcategory']}}"
        f"{'Downloaded':>{col_widths['downloaded']}}"
        f"{'Skipped':>{col_widths['skipped']}}"
        f"{'Failed':>{col_widths['failed']}}"
    )
    sep = "-" * len(header)
    print()
    print("=" * len(header))
    print("  PIPELINE SUMMARY")
    print("=" * len(header))
    print(header)
    print(sep)
    for row in rows:
        print(
            f"{row['state']:<{col_widths['state']}}"
            f"{row['category']:<{col_widths['category']}}"
            f"{row['subcategory']:<{col_widths['subcategory']}}"
            f"{row['downloaded']:>{col_widths['downloaded']}}"
            f"{row['skipped']:>{col_widths['skipped']}}"
            f"{row['failed']:>{col_widths['failed']}}"
        )
    print(sep)
    totals = {k: sum(r[k] for r in rows) for k in ("downloaded", "skipped", "failed")}
    print(
        f"{'TOTAL':<{col_widths['state'] + col_widths['category'] + col_widths['subcategory']}}"
        f"{totals['downloaded']:>{col_widths['downloaded']}}"
        f"{totals['skipped']:>{col_widths['skipped']}}"
        f"{totals['failed']:>{col_widths['failed']}}"
    )
    print("=" * len(header))
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Parse CLI arguments, create directory structure, then orchestrate
    downloaders based on user flags. Print a summary table on completion.
    """
    parser = build_parser()
    args = parser.parse_args()

    start_time = time.time()
    logger.info("=" * 60)
    logger.info("Education Data Pipeline — starting run")
    logger.info("  State(s)    : %s", args.state)
    logger.info("  Category    : %s", args.category)
    logger.info("  Subcategory : %s", args.subcategory)
    logger.info("  Upload      : %s", args.upload)
    logger.info("  Cleaning    : DISABLED (SKIP_CLEANING=True)")
    logger.info("=" * 60)

    # Always ensure the directory tree exists
    create_dir_structure()

    states = resolve_states(args.state)
    categories = resolve_categories(args.category)

    summary_rows: list[dict] = []

    for state in states:
        for category in categories:
            if args.skip_download:
                continue

            if category == "assessments":
                # Run per subcategory so users can target specific breakdowns
                subcategories = resolve_subcategories(args.subcategory)
                for sub in subcategories:
                    logger.info("--- Download: %s / %s / %s ---", state, category, sub)
                    result = run_downloader(state, category, sub)
                    summary_rows.append({
                        "state": state,
                        "category": category,
                        "subcategory": sub,
                        **result,
                    })
            else:
                logger.info("--- Download: %s / %s ---", state, category)
                result = run_downloader(state, category, "")
                summary_rows.append({
                    "state": state,
                    "category": category,
                    "subcategory": "",
                    **result,
                })

        # Drive upload (per state, after all categories done)
        if args.upload:
            run_drive_upload(state)

    elapsed = time.time() - start_time
    logger.info("Pipeline complete in %.1f seconds.", elapsed)

    # Print summary table
    if summary_rows:
        _print_summary_table(summary_rows)


if __name__ == "__main__":
    main()
