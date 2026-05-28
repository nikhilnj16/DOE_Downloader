"""
scripts/downloaders/base_downloader.py
=======================================
Abstract base class for all state/category downloader scripts.

All concrete downloaders (e.g. NevadaTestScoresDownloader) inherit from
BaseDownloader and only need to define:
  - STATE      : str
  - CATEGORY   : str
  - URLS       : list[str]
  - download_all() method

BaseDownloader handles:
  - HTTP session management with retry + exponential back-off
  - File-type detection (Content-Type header or URL extension)
  - Safe filename generation
  - Disk writes with explicit UTF-8 encoding awareness
  - Per-download logging to both pipeline.log and download_manifest.csv
"""

import logging
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Ensure the project root is on the path so config + utils are importable
# when a downloader script is run standalone.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from config import (
    BACKOFF_FACTOR,
    MAX_RETRIES,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    RETRY_STATUS_CODES,
    raw_dir,
)
from scripts.utils.file_utils import get_file_extension, safe_filename
from scripts.utils.logger import log_download, setup_logger


class BaseDownloader(ABC):
    """
    Abstract base class for all education data downloaders.

    Subclasses must define class attributes STATE, CATEGORY, and URLS,
    and implement the download_all() method.

    Attributes
    ----------
    STATE    : str   State identifier, e.g. "nevada"
    CATEGORY : str   Data category, e.g. "test_scores"
    URLS     : list  Source URLs specific to this state + category
    """

    STATE: str = ""
    CATEGORY: str = ""
    URLS: list[str] = []

    def __init__(self) -> None:
        """Initialise the downloader: set up logger and HTTP session."""
        if not self.STATE or not self.CATEGORY:
            raise NotImplementedError(
                "Subclasses must define STATE and CATEGORY class attributes."
            )

        self.logger: logging.Logger = setup_logger(
            name=f"{self.STATE}.{self.CATEGORY}"
        )
        self.session: requests.Session = self._build_session()
        self.output_dir: Path = raw_dir(self.STATE, self.CATEGORY)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def download_all(self) -> None:
        """
        Download every file defined in self.URLS.

        Subclasses implement the iteration logic here, optionally handling
        site-specific behaviour such as pagination or form submissions.
        """

    # ------------------------------------------------------------------
    # Core download helpers  (not overridden by subclasses)
    # ------------------------------------------------------------------

    def download_file(self, url: str, destination_path: Path) -> bool:
        """
        Download a single file to *destination_path* with retry logic.

        Retries up to MAX_RETRIES times with exponential back-off on
        transient HTTP errors or connection failures.

        Parameters
        ----------
        url              : str   The remote URL to fetch.
        destination_path : Path  Where to save the file locally.

        Returns
        -------
        bool  True on success, False on final failure.
        """
        self.logger.info("Downloading: %s", url)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.session.get(
                    url, timeout=REQUEST_TIMEOUT, stream=True
                )
                response.raise_for_status()

                # Determine final destination (may need extension appended)
                final_path = self._resolve_destination(url, response, destination_path)
                content = response.content
                self.save_file(content, final_path)

                filesize_kb = len(content) / 1024
                self.log_download(url, final_path.name, "success", filesize_kb)
                self.logger.info(
                    "Saved %s (%.1f KB)", final_path.name, filesize_kb
                )
                return True

            except requests.exceptions.HTTPError as exc:
                self.logger.warning(
                    "Attempt %d/%d — HTTP error for %s: %s",
                    attempt, MAX_RETRIES, url, exc,
                )
            except requests.exceptions.ConnectionError as exc:
                self.logger.warning(
                    "Attempt %d/%d — Connection error for %s: %s",
                    attempt, MAX_RETRIES, url, exc,
                )
            except requests.exceptions.Timeout:
                self.logger.warning(
                    "Attempt %d/%d — Timeout for %s", attempt, MAX_RETRIES, url
                )
            except requests.exceptions.RequestException as exc:
                self.logger.error("Unrecoverable request error for %s: %s", url, exc)
                break

            if attempt < MAX_RETRIES:
                sleep_seconds = BACKOFF_FACTOR ** attempt
                self.logger.debug(
                    "Retrying in %.1f seconds…", sleep_seconds
                )
                time.sleep(sleep_seconds)

        self.log_download(url, "", "failed", 0.0)
        self.logger.error("Failed to download after %d attempts: %s", MAX_RETRIES, url)
        return False

    def detect_extension(self, url: str, response: requests.Response) -> str:
        """
        Detect the file extension from the HTTP response or URL.

        Delegates to :func:`scripts.utils.file_utils.get_file_extension`.

        Parameters
        ----------
        url      : str
        response : requests.Response

        Returns
        -------
        str  Extension including leading dot, e.g. ".xlsx", or "".
        """
        return get_file_extension(url, response)

    def safe_filename(self, url: str) -> str:
        """
        Convert a URL to a safe local filename stem (no extension).

        Delegates to :func:`scripts.utils.file_utils.safe_filename`.

        Parameters
        ----------
        url : str

        Returns
        -------
        str  A filesystem-safe filename stem.
        """
        return safe_filename(url)

    def save_file(self, content: bytes, path: Path) -> None:
        """
        Write raw bytes to *path*, creating parent directories as needed.

        Parameters
        ----------
        content : bytes  Raw file bytes from the HTTP response.
        path    : Path   Absolute destination path.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def log_download(
        self,
        url: str,
        filename: str,
        status: str,
        filesize_kb: float,
    ) -> None:
        """
        Record a download event to the manifest CSV and pipeline log.

        Parameters
        ----------
        url         : str    Source URL
        filename    : str    Local filename (basename only)
        status      : str    "success" | "failed" | "skipped"
        filesize_kb : float  File size in kilobytes
        """
        log_download(
            state=self.STATE,
            category=self.CATEGORY,
            url=url,
            filename=filename,
            status=status,
            filesize_kb=filesize_kb,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_session(self) -> requests.Session:
        """
        Build a requests.Session with automatic retry on transient errors.

        Returns
        -------
        requests.Session
        """
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=BACKOFF_FACTOR,
            status_forcelist=RETRY_STATUS_CODES,
            allowed_methods=["GET", "HEAD"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.headers.update(REQUEST_HEADERS)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _resolve_destination(
        self,
        url: str,
        response: requests.Response,
        destination_path: Path,
    ) -> Path:
        """
        If *destination_path* has no extension, append the detected one.

        Parameters
        ----------
        url              : str
        response         : requests.Response
        destination_path : Path  May or may not already have an extension.

        Returns
        -------
        Path  Final path with extension.
        """
        if destination_path.suffix:
            return destination_path

        ext = self.detect_extension(url, response)
        if ext:
            return destination_path.with_suffix(ext)
        return destination_path
