"""
Web page extractor.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from app.core.logger import get_logger
from app.knowledge.base import ExtractionError

logger = get_logger(__name__)


class WebExtractor:
    """Fetch a URL and return cleaned text (not a file-based extractor)."""

    def extract_url(self, url: str, timeout: float = 15.0) -> str:
        try:
            import requests  # type: ignore
            from bs4 import BeautifulSoup  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(
                "requests/beautifulsoup4 not installed."
            ) from exc

        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": "EVA/1.0"})
            r.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(f"Failed to fetch {url}: {exc}") from exc

        try:
            soup = BeautifulSoup(r.text, "html.parser")
            # Remove scripts/styles/nav
            for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(f"Failed to parse HTML: {exc}") from exc

        # Collapse blank lines
        lines = [ln.strip() for ln in text.splitlines()]
        return "\n".join(ln for ln in lines if ln)