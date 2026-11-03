"""server/common.get_sweep: concurrent cold requests
share one sweep compute (single-flight)."""

import sys
import threading
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "server"))

import common  # noqa: E402


class SweepSingleFlightCase(unittest.TestCase):
    def setUp(self):
        self._orig_sweep = common.sweep_mod.sweep
        self._orig_cache = dict(common._sweep_cache)
        common._sweep_cache.update(at=0.0, result=None)
        self.calls = 0

        def slow_sweep(*args, **kwargs):
            self.calls += 1
            time.sleep(0.2)
            return {"sentinel": self.calls}

        common.sweep_mod.sweep = slow_sweep

    def tearDown(self):
        common.sweep_mod.sweep = self._orig_sweep
        common._sweep_cache.update(self._orig_cache)

    def test_concurrent_cold_calls_compute_once(self):
        results = []

        def hit():
            results.append(common.get_sweep())

        threads = [threading.Thread(target=hit)
                   for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(self.calls, 1)
        self.assertEqual(len(results), 6)
        self.assertTrue(
            all(r is results[0] for r in results))

    def test_warm_cache_serves_without_compute(self):
        first = common.get_sweep()
        second = common.get_sweep()
        self.assertIs(first, second)
        self.assertEqual(self.calls, 1)


if __name__ == "__main__":
    unittest.main()
