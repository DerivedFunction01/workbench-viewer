"""lib/util.fan_out: order preservation, sequential
equivalence, and exception passthrough."""

import time
import unittest

from lib.util import fan_out


class FanOutCase(unittest.TestCase):
    def test_results_in_input_order_under_pool(self):
        # Later items finish first; the result order must
        # still be the input order.
        def fn(i):
            time.sleep(0.02 * (5 - i))
            return i * 10

        self.assertEqual(
            fan_out(fn, range(5), workers=4),
            [0, 10, 20, 30, 40])

    def test_workers_one_matches_sequential_map(self):
        fn = lambda i: i + 1  # noqa: E731
        self.assertEqual(fan_out(fn, [1, 2, 3], workers=1),
                         [2, 3, 4])
        self.assertEqual(fan_out(fn, [1, 2, 3], workers=0),
                         [2, 3, 4])

    def test_empty_and_single_inputs(self):
        self.assertEqual(fan_out(abs, [], workers=8), [])
        self.assertEqual(fan_out(abs, [-2], workers=8), [2])

    def test_exception_propagates_as_sequential_would(self):
        def fn(i):
            if i == 2:
                raise ValueError("boom")
            return i

        with self.assertRaises(ValueError):
            fan_out(fn, range(5), workers=1)
        with self.assertRaises(ValueError):
            fan_out(fn, range(5), workers=4)


if __name__ == "__main__":
    unittest.main()
