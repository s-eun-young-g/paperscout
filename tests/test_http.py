"""Tests for the HTTP client's transient-error retry/backoff (no network)."""

import dataclasses

import httpx
import pytest

from paperscout.config import settings
from paperscout.http import Client


class _Resp:
    def __init__(self, status_code, text='{"ok": true}'):
        self.status_code = status_code
        self.text = text

    def json(self):
        import json
        return json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


class _FakeHttp:
    """Returns a scripted sequence of responses / exceptions, one per request()."""
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def request(self, method, url, **kw):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _client(script):
    # zero backoff so the test does not actually sleep
    fast = dataclasses.replace(settings, retry_backoff=0.0, min_request_interval=0.0, max_retries=4)
    c = Client.__new__(Client)
    c.settings = fast
    c._last = 0.0
    c._http = _FakeHttp(script)
    return c


def test_retries_then_succeeds_on_503():
    c = _client([_Resp(503), _Resp(503), _Resp(200)])
    resp = c._send("GET", "http://x")
    assert resp.status_code == 200
    assert c._http.calls == 3          # two retries then success


def test_retries_transport_error_then_succeeds():
    c = _client([httpx.ConnectError("boom"), _Resp(200)])
    resp = c._send("GET", "http://x")
    assert resp.status_code == 200
    assert c._http.calls == 2


def test_gives_up_after_max_retries_returns_last_5xx():
    # all attempts 503: returns the final response (raise_for_status happens in caller)
    c = _client([_Resp(503)] * 5)
    resp = c._send("GET", "http://x")
    assert resp.status_code == 503
    assert c._http.calls == 5          # 1 + max_retries(4)
