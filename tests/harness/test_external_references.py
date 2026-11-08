"""Guard for the portability rule (AGENTS.md): tracked files
never contain a personal name, another repo's name, or paths
outside this repo, so a fresh clone works anywhere.

Walks every tracked file (`git ls-files`), reads it as UTF-8
(binary files that do not decode are skipped), and asserts
none of the forbidden strings appear.

Two pattern sources:

- GENERIC shapes (below): path forms that are never portable.
  They are assembled by concatenation on purpose: this file
  is itself a tracked file scanned by its own test, so none
  of them may appear here literally. The shapes are generic —
  they name no person, project, or machine.
- PERSONAL literals (a personal name, a hosting username,
  sibling project names, the published artifact's slug) live
  ONLY in an untracked denylist: `state/denylist.txt` in this
  checkout, or the file the WB_DENYLIST_FILE env var names.
  Matching is case-insensitive. A split construction is still
  a leak — anyone reading the code learns the literal — so no
  personal literal, whole or fragmented, belongs in a tracked
  file. When no denylist is provisioned (a fresh clone
  elsewhere), the personal leg is inert and the generic leg
  still runs: the clone stays green, and on any machine where
  the denylist exists the gate enforces it.

One boundary: `viewer/vendor/` is pinned, unmodified
third-party code — the same carve-out as node_modules and
dist — so its files are excluded from the scan. Vendored
bytes are never patched to satisfy this guard; the exclusion
is the entire accommodation.

Offender messages never echo the matched string: a finding
names the file and which leg caught it, nothing more.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

GENERIC = [
    "/ho" + "me/",  # absolute home paths
    "~/" + "workspace",  # home-relative workspace paths
    "$HO" + "ME/workspace",  # env-form workspace paths
    "/op" + "t/",  # host tool paths
]

DENYLIST_ENV = "WB_DENYLIST_FILE"
DENYLIST_DEFAULT = ROOT / "state" / "denylist.txt"


def load_denylist(path=None):
    """Personal literals from the untracked denylist, or an
    empty list when none is provisioned. One literal per
    line; blank lines and #-comments are ignored."""
    if path is None:
        env = os.environ.get(DENYLIST_ENV)
        path = Path(env) if env else DENYLIST_DEFAULT
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def scan(texts, generic, personal):
    """Offender labels for a {name: text} mapping. Generic
    patterns match literally; personal literals match
    case-insensitively. Neither match is echoed."""
    offenders = []
    lowered_personal = [p.lower() for p in personal]
    for name, text in texts.items():
        for pattern in generic:
            if pattern in text:
                offenders.append(
                    f"{name} contains a forbidden string")
        if lowered_personal:
            lowered = text.lower()
            for _ in lowered_personal:
                if _ in lowered:
                    offenders.append(
                        f"{name} contains a denylisted string")
                    break
    return offenders


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
        texts = {}
        for name in names:
            if name.startswith("viewer/vendor/"):
                continue  # pinned third-party code; see docstring
            try:
                texts[name] = (ROOT / name).read_text(
                    encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
        offenders = scan(texts, GENERIC, load_denylist())
        self.assertEqual(offenders, [], "\n".join(offenders))


class TestDenylistMechanism(unittest.TestCase):
    # Synthetic stand-ins only: the mechanism is tested
    # without any real personal literal in a tracked file.
    FAKE = "quux-zzq-9"

    def test_load_denylist_parses_lines(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "denylist.txt"
            path.write_text(
                "# a comment\n\n  quux-zzq-9  \nfoo-bar\n",
                encoding="utf-8")
            self.assertEqual(load_denylist(path),
                             ["quux-zzq-9", "foo-bar"])

    def test_load_denylist_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                load_denylist(Path(td) / "absent.txt"), [])

    def test_scan_flags_personal_case_insensitively(self):
        texts = {"a.txt": "has QUUX-ZZQ-9 inside"}
        self.assertEqual(
            scan(texts, [], [self.FAKE]),
            ["a.txt contains a denylisted string"])

    def test_scan_inert_without_denylist(self):
        texts = {"a.txt": "has quux-zzq-9 inside"}
        self.assertEqual(scan(texts, [], []), [])

    def test_scan_flags_generic_shapes(self):
        texts = {"a.txt": "path " + "/ho" + "me/x" + " here"}
        self.assertEqual(
            scan(texts, GENERIC, []),
            ["a.txt contains a forbidden string"])


if __name__ == "__main__":
    unittest.main()
