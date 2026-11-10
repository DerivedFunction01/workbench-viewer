"""server.main startup ordering (wedge fix, 2026-11-10):
the HTTP bind precedes every warm-up. A storage stall
during warm-up must not park the process before it ever
answers — the 2026-11-10 restart churn was exactly that:
fresh instances parked in D state inside main()'s
synchronous sweep warm and never reached the bind."""

import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "server"))

import server  # noqa: E402


class StartupOrderCase(unittest.TestCase):
    def test_bind_precedes_warm_and_watchdog_starts(self):
        events = []

        class FakeHTTPServer:
            def __init__(self, address, handler):
                events.append("bind")

            def serve_forever(self):
                events.append("serve")

        warmed = threading.Event()

        def warm():
            events.append("warm")
            warmed.set()

        with mock.patch.object(
                server, "acquire_lock",
                lambda: events.append("lock")), \
            mock.patch.object(
                server.stackdump, "start_stackdump",
                lambda *a, **kw: events.append(
                    "stackdump")), \
            mock.patch.object(
                server, "start_message_maintenance",
                lambda: events.append("maintenance")), \
            mock.patch.object(
                server, "_warm_feeds", warm), \
            mock.patch.object(
                server, "ThreadingHTTPServer",
                FakeHTTPServer):
            rc = server.main()
        self.assertEqual(rc, 0)
        # The warm runs on a daemon thread; wait for it
        # before judging the order.
        self.assertTrue(warmed.wait(timeout=5))
        self.assertEqual(events[0], "lock")
        self.assertLess(events.index("bind"),
                        events.index("warm"))
        self.assertLess(events.index("stackdump"),
                        events.index("serve"))


if __name__ == "__main__":
    unittest.main()
