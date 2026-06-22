"""Shared utilities: HTTP fetching with retry, logging setup."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import requests

from src.config import REQUEST_MAX_RETRIES, REQUEST_RETRY_WAIT_SECONDS, REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger with INFO level if not already configured.

    Args:
        name: Logger name, typically ``__name__`` of the calling module.

    Returns:
        Configured :class:`logging.Logger` instance.
    """
    log = logging.getLogger(name)
    if not log.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        log.addHandler(handler)
    log.setLevel(logging.INFO)
    return log


def fetch_text(
    url: str,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
    max_retries: int = REQUEST_MAX_RETRIES,
    retry_wait: int = REQUEST_RETRY_WAIT_SECONDS,
    label: Optional[str] = None,
) -> str:
    """Fetch plain-text content from *url* with retry logic.

    Args:
        url: Target URL.
        timeout: Per-request timeout in seconds.
        max_retries: Maximum number of attempts (including the first).
        retry_wait: Seconds to wait between retries.
        label: Human-readable label used in log messages (defaults to URL).

    Returns:
        Response body as a decoded string.

    Raises:
        RuntimeError: If all attempts fail, with a descriptive message
            suitable for display in the Streamlit UI.
    """
    tag = label or url
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Fetching %s (attempt %d/%d)", tag, attempt, max_retries)
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            logger.info("OK — received %d bytes from %s", len(resp.content), tag)
            return resp.text
        except requests.exceptions.Timeout:
            msg = f"Timeout al conectar con {tag} (intento {attempt}/{max_retries})"
            logger.warning(msg)
        except requests.exceptions.HTTPError as exc:
            msg = f"HTTP {exc.response.status_code} desde {tag} (intento {attempt}/{max_retries})"
            logger.warning(msg)
        except requests.exceptions.ConnectionError:
            msg = f"Error de conexión con {tag} (intento {attempt}/{max_retries})"
            logger.warning(msg)

        if attempt < max_retries:
            logger.info("Esperando %ds antes de reintentar…", retry_wait)
            time.sleep(retry_wait)

    raise RuntimeError(
        f"No se pudo obtener datos de {tag} tras {max_retries} intentos. "
        "Verifique su conexión o que la fuente esté disponible."
    )


def fetch_binary(
    url: str,
    timeout: int = 120,
    max_retries: int = REQUEST_MAX_RETRIES,
    retry_wait: int = REQUEST_RETRY_WAIT_SECONDS,
    label: Optional[str] = None,
) -> bytes:
    """Fetch binary content (e.g. NetCDF) from *url* with retry logic.

    Args:
        url: Target URL.
        timeout: Per-request timeout in seconds (longer default for large files).
        max_retries: Maximum number of attempts.
        retry_wait: Seconds to wait between retries.
        label: Human-readable label for log messages.

    Returns:
        Raw response bytes.

    Raises:
        RuntimeError: If all attempts fail.
    """
    tag = label or url
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Fetching binary %s (attempt %d/%d)", tag, attempt, max_retries)
            resp = requests.get(url, timeout=timeout, stream=True)
            resp.raise_for_status()
            content = resp.content
            logger.info("OK — received %d bytes from %s", len(content), tag)
            return content
        except requests.exceptions.Timeout:
            logger.warning("Timeout al descargar %s (intento %d/%d)", tag, attempt, max_retries)
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "HTTP %d desde %s (intento %d/%d)",
                exc.response.status_code, tag, attempt, max_retries,
            )
        except requests.exceptions.ConnectionError:
            logger.warning("Error de conexión con %s (intento %d/%d)", tag, attempt, max_retries)

        if attempt < max_retries:
            time.sleep(retry_wait)

    raise RuntimeError(
        f"No se pudo descargar {tag} tras {max_retries} intentos."
    )


# ---------------------------------------------------------------------------
# NOAA data freshness check
# ---------------------------------------------------------------------------

# Maps ONI season codes to the last month of that season (used to assign
# a representative calendar month for comparison purposes).
_ONI_SEASON_TO_MONTH: dict[str, int] = {
    "DJF": 2, "JFM": 3, "FMA": 4, "MAM": 5, "AMJ": 6,
    "MJJ": 7, "JJA": 8, "JAS": 9, "ASO": 10, "SON": 11,
    "OND": 12, "NDJ": 1,
}

STALE_THRESHOLD_DAYS: int = 40  # NOAA updates monthly; flag after ~40 days


@dataclass
class FreshnessReport:
    """Result of comparing a local NOAA data file against freshly fetched data.

    Attributes:
        local_file_mtime:   OS modification time of the local file (UTC).
        local_last_period:  Latest (year, month) tuple found in the local file.
        remote_last_period: Latest (year, month) tuple found in the fetched text.
        days_since_write:   Days elapsed since the local file was last written.
        period_delta_months: Months by which the remote leads the local file
                             (0 = same period, positive = remote is ahead).
        is_current:         True when local and remote share the same latest period.
        is_stale_by_age:    True when the file has not been refreshed in
                             more than ``STALE_THRESHOLD_DAYS`` days.
        status:             Human-readable summary ("CURRENT" / "STALE").
        message:            Detailed explanation suitable for Streamlit display.
    """

    local_file_mtime: datetime
    local_last_period: Tuple[int, int]   # (year, month)
    remote_last_period: Tuple[int, int]  # (year, month)
    days_since_write: int
    period_delta_months: int
    is_current: bool
    is_stale_by_age: bool
    status: str
    message: str


