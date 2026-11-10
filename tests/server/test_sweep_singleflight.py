"""server/common.get_sweep: concurrent cold requests
share one sweep compute (single-flight), and past the
TTL a request serves the stale result while one
background thread recomputes (stale-while-recompute)."""

import sys
import threading
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "server"))

import common  # noqa: E402


class SweepSingleFlightCase(unittest.TestCase):
    def setUp(self):
        self._orig_sweep = common.sweep_mod.sweep
        self._orig_cache = dict(common._sweep_cache)
        self._orig_ttl = common.CFG["sweep_ttl_s"]
        common.CFG["sweep_ttl_s"] = 0.05
        common._sweep_cache.update(at=0.0, result=None)
        self.calls = 0

        def slow_sweep(*args, **kwargs):
            self.calls += 1
            time.sleep(0.2)
            return {"sentinel": self.calls}

        common.sweep_mod.sweep = slow_sweep

    def tearDown(self):
        common.sweep_mod.sweep = self._orig_sweep
        common.CFG["sweep_ttl_s"] = self._orig_ttl
        common._sweep_cache.update(self._orig_cache)
        # A kicked background refresh may still be in
        # flight; wait it out so it cannot leak a store
        # into a later test.
        deadline = time.monotonic() + 5
        while common._sweep_refreshing \
                and time.monotonic() < deadline:
            time.sleep(0.02)

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

    def test_stale_result_serves_while_recompute_runs(self):
        first = common.get_sweep()
        time.sleep(0.1)  # past the (shortened) TTL
        t0 = time.monotonic()
        served = common.get_sweep()
        # Served immediately from the stale cache, not
        # after the 0.2 s recompute the old inline shape
        # would have made this caller wait through.
        self.assertLess(time.monotonic() - t0, 0.15)
        self.assertIs(served, first)
        # The kicked background recompute lands the fresh
        # result in the cache.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if common._sweep_cache["result"] is not first:
                break
            time.sleep(0.02)
        self.assertIsNot(common._sweep_cache["result"],
                         first)
        self.assertEqual(self.calls, 2)
        # And the fresh result is what now serves.
        self.assertIs(common.get_sweep(),
                      common._sweep_cache["result"])

    def test_recompute_failure_keeps_stale_and_retries(self):
        first = common.get_sweep()
        time.sleep(0.1)  # past the (shortened) TTL

        def boom(*args, **kwargs):
            self.calls += 1
            raise RuntimeError("stall")

        common.sweep_mod.sweep = boom
        served = common.get_sweep()
        self.assertIs(served, first)
        deadline = time.monotonic() + 5
        while common._sweep_refreshing \
                and time.monotonic() < deadline:
            time.sleep(0.02)
        # The failure did not poison the cache: the stale
        # result is still what serves, and the next stale
        # read kicks another refresh (it does not wedge
        # the refreshing flag).
        self.assertIs(common._sweep_cache["result"],
                      first)
        self.assertFalse(common._sweep_refreshing)
        self.assertIs(common.get_sweep(), first)


if __name__ == "__main__":
    unittest.main()
