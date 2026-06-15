"""Polite, cached HTTP client shared by all sources.

A descriptive User-Agent, a minimum interval between live requests, and a SQLite
cache so reruns stay offline. Supports GET (with params) and POST (JSON).
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

import httpx

from .cache import Cache
from .config import Settings


class Client:
    def __init__(self, settings: Settings, cache: Cache):
        self.settings = settings
        self.cache = cache
        self._last = 0.0
        self._http = httpx.Client(
            headers={"User-Agent": settings.user_agent},
            timeout=settings.request_timeout,
            follow_redirects=True,
        )

    def _throttle(self) -> None:
        wait = self.settings.min_request_interval - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)

    def _cache_window(self, refresh: bool, offline: bool) -> Optional[float]:
        if offline:
            return None  # any age
        return self.settings.cache_ttl_hours * 3600

    def get_json(self, url: str, params: Optional[dict] = None, *,
                 refresh: bool = False, offline: bool = False) -> Any:
        key = "GET " + url + "?" + json.dumps(params or {}, sort_keys=True)
        if not refresh:
            cached = self.cache.get(key, self._cache_window(refresh, offline))
            if cached is not None:
                return json.loads(cached)
        if offline:
            raise RuntimeError(f"No cached copy for {key} and offline mode is on.")
        self._throttle()
        resp = self._http.get(url, params=params)
        self._last = time.time()
        resp.raise_for_status()
        self.cache.put(key, resp.text)
        return resp.json()

    def post_json(self, url: str, payload: dict, *,
                  refresh: bool = False, offline: bool = False) -> Any:
        key = "POST " + url + " " + json.dumps(payload, sort_keys=True)
        if not refresh:
            cached = self.cache.get(key, self._cache_window(refresh, offline))
            if cached is not None:
                return json.loads(cached)
        if offline:
            raise RuntimeError(f"No cached copy for {key} and offline mode is on.")
        self._throttle()
        resp = self._http.post(url, json=payload)
        self._last = time.time()
        resp.raise_for_status()
        self.cache.put(key, resp.text)
        return resp.json()

    def close(self) -> None:
        self._http.close()
