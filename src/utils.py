"""Shared utilities: HTTP fetching with retry, logging setup, file-based caching."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Tuple

import requests

from src.config import (
    CACHE_DIR,
    CACHE_TTL_SECONDS,
    RAW_FALLBACK_PATHS,
    REQUEST_MAX_RETRIES,
    REQUEST_MAX_TOTAL_SECONDS,
    REQUEST_RETRY_BACKOFF,
    REQUEST_RETRY_WAIT_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
)

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


# ---------------------------------------------------------------------------
# File-based response cache
# ---------------------------------------------------------------------------

def _cache_key(url: str) -> str:
    """Generate a filesystem-safe cache key from a URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _cache_path(url: str) -> Path:
    """Return the cache file path for a given URL."""
    cache_dir = Path(CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{_cache_key(url)}.cache"


def cache_get(url: str, ttl: int = CACHE_TTL_SECONDS) -> Optional[str]:
    """Return cached response text if fresh, else None."""
    path = _cache_path(url)
    if not path.exists():
        return None
    try:
        meta_path = path.with_suffix(".meta")
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            cached_at = meta.get("cached_at", 0)
        else:
            cached_at = path.stat().st_mtime
        age = time.time() - cached_at
        if age > ttl:
            logger.info("Cache expired for %s (age=%.0fs, ttl=%ds)", url, age, ttl)
            return None
        text = path.read_text(encoding="utf-8")
        logger.info("Cache hit for %s (age=%.0fs)", url, age)
        return text
    except Exception as exc:
        logger.warning("Cache read error for %s: %s", url, exc)
        return None


def cache_put(url: str, text: str) -> None:
    """Store response text in the file cache."""
    try:
        path = _cache_path(url)
        path.write_text(text, encoding="utf-8")
        meta_path = path.with_suffix(".meta")
        meta_path.write_text(
            json.dumps({"url": url, "cached_at": time.time()}),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("Cache write error for %s: %s", url, exc)


def fetch_text(
    url: str,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
    max_retries: int = REQUEST_MAX_RETRIES,
    retry_wait: int = REQUEST_RETRY_WAIT_SECONDS,
    label: Optional[str] = None,
    use_cache: bool = True,
    backoff: float = REQUEST_RETRY_BACKOFF,
    max_total_seconds: int = REQUEST_MAX_TOTAL_SECONDS,
) -> str:
    """Fetch plain-text content from *url* with retry logic.

    Retries use a geometric backoff (``retry_wait`` seconds before the first
    retry, multiplied by ``backoff`` after each further failure), so a source
    that is briefly overloaded gets progressively more breathing room.  The
    whole sequence — requests and waits together — is capped at
    ``max_total_seconds``: attempts stop early rather than exceed the budget,
    so one unreachable endpoint cannot stall the build.

    Args:
        url: Target URL.
        timeout: Per-request timeout in seconds.
        max_retries: Maximum number of attempts (including the first).
        retry_wait: Seconds to wait before the first retry.
        label: Human-readable label used in log messages (defaults to URL).
        use_cache: Read from and write to the short-lived HTTP response cache.
        backoff: Multiplier applied to the wait after each failed attempt.
        max_total_seconds: Ceiling on the total time spent on this URL.

    Returns:
        Response body as a decoded string.

    Raises:
        RuntimeError: If all attempts fail, with a descriptive message
            suitable for display in the Streamlit UI.
    """
    tag = label or url

    # Check cache first
    if use_cache:
        cached = cache_get(url)
        if cached is not None:
            return cached

    started = time.monotonic()
    wait = float(retry_wait)
    attempts_made = 0

    for attempt in range(1, max_retries + 1):
        remaining = max_total_seconds - (time.monotonic() - started)
        if attempt > 1 and remaining <= 0:
            logger.warning(
                "Presupuesto de %ds agotado para %s tras %d intento(s)",
                max_total_seconds, tag, attempts_made,
            )
            break

        # Never let a single request run past the remaining budget.
        attempt_timeout = timeout if attempt == 1 else max(1, min(timeout, int(remaining)))
        attempts_made = attempt
        try:
            logger.info("Fetching %s (attempt %d/%d)", tag, attempt, max_retries)
            resp = requests.get(url, timeout=attempt_timeout, allow_redirects=True)
            resp.raise_for_status()
            logger.info("OK — received %d bytes from %s", len(resp.content), tag)
            text = resp.text
            if use_cache:
                cache_put(url, text)
            return text
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
            remaining = max_total_seconds - (time.monotonic() - started)
            if remaining <= 0:
                logger.warning(
                    "Presupuesto de %ds agotado para %s — no se reintenta",
                    max_total_seconds, tag,
                )
                break
            sleep_for = min(wait, remaining)
            logger.info("Esperando %.0fs antes de reintentar…", sleep_for)
            time.sleep(sleep_for)
            wait *= backoff

    raise RuntimeError(
        f"No se pudo obtener datos de {tag} tras {attempts_made} intentos. "
        "Verifique su conexión o que la fuente esté disponible."
    )


# ---------------------------------------------------------------------------
# Versioned offline copies (data/raw/) used when a live fetch fails
# ---------------------------------------------------------------------------


@dataclass
class SourceText:
    """Raw text for one index together with where it actually came from.

    Attributes:
        text:       The raw ASCII payload.
        status:     ``"live"`` when NOAA answered, ``"cached"`` when the
                    versioned copy in ``data/raw/`` was read instead.
        path:       Repo-relative path of the local copy used, else None.
        as_of:      ISO date of the copy's contents, else None.  See
                    ``as_of_source`` for how it was determined.
        as_of_source: ``"commit"`` when ``as_of`` is the date of the last
                    commit that touched the file — the reliable answer — or
                    ``"mtime"`` when git could not date it and the filesystem
                    timestamp had to be used.  A CI checkout rewrites mtimes
                    to the build time, so an ``"mtime"`` date says little
                    about how old the data really is.
        live_error: The live-fetch error that forced the fallback, else None.
    """

    text: str
    status: str
    path: Optional[str] = None
    as_of: Optional[str] = None
    as_of_source: Optional[str] = None
    live_error: Optional[str] = None

    @property
    def is_cached(self) -> bool:
        """True when this text came from the versioned offline copy."""
        return self.status == "cached"


def _git_commit_date(path: Path) -> Optional[str]:
    """Return the ISO date of the last commit that touched *path*, else None.

    This is the only trustworthy age for a versioned file: a CI checkout
    rewrites every mtime to the time of the build, so the filesystem
    timestamp of ``data/raw/oni.ascii.txt`` always reads as "today" there,
    however old the data inside it is.

    Returns None when git is not installed, when the history does not reach
    the last commit for that path (a shallow clone), or when the file is not
    tracked.

    Args:
        path: Absolute path to the file.

    Returns:
        ``"YYYY-MM-DD"``, or None when git cannot answer.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(path.parent), "log", "-1", "--format=%cs", "--", str(path)],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("git no disponible para fechar %s: %s", path.name, exc)
        return None

    if proc.returncode != 0:
        logger.warning(
            "git log falló para %s (código %d): %s",
            path.name, proc.returncode, (proc.stderr or "").strip()[:200],
        )
        return None

    date = (proc.stdout or "").strip()
    if len(date) != 10 or date.count("-") != 2:
        logger.warning(
            "git log no devolvió una fecha para %s "
            "(¿clon superficial o archivo sin seguimiento?)", path.name,
        )
        return None
    return date


def file_as_of(path: Path) -> tuple[str, str]:
    """Date the contents of *path*, and say how that date was obtained.

    Args:
        path: Absolute path to the file.

    Returns:
        ``(iso_date, source)`` where *source* is ``"commit"`` or ``"mtime"``.
    """
    commit_date = _git_commit_date(path)
    if commit_date:
        return commit_date, "commit"
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date().isoformat()
    return mtime, "mtime"


def read_raw_fallback(url: str, label: Optional[str] = None) -> SourceText:
    """Read the versioned offline copy registered for *url*.

    Args:
        url: The live endpoint whose offline copy is wanted.
        label: Human-readable label used in messages.

    Returns:
        A :class:`SourceText` with ``status="cached"``.

    Raises:
        RuntimeError: If no offline copy is registered for *url*, if the file
            is missing, or if it is empty.  The message names the expected
            path, so the failure is actionable instead of silent.
    """
    tag = label or url
    rel = RAW_FALLBACK_PATHS.get(url)
    if rel is None:
        raise RuntimeError(
            f"{tag}: la descarga en vivo falló y no hay copia versionada "
            f"registrada para {url}."
        )

    path = Path(rel)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / rel

    if not path.exists():
        raise RuntimeError(
            f"{tag}: la descarga en vivo falló y la copia versionada no "
            f"existe ({rel}). Ejecute el workflow «Refresh NOAA ENSO "
            f"Data» para regenerarla."
        )

    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        raise RuntimeError(
            f"{tag}: la copia versionada {rel} está vacía; no se "
            f"publica nada con ella."
        )

    as_of, as_of_source = file_as_of(path)
    if as_of_source == "commit":
        logger.warning(
            "%s: usando la copia versionada %s (último commit %s) — la "
            "descarga en vivo falló.", tag, rel, as_of,
        )
    else:
        logger.warning(
            "%s: usando la copia versionada %s (mtime %s; git no pudo fechar el "
            "archivo, así que esa fecha puede ser la del checkout y no la de "
            "los datos) — la descarga en vivo falló.", tag, rel, as_of,
        )
    return SourceText(
        text=text, status="cached", path=rel, as_of=as_of, as_of_source=as_of_source
    )


def fetch_text_or_cached(
    url: str,
    label: Optional[str] = None,
    **kwargs,
) -> SourceText:
    """Fetch *url*; on failure fall back to its versioned copy in ``data/raw/``.

    The fallback is strictly per-URL: a cached file may only ever stand in for
    its own index.  Nothing is invented and nothing is substituted silently —
    the returned :class:`SourceText` records which copy was used and when it
    was written, so callers can publish that provenance.

    Args:
        url: Target URL.
        label: Human-readable label used in log messages.
        **kwargs: Forwarded to :func:`fetch_text`.

    Returns:
        A :class:`SourceText` with ``status`` ``"live"`` or ``"cached"``.

    Raises:
        RuntimeError: If the live fetch fails *and* no usable offline copy
            exists.  The message names both the endpoint and the expected path.
    """
    tag = label or url
    try:
        return SourceText(text=fetch_text(url, label=label, **kwargs), status="live")
    except RuntimeError as exc:
        logger.warning(
            "%s: descarga en vivo fallida (%s) — probando la copia local", tag, exc
        )
        fallback = read_raw_fallback(url, label=label)
        fallback.live_error = str(exc)
        return fallback


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

    It does **not** understand every CPC layout.  The SOI file, for one, puts
    twelve monthly values on each year's row and runs the year into the first
    value when that value is wide (``2030-999.9-999.9...``), which no rule
    here matches.  Rather than grow a second SOI parser next to
    :func:`src.fetch_enso.parse_soi`, callers pass their own
    ``period_parser`` to :func:`check_noaa_data_freshness`.

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
    period_parser: Optional[Callable[[str], Tuple[int, int]]] = None,
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
        period_parser: Callable returning the latest ``(year, month)`` of a
                       raw payload.  Defaults to :func:`_parse_last_period`.
                       Pass the index's own parser for formats that one does
                       not read — the SOI file, for instance.

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
    parse_period = period_parser or _parse_last_period
    local_text = path.read_text(encoding="utf-8", errors="replace")
    local_period = parse_period(local_text)
    remote_period = parse_period(fetched_text)

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
