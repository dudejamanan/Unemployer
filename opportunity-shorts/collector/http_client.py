from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class FetchError(Exception):
    """Raised when a source can't be fetched (bad board token, blocked, network down...)."""


class HttpClient:
    """Polite HTTP client: identifies itself, retries on 429/5xx, spaces requests per host."""

    def __init__(self, user_agent: str, timeout: int = 25, min_delay: float = 0.7, retries: int = 3):
        self.timeout = timeout
        self.min_delay = min_delay
        self._last: dict[str, float] = {}
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept": "application/json, */*;q=0.8"})
        retry = Retry(total=retries, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504],
                      allowed_methods=["GET"], respect_retry_after_header=True)
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _wait(self, url: str) -> None:
        host = urlparse(url).netloc
        gap = time.monotonic() - self._last.get(host, 0.0)
        if gap < self.min_delay:
            time.sleep(self.min_delay - gap)
        self._last[host] = time.monotonic()

    def _get(self, url: str, params=None, headers=None) -> requests.Response:
        self._wait(url)
        try:
            r = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
        except requests.RequestException as e:
            raise FetchError(f"{url}: {e}") from e
        if r.status_code != 200:
            raise FetchError(f"{url}: HTTP {r.status_code}")
        return r

    def get_json(self, url: str, params=None, headers=None) -> Any:
        r = self._get(url, params, headers)
        try:
            return r.json()
        except ValueError as e:
            raise FetchError(f"{url}: response was not JSON") from e

    def get_text(self, url: str, params=None, headers=None) -> str:
        return self._get(url, params, headers).text
