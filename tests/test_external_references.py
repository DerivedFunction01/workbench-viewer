"""Guard for the portability rule (AGENTS.md): tracked files
never contain the owner's name, another repo's name, or paths
outside this repo, so a fresh clone works anywhere.

Walks every tracked file (`git ls-files`), reads it as UTF-8
(binary files that do not decode are skipped), and asserts
none of the forbidden strings appear.

The forbidden strings are assembled by concatenation on
purpose: this file is itself a tracked file scanned by its
own test, so none of them may appear here literally.
"""

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN = [
    "Den" + "ny",  # the owner's name, capitalized
    "den" + "ny",  # the owner's name, lowercase (the old author handle)
    "usmc-pay-" + "monitor",  # the other project repo (either version form)
    "edg" + "ar-sec",  # the excluded repo
    "/ho" + "me/",  # absolute home paths
    "~/" + "workspace",  # home-relative workspace paths
    "$HO" + "ME/workspace",  # env-form workspace paths
    "/op" + "t/",  # host tool paths
    "workbench-viewer-" + "2",  # the published artifact's slug
    "Derived" + "Function01",  # the owner's hosting username
]


class TestExternalReferences(unittest.TestCase):
    def test_no_forbidden_strings_in_tracked_files(self):
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
        names = [n for n in out.decode("utf-8").split("\0") if n]
        self.assertTrue(names, "git ls-files returned nothing")
        offenders = []
        for name in names:
            try:
                text = (ROOT / name).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for pattern in FORBIDDEN:
                if pattern in text:
                    offenders.append(f"{name} contains a forbidden string")
        self.assertEqual(offenders, [], "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
