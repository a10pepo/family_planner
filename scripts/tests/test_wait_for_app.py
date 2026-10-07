import http.client
import importlib.util
import urllib.error
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "wait_for_app", Path(__file__).resolve().parents[1] / "wait_for_app.py"
)
waiter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(waiter)


class Clock:
    def __init__(self):
        self.seconds = 0

    def now(self):
        return self.seconds

    def sleep(self, seconds):
        self.seconds += seconds


@pytest.mark.parametrize(
    "failure",
    [
        ConnectionResetError(),
        TimeoutError(),
        urllib.error.URLError("startup"),
        http.client.RemoteDisconnected(),
        http.client.BadStatusLine("startup"),
    ],
)
def test_retries_transient_failure_until_both_services_answer(failure):
    clock = Clock()
    calls = []

    def open_url(url, timeout):
        calls.append(url)
        assert timeout == 3
        if len(calls) == 2:
            raise failure
        return nullcontext(SimpleNamespace(status=200))

    assert waiter.wait_for_app(6, open_url=open_url, now=clock.now, sleep=clock.sleep)
    assert calls == list(waiter.URLS) * 2
    assert clock.seconds == 2


def test_fails_at_deadline_when_identity_never_becomes_ready():
    clock = Clock()
    calls = []

    def open_url(url, timeout):
        calls.append(url)
        return nullcontext(SimpleNamespace(status=200 if url == waiter.URLS[0] else 503))

    assert not waiter.wait_for_app(6, open_url=open_url, now=clock.now, sleep=clock.sleep)
    assert calls == list(waiter.URLS) * 3
    assert clock.seconds == 6
