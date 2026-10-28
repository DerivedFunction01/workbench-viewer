"""Absorption plan Steps 4 + 6: repo-scope peek and guarded
save (lib/files repo_peek / repo_save) over a real git
fixture — the git repo viewer's semantics re-derived in
house idioms. Covers the withhold/reveal pair, the caps,
escape refusal, the sha conflict, the secret-confirm gate,
and the backup + audit landing of a good save."""

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from lib import files as files_mod

PAST = "2026-10-20T12:00:00+00:00"


def git(cwd, *args):
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0",
           "GIT_AUTHOR_DATE": PAST, "GIT_COMMITTER_DATE": PAST}
    out = subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=T",
         "-c", "user.email=t@t", *args],
        capture_output=True, text=True, env=env)
    if out.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)}: {out.stderr}")
    return out.stdout.strip()


def sha_of(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class RepoFilesCase(unittest.TestCase):
    """A committed repo: notes.txt (then dirtied), .env
    (secret-shaped), bin.dat (binary), big.txt (over the
    line cap), link.txt (a symlink to notes.txt). Saves
    land their backup/audit under a state dir OUTSIDE the
    repo, as the server will arrange."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wb-repofiles-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        (self.repo / "notes.txt").write_text("one\ntwo\n")
        (self.repo / ".env").write_text("TOKEN=hunter2\n")
        (self.repo / "bin.dat").write_bytes(b"\x00\x01\x02")
        (self.repo / "big.txt").write_text(
            "".join(f"line {i}\n" for i in range(2100)))
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "base")
        (self.repo / "notes.txt").write_text("one\ntwo\nthree\n")
        os.symlink("notes.txt", self.repo / "link.txt")
        self.state = self.tmp / "state"
        self.backup_dir = self.state / "edit-backups" / "repo"
        self.audit_log = self.state / "edit-log.jsonl"

    def save(self, rel, content, base, **kw):
        kw.setdefault("editing_enabled", True)
        kw.setdefault("backup_dir", self.backup_dir)
        kw.setdefault("audit_log", self.audit_log)
        return files_mod.repo_save(
            self.repo, rel, content, base, **kw)

    # -- peek ------------------------------------------------

    def test_peek_text_with_diff(self):
        out = files_mod.repo_peek(self.repo, "notes.txt")
        self.assertEqual(out["content"], "one\ntwo\nthree\n")
        self.assertFalse(out["truncated"])
        self.assertEqual(out["sha256"],
                         sha_of("one\ntwo\nthree\n"))
        self.assertIn("+three", out["diff"])
        self.assertFalse(out["editable"])
        self.assertEqual(out["editable_reason"],
                         "editing disabled")

    def test_peek_clean_file_has_no_diff(self):
        out = files_mod.repo_peek(self.repo, "bin.dat")
        self.assertTrue(out["is_binary"])
        self.assertIsNone(out["content"])
        self.assertIsNone(out["diff"])
        self.assertEqual(out["editable_reason"], "binary")

    def test_peek_secret_withheld_then_revealed(self):
        out = files_mod.repo_peek(self.repo, ".env")
        self.assertEqual(out["withheld"], "secret")
        self.assertIsNone(out["content"])
        self.assertIsNone(out["sha256"])
        self.assertNotIn("revealed", out)
        out = files_mod.repo_peek(self.repo, ".env",
                                  reveal=True)
        self.assertIsNone(out["withheld"])
        self.assertTrue(out["revealed"])
        self.assertEqual(out["content"], "TOKEN=hunter2\n")
        self.assertEqual(out["sha256"], sha_of("TOKEN=hunter2\n"))

    def test_peek_secret_withheld_even_when_missing(self):
        out = files_mod.repo_peek(self.repo, "missing.key")
        self.assertEqual(out["withheld"], "secret")
        self.assertEqual(out["size_bytes"], 0)

    def test_peek_over_cap_truncated_and_uneditable(self):
        out = files_mod.repo_peek(
            self.repo, "big.txt", editing_enabled=True)
        self.assertTrue(out["truncated"])
        self.assertFalse(out["editable"])
        self.assertEqual(out["editable_reason"], "too large")
        self.assertEqual(
            len(out["content"].splitlines()),
            files_mod.PEEK_MAX_LINES)

    def test_peek_editable_when_enabled(self):
        out = files_mod.repo_peek(
            self.repo, "notes.txt", editing_enabled=True)
        self.assertTrue(out["editable"])
        self.assertIsNone(out["editable_reason"])

    def test_peek_escapes_refused(self):
        for bad in ("../outside.txt", "/etc/passwd", ""):
            with self.assertRaises(files_mod.FileError_) as cm:
                files_mod.repo_peek(self.repo, bad)
            self.assertEqual(cm.exception.status, 400)

    def test_peek_missing_is_404(self):
        with self.assertRaises(files_mod.FileError_) as cm:
            files_mod.repo_peek(self.repo, "nope.txt")
        self.assertEqual(cm.exception.status, 404)

    # -- save --------------------------------------------------

    def test_save_good_lands_backup_and_audit(self):
        base = sha_of("one\ntwo\nthree\n")
        out = self.save("notes.txt", "one\ntwo\nthree\nfour\n",
                        base)
        self.assertEqual((self.repo / "notes.txt").read_text(),
                         "one\ntwo\nthree\nfour\n")
        self.assertEqual(out["sha256"],
                         sha_of("one\ntwo\nthree\nfour\n"))
        backup = Path(out["backup"])
        self.assertTrue(backup.is_file())
        self.assertEqual(backup.read_text(), "one\ntwo\nthree\n")
        lines = self.audit_log.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["path"], "notes.txt")
        self.assertEqual(record["sha_before"], base)
        self.assertEqual(record["sha_after"], out["sha256"])

    def test_save_stale_sha_conflicts_and_writes_nothing(self):
        with self.assertRaises(files_mod.FileError_) as cm:
            self.save("notes.txt", "changed\n", "0" * 64)
        self.assertEqual(cm.exception.status, 409)
        self.assertEqual(
            cm.exception.payload["current_sha256"],
            sha_of("one\ntwo\nthree\n"))
        self.assertEqual((self.repo / "notes.txt").read_text(),
                         "one\ntwo\nthree\n")
        self.assertFalse(self.backup_dir.exists())

    def test_save_editing_disabled_refused(self):
        with self.assertRaises(files_mod.FileError_) as cm:
            self.save("notes.txt", "x\n",
                      sha_of("one\ntwo\nthree\n"),
                      editing_enabled=False)
        self.assertEqual(cm.exception.status, 403)
        self.assertEqual((self.repo / "notes.txt").read_text(),
                         "one\ntwo\nthree\n")

    def test_save_secret_needs_confirm(self):
        base = sha_of("TOKEN=hunter2\n")
        with self.assertRaises(files_mod.FileError_) as cm:
            self.save(".env", "TOKEN=new\n", base)
        self.assertEqual(cm.exception.status, 403)
        self.assertEqual((self.repo / ".env").read_text(),
                         "TOKEN=hunter2\n")
        out = self.save(".env", "TOKEN=new\n", base,
                        confirm_secret=True)
        self.assertEqual((self.repo / ".env").read_text(),
                         "TOKEN=new\n")
        self.assertEqual(out["sha256"], sha_of("TOKEN=new\n"))

    def test_save_secret_refused_before_existence(self):
        with self.assertRaises(files_mod.FileError_) as cm:
            self.save("ghost.key", "x\n", "0" * 64)
        self.assertEqual(cm.exception.status, 403)

    def test_save_symlink_refused(self):
        with self.assertRaises(files_mod.FileError_) as cm:
            self.save("link.txt", "x\n",
                      sha_of("one\ntwo\nthree\n"))
        self.assertEqual(cm.exception.status, 403)

    def test_save_binary_and_over_cap_refused(self):
        raw = (self.repo / "bin.dat").read_bytes()
        with self.assertRaises(files_mod.FileError_) as cm:
            self.save("bin.dat", "x\n",
                      hashlib.sha256(raw).hexdigest())
        self.assertEqual(cm.exception.status, 403)
        big = (self.repo / "big.txt").read_text()
        with self.assertRaises(files_mod.FileError_) as cm:
            self.save("big.txt", "x\n", sha_of(big))
        self.assertEqual(cm.exception.status, 403)
        with self.assertRaises(files_mod.FileError_) as cm:
            self.save("notes.txt", "x\n" * 2100,
                      sha_of("one\ntwo\nthree\n"))
        self.assertEqual(cm.exception.status, 413)

    def test_save_escape_refused(self):
        with self.assertRaises(files_mod.FileError_) as cm:
            self.save("../outside.txt", "x\n", "0" * 64)
        self.assertEqual(cm.exception.status, 400)
        self.assertFalse((self.tmp / "outside.txt").exists())


if __name__ == "__main__":
    unittest.main()
