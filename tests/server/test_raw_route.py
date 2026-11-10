"""Raw byte-route tests (byte-route plan, Step 1): the
server answers GET /raw/<slug>/entries/<id>/<path...> with
the file's bytes verbatim under its own content type — the
one non-JSON route — with plain-text errors under the §7
status conventions."""

import urllib.error
import urllib.request

from tests.server.test_server import ServerCase


class TestRawRoute(ServerCase):
    def req_bytes(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request,
                                        timeout=10) as r:
                return (r.status, r.headers.get_content_type(),
                        r.headers.get("Cache-Control"),
                        r.read())
        except urllib.error.HTTPError as e:
            return (e.code, e.headers.get_content_type(),
                    e.headers.get("Cache-Control"), e.read())

    def test_entry_page_serves_verbatim(self):
        status, ctype, cache, body = self.req_bytes(
            "/raw/alpha/entries/tile-a/mock.html")
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "text/html")
        self.assertEqual(cache, "no-store")
        self.assertIn(b"A</h1>", body)
        self.assertIn(b"--ink:#111", body)

    def test_unknown_project_404_plain_text(self):
        status, ctype, _cache, body = self.req_bytes(
            "/raw/nope/entries/tile-a/mock.html")
        self.assertEqual(status, 404)
        self.assertEqual(ctype, "text/plain")
        self.assertIn(b"no such project", body)

    def test_unknown_entry_404(self):
        status, _ct, _cc, _body = self.req_bytes(
            "/raw/alpha/entries/nope/mock.html")
        self.assertEqual(status, 404)

    def test_missing_file_404(self):
        status, _ct, _cc, _body = self.req_bytes(
            "/raw/alpha/entries/tile-a/nope.html")
        self.assertEqual(status, 404)

    def test_escape_refused_400(self):
        status, _ct, _cc, _body = self.req_bytes(
            "/raw/alpha/entries/tile-a/..%2Fregistry.db")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    import unittest
    unittest.main()
