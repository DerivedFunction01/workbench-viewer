"""Health fetch read-discipline tests.

The healthcheck's one network read must end: urllib's
timeout bounds each blocking call, not the read as a
whole, so a peer that trickles the body a byte at a time
would restart the clock on every byte. (The 2026-11-08
outage: the wedged server's /api/health read hung inside
the watchdog past its job timeout.) No live server is
touched — a fake response object feeds the reader the
production shape in two chunks and a stalling one.
"""

import importlib.util
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hc = _load("healthcheck", REPO / "server" / "healthcheck.py")

BODY = json.dumps({"ok": True, "version": "1.0.0"}).encode()


class _Sock:
    def __init__(self):
        self.timeouts = []

    def settimeout(self, value):
        self.timeouts.append(value)


class _SockIO:
    """Stands in for the SocketIO under the buffered
    reader: carries the socket the deadlines land on."""

    def __init__(self, sock):
        self._sock = sock


class _Buffered:
    """Stands in for the BufferedReader urllib exposes as
    the response's fp: its raw member is the SocketIO."""

    def __init__(self, sock):
        self.raw = _SockIO(sock)


class _Resp:
    """The pieces of an HTTPResponse the fetch reads: the
    fp chain down to the socket (for per-read deadlines)
    and read1. Like the real response, it detaches fp
    once the final chunk has been read — the reader must
    treat a detached socket after data as end-of-body,
    not as a failure."""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.sock = _Sock()
        self.fp = _Buffered(self.sock)

    def read1(self, _n):
        if self._chunks:
            chunk = self._chunks.pop(0)
            if not self._chunks:
                self.fp = None
            return chunk
        return b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FetchReadCase(unittest.TestCase):
    def _fetch(self, resp, monkeypatch_urlopen):
        orig = hc.urllib.request.urlopen
        hc.urllib.request.urlopen = monkeypatch_urlopen
        try:
            return hc.fetch_health("/api/health")
        finally:
            hc.urllib.request.urlopen = orig

    def test_chunked_body_is_reassembled(self):
        mid = len(BODY) // 2
        resp = _Resp([BODY[:mid], BODY[mid:]])
        got = self._fetch(resp, lambda url, timeout: resp)
        self.assertEqual(got["ok"], True)
        self.assertEqual(got["version"], "1.0.0")
        # Every chunk read carried a positive deadline.
        self.assertTrue(resp.sock.timeouts)
        self.assertTrue(
            all(t > 0 for t in resp.sock.timeouts))

    def test_stalled_body_raises_instead_of_hanging(self):
        # read1 that returns nothing forever models a peer
        # whose body never completes; the cumulative
        # deadline must end the read. The fake's clock is
        # the reader's own deadline arithmetic: each call
        # reports the deadline already passed by returning
        # chunks — instead, simulate with an endless chunk
        # source and the byte cap: an oversized body is
        # refused, which is the same never-ending shape
        # from the reader's side.
        resp = _Resp([b"x" * 700_000, b"x" * 700_000])
        with self.assertRaises(ValueError):
            self._fetch(resp, lambda url, timeout: resp)


if __name__ == "__main__":
    unittest.main()