def _parse_last_period(text: str) -> Tuple[int, int]:
    """Extract the latest (year, month) from a NOAA CPC ASCII data string.

    Handles two formats emitted by NOAA CPC:

    - **Monthly** (Niño 3.4, SOI monthly block): rows start with integer year
      followed by integer month, e.g.::

          YR   MON  NINO3.4  ANOM
          2025   5   28.32   0.51

    - **Seasonal / ONI**: rows start with a 3-letter season code followed by
      the year, e.g.::

          Season  YR    ANOM
          NDJ  2024  -0.92

    The function scans all data rows, ignores headers, and returns the
    ``(year, month)`` pair from the last valid row found.

    Args:
        text: Raw ASCII content of the NOAA data file or freshly fetched string.

    Returns:
        ``(year, month)`` of the latest data point (month in 1–12).

    Raises:
        ValueError: If no valid data row can be found in *text*.
    """
    last_year: Optional[int] = None
    last_month: Optional[int] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue

        # --- Seasonal / ONI format: "DJF  2025  -0.3 ..." ---
        if parts[0].upper() in _ONI_SEASON_TO_MONTH:
            try:
                year = int(parts[1])
                month = _ONI_SEASON_TO_MONTH[parts[0].upper()]
                last_year, last_month = year, month
                continue
            except (ValueError, IndexError):
                continue

        # --- Monthly format: "2025  5  28.32 ..." ---
        try:
            year = int(parts[0])
            month = int(parts[1])
            if 1950 <= year <= 2100 and 1 <= month <= 12:
                last_year, last_month = year, month
        except (ValueError, IndexError):
            continue

    if last_year is None or last_month is None:
        raise ValueError("No valid data rows found in the provided text.")

    return last_year, last_month


def _period_delta_months(older: Tuple[int, int], newer: Tuple[int, int]) -> int:
    """Return how many months *newer* leads *older* (can be negative)."""
    return (newer[0] - older[0]) * 12 + (newer[1] - older[1])


def check_noaa_data_freshness(
    local_file_path: str | Path,
    fetched_text: str,
    stale_threshold_days: int = STALE_THRESHOLD_DAYS,
) -> FreshnessReport:
    """Compare a local NOAA ENSO data file against freshly fetched text.

    Checks two independent signals:

    1. **Age of the local file** — how many days since it was written to disk.
    2. **Period coverage** — whether the fetched data contains a newer month
       than what the local file holds.

    Both checks are independent: a recently written file can still be behind
    if NOAA published new data between the write and now, and an old file can
    be "current" if the remote source itself has not been updated.

    Args:
        local_file_path: Path to the locally saved NOAA ASCII data file.
        fetched_text:    Raw text returned by the live NOAA endpoint (the same
                         format as the local file).
        stale_threshold_days: Number of days after which the local file is
                              considered stale by age alone (default 40).

    Returns:
        A :class:`FreshnessReport` with all comparison details.

    Raises:
        FileNotFoundError: If *local_file_path* does not exist.
        ValueError: If valid data rows cannot be parsed from either source.

    Example::

        from src.utils import check_noaa_data_freshness, fetch_text
        from src.config import NOAA_ONI_URL

        live_text = fetch_text(NOAA_ONI_URL, label="ONI live")
        report = check_noaa_data_freshness("data/raw/oni.ascii.txt", live_text)

        print(report.status)   # "CURRENT" or "STALE"
        print(report.message)
    """
    path = Path(local_file_path)
    if not path.exists():
        raise FileNotFoundError(f"Local NOAA data file not found: {path}")

    # --- File modification time ---
    mtime_ts = path.stat().st_mtime
    mtime_utc = datetime.fromtimestamp(mtime_ts, tz=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    days_since_write = (now_utc - mtime_utc).days

    # --- Parse latest period from each source ---
    local_text = path.read_text(encoding="utf-8", errors="replace")
    local_period = _parse_last_period(local_text)
    remote_period = _parse_last_period(fetched_text)

    # --- Staleness flags ---
    delta_months = _period_delta_months(local_period, remote_period)
    is_current = delta_months == 0
    is_stale_by_age = days_since_write > stale_threshold_days

    # --- Human-readable status ---
    local_label = f"{local_period[0]}-{local_period[1]:02d}"
    remote_label = f"{remote_period[0]}-{remote_period[1]:02d}"

    if is_current and not is_stale_by_age:
        status = "CURRENT"
        message = (
            f"Data is current. Local file and remote source both end at "
            f"{remote_label}. File written {days_since_write}d ago."
        )
    elif not is_current and delta_months > 0:
        status = "STALE"
        message = (
            f"Remote data is {delta_months} month(s) ahead of local file. "
            f"Local ends at {local_label}, remote ends at {remote_label}. "
            f"File written {days_since_write}d ago — refresh recommended."
        )
    elif not is_current and delta_months < 0:
        # Local file is somehow ahead of the live endpoint (unusual)
        status = "STALE"
        message = (
            f"Local file ({local_label}) is ahead of the live source "
            f"({remote_label}) by {abs(delta_months)} month(s). "
            f"The remote endpoint may be lagging or the local file is corrupt."
        )
    else:
        # Same period but file is old — data not yet updated upstream
        status = "STALE"
        message = (
            f"Local file covers the same period as remote ({remote_label}), "
            f"but was last written {days_since_write}d ago "
            f"(threshold: {stale_threshold_days}d). "
            f"Consider re-fetching to confirm no mid-month corrections were applied."
        )

    logger.info(
        "Freshness check [%s] — local: %s | remote: %s | Δ %+d months | "
        "file age: %dd | status: %s",
        path.name, local_label, remote_label, delta_months, days_since_write, status,
    )

    return FreshnessReport(
        local_file_mtime=mtime_utc,
        local_last_period=local_period,
        remote_last_period=remote_period,
        days_since_write=days_since_write,
        period_delta_months=delta_months,
        is_current=is_current,
        is_stale_by_age=is_stale_by_age,
        status=status,
        message=message,
    )
