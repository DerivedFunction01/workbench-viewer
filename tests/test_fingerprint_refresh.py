"""server/common.get_fingerprints, decoupled (B5): the
walks refresh on their own path from the last sweep's
known project roots — no re-discovery, the same cadence
bound, single-flighted — while get_sweep no longer pays
the walks inside its compute lock."""

import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "server"))

import common  # noqa: E402


class FakeProject:
    def __init__(self, slug, root):
        self.slug = slug
        self.root = root


class FakeResult:
    def __init__(self, projects):
        self.projects = projects


class FingerprintRefreshCase(unittest.TestCase):
    TTL = 0.3

    def setUp(self):
        self._orig_sweep = common.sweep_mod.sweep
        self._orig_sweep_cache = dict(common._sweep_cache)
        self._orig_fp_cache = dict(common._fingerprint_cache)
        self._orig_ttl = common.CFG["sweep_ttl_s"]
        common.CFG["sweep_ttl_s"] = self.TTL
        common._sweep_cache.update(at=0.0, result=None)
        common._fingerprint_cache.update(
            map={}, at=0.0, sweep=None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / "alpha"
        todos = root / ".plans" / "b1" / "todos"
        todos.mkdir(parents=True)
        (root / "workbench.yaml").write_text(
            "name: Alpha\nslug: alpha\n", encoding="utf-8")
        self.todo = todos / "01-a.md"
        self.todo.write_text("---\nid: t-1\n---\n",
                             encoding="utf-8")
        self.result = FakeResult(
            [FakeProject("alpha", root)])
        self.sweep_calls = 0

        def fake_sweep(*args, **kwargs):
            self.sweep_calls += 1
            return self.result

        common.sweep_mod.sweep = fake_sweep

    def tearDown(self):
        common.sweep_mod.sweep = self._orig_sweep
        common._sweep_cache.update(self._orig_sweep_cache)
        common._fingerprint_cache.update(self._orig_fp_cache)
        common.CFG["sweep_ttl_s"] = self._orig_ttl

    def test_refresh_without_rediscovery(self):
        first = common.get_fingerprints()
        self.assertEqual(self.sweep_calls, 1)
        # A .plans write lands; discovery stays warm (its
        # cache freshly stamped) while the fingerprint
        # cadence lapses — the refresh must stand on the
        # last sweep's roots alone.
        self.todo.write_text("---\nid: t-1\n---\nchanged\n",
                             encoding="utf-8")
        time.sleep(self.TTL + 0.05)
        common._sweep_cache.update(at=time.monotonic())
        second = common.get_fingerprints()
        self.assertNotEqual(second["alpha"], first["alpha"])
        self.assertEqual(self.sweep_calls, 1)

    def test_within_cadence_serves_cached(self):
        first = common.get_fingerprints()
        self.todo.write_text("---\nid: t-1\n---\nchanged\n",
                             encoding="utf-8")
        # Inside the cadence the cached map serves as-is:
        # the freshness bound is the cadence, as before.
        self.assertEqual(common.get_fingerprints(), first)

    def test_new_sweep_result_recomputes_within_cadence(self):
        first = common.get_fingerprints()
        self.todo.write_text("---\nid: t-1\n---\nchanged\n",
                             encoding="utf-8")
        # A re-discovery (here forced) replaces the roots:
        # fingerprints recompute from the new result even
        # though their own cadence has not lapsed.
        self.result = FakeResult(self.result.projects)
        common.get_sweep(force=True)
        second = common.get_fingerprints()
        self.assertNotEqual(second["alpha"], first["alpha"])

    def test_concurrent_refresh_single_flights(self):
        orig_fp = common.fingerprint_mod.project_fingerprint
        self.addCleanup(
            setattr, common.fingerprint_mod,
            "project_fingerprint", orig_fp)
        walks = 0

        def slow_fp(root):
            nonlocal walks
            walks += 1
            time.sleep(0.05)
            return orig_fp(root)

        common.fingerprint_mod.project_fingerprint = slow_fp
        common.get_sweep()
        results = []

        def hit():
            results.append(common.get_fingerprints())

        threads = [threading.Thread(target=hit)
                   for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(walks, 1)
        self.assertTrue(
            all(r == results[0] for r in results))


if __name__ == "__main__":
    unittest.main()
