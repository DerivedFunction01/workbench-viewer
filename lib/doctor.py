"""wb doctor: read-only consistency checks over every
project the sweep registers.

The doctor derives everything from the same lib functions
the server feeds use — the bundle/todo parser
(lib/plans/bundles.py), the plan parser's status vocabulary
(lib/plans/parser.py), the registry validator suite
(lib/validators.py), and the Board feed's approval-coverage
derivation (lib/staleness.py). It holds no second
implementation of any of them.

A finding is a dict {project, check, subject, detail}; its
identity is the (project, check, subject) triple. The
doctor never mutates project data: its only writes are its
own run state (state/doctor-findings.json, resolved through
the server config seam by the CLI) and, when the finding
set changes under --post, one digest message through
lib/messages.py — the one message path.

Check families:
  plan-closeout        a flat plan's declared Status
                       contradicts its filing (the bundles
                       module's closeout derivation)
  plan-status          a plan with no Status header, or a
                       declared value outside the
                       recognized vocabulary
  plan-missing-child   a declared subplan path that does
                       not resolve to a file
  plan-done-not-closed a bundle whose todos are all done
                       while its plan still declares an
                       active status in the active tree
  todo-frontmatter     a todo file the bundles parser
                       flags invalid
  todo-missing-plan    a todo needs no plan reference; a
                       reference counts as resolved when
                       the named plan exists in the active
                       tree or under finished/ — the
                       finding fires only when the named
                       plan exists in neither
  todo-duplicate-id    one todo id living in more than one
                       bundle of a project
  registry-validator   the validate_project suite's
                       findings, unchanged
  approval-coverage    an approved entry whose current
                       state the approval no longer covers
  entry-archive-mismatch
                       an entry whose archived flag and
                       folder location disagree, where the
                       validator suite did not already
                       report that entry
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from . import messages as msg_mod
from . import registry as reg
from . import staleness as stale_mod
from . import validators as val_mod
from .plans import bundles as bundle_parser
from .plans.parser import declared_status

# The plan syntax standard's Status vocabulary (draft,
# approved, in progress, complete, superseded) plus the
# parser's DONE_WORDS synonyms for the closed states.
STATUS_VOCABULARY = frozenset({
    "draft", "approved", "in progress",
    "complete", "superseded",
    "done", "finished", "implemented",
})

CLOSED_STATUSES = ("complete", "superseded")


def _finding(project, check, subject, detail):
    return {"project": project, "check": check,
            "subject": subject, "detail": detail}


def finding_key(finding):
    """The identity of a finding: (project, check,
    subject). Detail text may be reworded without the
    finding becoming a different one."""
    return (finding["project"], finding["check"],
            finding["subject"])


# ----------------------------------------------------------------
# Plan / todo family
# ----------------------------------------------------------------

def _plan_ref_exists(root, plans_dir, ref) -> bool:
    """A todo's plan reference resolves the way it is
    written in the corpus: project-root-relative
    (`.plans/<file>`) or plans-dir-relative. A plan that
    was closed out after the todo was written now lives
    under `<plans_dir>/finished/` at the same relative
    path — flat plans and whole bundles alike — so that
    spelling resolves too. A reference naming a plan in
    neither tree does not resolve."""
    for candidate in (root / ref, plans_dir / ref):
        if candidate.is_file():
            return True
        try:
            relative = candidate.relative_to(plans_dir)
        except ValueError:
            continue
        if (plans_dir / "finished" / relative).is_file():
            return True
    return False


def _plan_status_finding(slug, plan):
    """One plan summary → its plan-status finding or None.
    Shared by flat plans and bundle plan.md files."""
    raw = plan["status_raw"]
    if not raw:
        return _finding(
            slug, "plan-status", plan["path"],
            "no Status: header line — the plan declares "
            "no status")
    declared = declared_status(raw)
    if declared is not None \
            and declared not in STATUS_VOCABULARY:
        return _finding(
            slug, "plan-status", plan["path"],
            f"Status declares {declared!r}, outside the "
            f"recognized vocabulary "
            f"({', '.join(sorted(STATUS_VOCABULARY))})")
    return None


def plan_todo_findings(project) -> list:
    """The plan/todo check family for one swept project.
    `project` is a sweep Project (its manifest carries the
    plans dir and the project root)."""
    slug = project.slug
    manifest = project.manifest
    plans_dir = manifest.plans
    out = []
    if plans_dir is None or not plans_dir.is_dir():
        return out
    bundles = bundle_parser.list_bundles(plans_dir)
    todo_bundles = {}
    for b in bundles:
        plan = b["plan"]
        if b["kind"] == "flat-plan":
            for err in b["errors"]:
                if err["error"].startswith("closeout:"):
                    out.append(_finding(
                        slug, "plan-closeout", err["path"],
                        err["error"]))
        if plan is not None:
            status_finding = _plan_status_finding(slug, plan)
            if status_finding is not None:
                out.append(status_finding)
            for sub in plan["subplans"]:
                if not (plans_dir / sub).is_file():
                    out.append(_finding(
                        slug, "plan-missing-child",
                        f"{plan['path']} -> {sub}",
                        f"declared subplan {sub!r} does "
                        f"not resolve to a file"))
        if b["kind"] == "bundle" and not b["archived"] \
                and plan is not None and b["todos"] \
                and all(t["valid"] and t["status"] == "done"
                        for t in b["todos"]):
            declared = declared_status(plan["status_raw"])
            if declared is not None \
                    and declared not in CLOSED_STATUSES:
                out.append(_finding(
                    slug, "plan-done-not-closed",
                    plan["path"],
                    f"every todo in bundle {b['id']} is "
                    f"done, but the plan still declares "
                    f"{declared!r} in the active tree — "
                    f"close it out or reopen a todo"))
        for t in b["todos"]:
            if t["id"]:
                todo_bundles.setdefault(t["id"], set()) \
                    .add(b["id"])
            if not t["valid"]:
                out.append(_finding(
                    slug, "todo-frontmatter", t["path"],
                    "; ".join(t["errors"])))
            if t["plan"] and not _plan_ref_exists(
                    manifest.root, plans_dir, t["plan"]):
                out.append(_finding(
                    slug, "todo-missing-plan", t["path"],
                    f"plan reference {t['plan']!r} does "
                    f"not resolve to a file"))
    for todo_id, homes in todo_bundles.items():
        if len(homes) > 1:
            out.append(_finding(
                slug, "todo-duplicate-id", todo_id,
                f"todo id appears in more than one "
                f"bundle: {', '.join(sorted(homes))}"))
    return out


# ----------------------------------------------------------------
# Registry family
# ----------------------------------------------------------------

def registry_findings(project) -> list:
    """The registry check family for one swept project:
    the validator suite unchanged, the Board feed's
    approval-coverage derivation, and the archive
    mismatch the suite leaves unreported."""
    slug = project.slug
    manifest = project.manifest
    out = []
    if manifest.registry is None \
            or not manifest.registry.is_file():
        return out
    db_path = manifest.registry
    layout = (manifest.mockups, manifest.archive)
    reported_archive = set()
    for f in val_mod.validate_project(db_path, layout):
        out.append(_finding(
            slug, "registry-validator",
            f"{f['validator']}:{f['entry']}", f["message"]))
        if f["validator"] == "archived-folder-agreement":
            reported_archive.add(f["entry"])
    for e in reg.list_entries(db_path, archived=None):
        if not e["archived"]:
            coverage = stale_mod.approval_coverage(
                e, reg.latest_review(db_path, e["id"]))
            if coverage["approved"] \
                    and not coverage["covers_current"]:
                out.append(_finding(
                    slug, "approval-coverage", e["id"],
                    f"approved at {coverage['approved_at']} "
                    f"against state "
                    f"{(coverage['approved_state_sha256'] or '')[:12]}; "
                    f"the entry's state has changed since "
                    f"— the approval no longer covers it"))
        if e["id"] in reported_archive:
            continue
        if e.get("source_kind") == "entry-dir" \
                and e.get("entry_dir"):
            in_archive = val_mod._is_under(
                Path(e["entry_dir"]), layout[1])
            if bool(e["archived"]) != in_archive:
                state = "archived" if e["archived"] \
                    else "not archived"
                place = "under the archive dir" if in_archive \
                    else "outside the archive dir"
                out.append(_finding(
                    slug, "entry-archive-mismatch", e["id"],
                    f"entry is {state} but its folder is "
                    f"{place}"))
    return out


# ----------------------------------------------------------------
# The sweep-wide run
# ----------------------------------------------------------------

def run_checks(projects) -> list:
    """Every finding across the swept projects, sorted by
    identity for stable output and diffing."""
    out = []
    for project in projects:
        out.extend(plan_todo_findings(project))
        out.extend(registry_findings(project))
    out.sort(key=lambda f: (finding_key(f), f["detail"]))
    return out


# ----------------------------------------------------------------
# Run state, the diff, and the digest (step 3)
# ----------------------------------------------------------------

STATE_VERSION = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc) \
        .isoformat(timespec="seconds")


def _key_str(key) -> str:
    return json.dumps(list(key))


def load_state(path):
    """The previous run's finding records, keyed by the
    JSON form of the finding identity:
    {key: {project, check, subject, detail, first_seen}}.
    None when no state file exists — the next --post run
    is the baseline."""
    path = Path(path)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("findings", {})


def save_state(path, records) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps({"version": STATE_VERSION,
                    "findings": records},
                   indent=1, sort_keys=True),
        encoding="utf-8")
    tmp.replace(path)


def diff_findings(prev_records, current, *, now):
    """Diff the current finding list against the previous
    run's records. Returns (new, resolved, merged,
    baseline): `new` and `resolved` are finding-shaped
    records; `merged` is the next state (surviving findings
    keep their first-seen stamp, new ones take `now`)."""
    current_by_key = {}
    for f in current:
        current_by_key[_key_str(finding_key(f))] = f
    if prev_records is None:
        merged = {k: {**f, "first_seen": now}
                  for k, f in current_by_key.items()}
        return list(current), [], merged, True
    new = []
    merged = {}
    for k, f in current_by_key.items():
        if k in prev_records:
            merged[k] = {**f, "first_seen":
                         prev_records[k]["first_seen"]}
        else:
            new.append(f)
            merged[k] = {**f, "first_seen": now}
    resolved = [rec for k, rec in prev_records.items()
                if k not in current_by_key]
    resolved.sort(key=lambda r: (r["project"], r["check"],
                                 r["subject"]))
    new.sort(key=lambda f: (finding_key(f), f["detail"]))
    return new, resolved, merged, False


def _digest_record(rec) -> str:
    return (f"- [{rec['project']}] {rec['check']} — "
            f"{rec['subject']}: {rec['detail']}")


def format_digest(new, resolved, *, baseline,
                  current_count) -> str:
    """The digest message body: new findings first, then
    resolved (a fix confirms itself). A baseline digest
    names the full current set."""
    lines = []
    if baseline:
        lines.append("wb doctor — baseline digest "
                     "(first recorded run)")
        lines.append(f"{current_count} current "
                     f"finding(s):")
        lines.extend(_digest_record(f) for f in new)
    else:
        lines.append(
            f"wb doctor — findings changed: "
            f"{len(new)} new, {len(resolved)} resolved "
            f"({current_count} current)")
        if new:
            lines.append("")
            lines.append("New:")
            lines.extend(_digest_record(f) for f in new)
        if resolved:
            lines.append("")
            lines.append("Resolved:")
            lines.extend(_digest_record(r) for r in resolved)
    return "\n".join(lines) + "\n"


def run_post(projects, *, state_path, messages_db,
             harness_slug, findings=None, now=None) -> dict:
    """One --post run: check, diff against the previous
    state, post ONE digest through lib/messages when the
    finding set changed (a first run always posts its
    baseline), then rewrite the state file. The digest is
    authored by the harness's own sender and lands born
    sent, so the watcher outbox carries it like any other
    workbench message."""
    now = now or _now_iso()
    current = findings if findings is not None \
        else run_checks(projects)
    prev = load_state(state_path)
    new, resolved, merged, baseline = diff_findings(
        prev, current, now=now)
    posted = False
    message_id = None
    if baseline or new or resolved:
        body = format_digest(new, resolved,
                             baseline=baseline,
                             current_count=len(current))
        Path(messages_db).parent.mkdir(parents=True,
                                       exist_ok=True)
        msg = msg_mod.create_message(
            messages_db, author="Muse", body=body,
            project_slug=harness_slug, send=True)
        message_id = msg["id"]
        posted = True
    save_state(state_path, merged)
    return {"findings": current, "new": new,
            "resolved": resolved, "baseline": baseline,
            "posted": posted, "message_id": message_id}
