"""Shared utilities: HTTP fetching with retry, logging setup."""

from __future__ import annotations

import logging
import time
from typing import Optional

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
