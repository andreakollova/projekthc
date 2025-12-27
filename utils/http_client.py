from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class HttpResult:
    url: str
    status_code: int
    text: str | None
    headers: dict


class RequestLimitExceeded(Exception):
    pass


class HttpClient:
    def __init__(
        self,
        user_agent: str,
        timeout: float,
        min_sleep: float,
        max_sleep: float,
        max_retries: int,
        backoff_base: float,
        backoff_jitter_min: float,
        backoff_jitter_max: float,
        max_requests_per_run: int,
        storage_http_meta,
        logger,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Language": "sk,en;q=0.8",
            }
        )
        self.timeout = timeout
        self.min_sleep = min_sleep
        self.max_sleep = max_sleep
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_jitter_min = backoff_jitter_min
        self.backoff_jitter_max = backoff_jitter_max
        self.max_requests_per_run = max_requests_per_run
        self.storage_http_meta = storage_http_meta
        self.log = logger
        self._request_count = 0

    @property
    def request_count(self) -> int:
        return self._request_count

    def _sleep_human(self, extra_min: float = 0.0, extra_max: float = 0.0) -> None:
        lo = self.min_sleep + extra_min
        hi = self.max_sleep + extra_max
        delay = random.uniform(lo, hi)
        time.sleep(delay)

    def get(
        self,
        url: str,
        *,
        extra_sleep: bool = False,
        allow_redirects: bool = True,
        extra_headers: dict | None = None,
        conditional: bool = True,
    ) -> HttpResult:
        """
        - extra_headers: doplnkové headers (napr. Referer, X-Requested-With)
        - conditional: ak False, neposiela If-None-Match / If-Modified-Since (teda nevyrobíš 304 s prázdnym body)
        """
        if self._request_count >= self.max_requests_per_run:
            raise RequestLimitExceeded(f"Hard limit requestov prekročený: {self.max_requests_per_run}")

        headers: dict[str, str] = {}

        # conditional headers (etag/last-modified)
        if conditional:
            meta = self.storage_http_meta.get_meta(url)
            if meta:
                if meta.get("etag"):
                    headers["If-None-Match"] = meta["etag"]
                if meta.get("last_modified"):
                    headers["If-Modified-Since"] = meta["last_modified"]
        else:
            # “force fresh” – aby server nevracal 304 bez body
            headers["Cache-Control"] = "no-cache"
            headers["Pragma"] = "no-cache"

        # merge extra headers
        if extra_headers:
            headers.update(extra_headers)

        attempt = 0
        while True:
            attempt += 1
            self._request_count += 1

            if extra_sleep:
                self._sleep_human(extra_min=2.0, extra_max=6.0)
            else:
                self._sleep_human()

            try:
                resp = self.session.get(url, headers=headers, timeout=self.timeout, allow_redirects=allow_redirects)
                status = resp.status_code

                # 304 – unchanged
                if status == 304:
                    self.log.info(f"304 Not Modified – preskakujem: {url}")
                    return HttpResult(url=url, status_code=status, text=None, headers=dict(resp.headers))

                # retry statuses
                if status in (429, 503, 502, 504):
                    if attempt <= self.max_retries:
                        self._backoff(attempt, status, url)
                        continue

                resp.raise_for_status()

                # store meta only when conditional flow is on (má zmysel caching)
                if conditional:
                    self.storage_http_meta.upsert_meta(
                        url=url,
                        etag=resp.headers.get("ETag"),
                        last_modified=resp.headers.get("Last-Modified"),
                    )

                return HttpResult(url=url, status_code=status, text=resp.text, headers=dict(resp.headers))

            except requests.RequestException as e:
                if attempt <= self.max_retries:
                    self._backoff(attempt, None, url, exc=e)
                    continue
                raise

    def _backoff(self, attempt: int, status: Optional[int], url: str, exc: Exception | None = None) -> None:
        base = self.backoff_base ** (attempt - 1)
        jitter = random.uniform(self.backoff_jitter_min, self.backoff_jitter_max)
        delay = base + jitter
        if status:
            self.log.warning(f"Retry {attempt}/{self.max_retries} po statuse {status} – sleep {delay:.2f}s – {url}")
        else:
            self.log.warning(f"Retry {attempt}/{self.max_retries} po chybe {exc} – sleep {delay:.2f}s – {url}")
        time.sleep(delay)
