"""The choice kit: spec handling for starter study
artifacts (choice-kit plan, 2026-11-08).

A kit artifact is a registry entry of kind "artifact" whose
main file (index.html) is the shared kit runtime with one
study's SPEC embedded as JSON, plus the spec itself kept
beside it as spec.json — the editable source of truth.
`wb artifact new` stamps an entry out from the template in
templates/choice-kit/; `wb artifact build` re-renders
index.html from spec.json after edits. Publishing the
rendered page as a platform artifact is the agent's
artifact-tool step; nothing here publishes.

The spec's choices also derive a registry state_schema (in
the validators' vocabulary) so answers given inside the
viewer ride the existing review/set-state path. A `multi`
choice has no registry field type — it is excluded from
the schema and its answers travel in the copy payload only.

Stdlib only, like the rest of lib/.
"""

import json
import os
import re
from pathlib import Path

from . import registry as reg
from . import validators as val_mod
from .registry.constants import check_slug
from .util import sha256_file, write_text

SPEC_TYPES = ("toggle", "single", "multi", "slider",
              "input-text", "input-number")

# The back control's target is deployment data, never a
# tracked default (byte-route plan, 2026-11-10;
# portability fix, 2026-11-11): the target is recorded
# in the spec at stamp time, and the only default a
# stamp applies comes from the environment override
# (BACK_HREF_ENV) — a deployment points its kit pages
# home by setting it. Tracked code carries no target of
# its own: with no override set, a spec without its own
# back keeps none, and the page renders no back control
# (honest absence) rather than a target invented here.
DEFAULT_BACK_HREF = None
DEFAULT_BACK_LABEL = "← Workbench"
BACK_HREF_ENV = "WB_KIT_BACK_HREF"

_CK_SPEC_RE = re.compile(
    r'(<script type="application/json" id="ck-spec">)'
    r"(.*?)"
    r"(</script>)",
    re.DOTALL)


class KitError(Exception):
    """A spec or template problem the caller can fix."""


def _is_number(value):
    return isinstance(value, (int, float)) \
        and not isinstance(value, bool)


def load_spec(path) -> dict:
    """Read a spec JSON file. KitError on an unreadable
    file or invalid JSON."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise KitError(f"cannot read spec {path}: {e}") \
            from e
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise KitError(f"spec {path} is not valid JSON: "
                       f"{e}") from e


def validate_spec(spec) -> list:
    """Spec problems as a list of strings (empty = valid).

    Shape: an object with a slug-shaped `id` and a `title`;
    `choices` a list whose ids are unique and slug-shaped
    and whose types are all in SPEC_TYPES; `sections` a
    list whose `controls` name declared choices only."""
    errors = []
    if not isinstance(spec, dict):
        return ["spec must be a JSON object"]
    spec_id = spec.get("id")
    if not isinstance(spec_id, str) or not spec_id:
        errors.append("spec id is required")
    else:
        try:
            check_slug(spec_id)
        except reg.RegistryError:
            errors.append(
                f"spec id {spec_id!r} is not slug-shaped "
                f"(lowercase letters, digits, hyphens)")
    if not isinstance(spec.get("title"), str) \
            or not spec.get("title"):
        errors.append("spec title is required")
    back = spec.get("back")
    if back is not None:
        if not isinstance(back, dict) \
                or not isinstance(back.get("href"), str) \
                or not back.get("href"):
            errors.append(
                "spec back must be an object with a "
                "non-empty href")
        elif "label" in back \
                and not isinstance(back["label"], str):
            errors.append("spec back label must be a string")
    choices = spec.get("choices", [])
    if not isinstance(choices, list):
        errors.append("spec choices must be a list")
        choices = []
    choice_ids = set()
    for choice in choices:
        if not isinstance(choice, dict):
            errors.append("every choice must be an object")
            continue
        cid = choice.get("id")
        if not isinstance(cid, str) or not cid:
            errors.append("every choice needs an id")
            continue
        try:
            check_slug(cid)
        except reg.RegistryError:
            errors.append(
                f"choice id {cid!r} is not slug-shaped")
        if cid in choice_ids:
            errors.append(f"duplicate choice id {cid!r}")
        choice_ids.add(cid)
        ctype = choice.get("type")
        if ctype not in SPEC_TYPES:
            errors.append(
                f"choice {cid!r}: type must be one of "
                f"{SPEC_TYPES}, got {ctype!r}")
            continue
        if ctype in ("single", "multi"):
            options = choice.get("options")
            if not isinstance(options, list) \
                    or not options:
                errors.append(
                    f"choice {cid!r}: {ctype} needs a "
                    f"non-empty options list")
            else:
                values = []
                for opt in options:
                    if not isinstance(opt, dict) \
                            or "value" not in opt:
                        errors.append(
                            f"choice {cid!r}: every option "
                            f"needs a value")
                    else:
                        values.append(opt["value"])
                if len(set(values)) != len(values):
                    errors.append(
                        f"choice {cid!r}: option values "
                        f"must be unique")
        if ctype == "slider":
            lo, hi = choice.get("min"), choice.get("max")
            if not _is_number(lo) or not _is_number(hi):
                errors.append(
                    f"choice {cid!r}: slider needs numeric "
                    f"min and max")
            elif not lo < hi:
                errors.append(
                    f"choice {cid!r}: slider min must be "
                    f"less than max")
        place = choice.get("place")
        if place is not None and place != "section":
            errors.append(
                f"choice {cid!r}: place must be "
                f"\"section\" when present, got {place!r}")
    sections = spec.get("sections", [])
    if not isinstance(sections, list):
        errors.append("spec sections must be a list")
        sections = []
    for section in sections:
        if not isinstance(section, dict):
            errors.append("every section must be an object")
            continue
        for cid in section.get("controls") or []:
            if cid not in choice_ids:
                errors.append(
                    f"section "
                    f"{section.get('id') or section.get('heading')!r}: "
                    f"controls names undeclared choice "
                    f"{cid!r}")
    return errors


def demo_spec() -> dict:
    """The scaffold spec: the fictional reading-app
    settings study shipped as templates/choice-kit/
    spec.demo.json (the demo file create_kit uses by
    default). This in-code mirror exists for callers
    without the template tree; a test pins the two
    equal. It exercises every mechanism — one choice of
    every type, inline linked controls, a place:
    "section" choice, an fb-labelled section, and a
    section image."""
    svg = (
        "data:image/svg+xml,%3Csvg "
        "xmlns='http://www.w3.org/2000/svg' width='320' "
        "height='120'%3E%3Crect width='320' height='120' "
        "fill='%23e8e4da'/%3E%3Crect x='16' y='16' "
        "width='288' height='20' fill='%23b9b2a2'/%3E"
        "%3Crect x='16' y='48' width='200' height='12' "
        "fill='%23cfc8b8'/%3E%3Crect x='16' y='68' "
        "width='240' height='12' fill='%23cfc8b8'/%3E"
        "%3C/svg%3E")
    return {
        "id": "reading-app-settings-study",
        "title": "Reading App Settings — Study",
        "intro": "A fictional settings study that "
                 "demonstrates every choice-kit control "
                 "by example. Change anything, then press "
                 "**Copy** and paste the JSON back. Turn "
                 "on **Feedback mode** to annotate any "
                 "block instead of changing it.",
        "sections": [
            {"id": "appearance",
             "heading": "Appearance",
             "body": "The reading surface restyles "
                     "itself around two picks.\n\n"
                     "- **Dark mode** trades contrast "
                     "for comfort at night\n"
                     "- Layout density decides how much "
                     "fits on one screen\n\n"
                     "Both controls live right here, "
                     "next to the text they govern — and "
                     "again in the summary at the end, "
                     "bound to the same value, so "
                     "changing either one changes both.",
             "controls": ["dark-mode", "layout"],
             "image": {
                 "alt": "A plain grey rectangle standing "
                        "in for an app window",
                 "src": svg}},
            {"id": "reading-comfort",
             "heading": "Reading comfort",
             "body": "Long-form text stays readable "
                     "when the type size and the line "
                     "spacing fit the reader. This whole "
                     "section carries a feedback label: "
                     "in Feedback mode, clicking any "
                     "unlabelled part of it resolves to "
                     "this section.\n\n"
                     "The **line spacing** pick exists "
                     "only in this section — its summary "
                     "row shows the current value and a "
                     "jump link instead of a second "
                     "control.",
             "controls": ["font-size", "line-spacing"],
             "fb": "Reading comfort section"},
        ],
        "choices": [
            {"id": "dark-mode", "type": "toggle",
             "label": "Dark mode",
             "help": "Invert the reading surface for "
                     "low-light use.",
             "default": True},
            {"id": "layout", "type": "single",
             "label": "Layout density",
             "help": "How much content fits on one "
                     "screen.",
             "options": [
                 {"value": "comfortable",
                  "label": "Comfortable"},
                 {"value": "compact", "label": "Compact",
                  "recommended": True},
                 {"value": "list", "label": "List"}]},
            {"id": "line-spacing", "type": "single",
             "label": "Line spacing",
             "help": "Vertical rhythm between lines of "
                     "body text.",
             "place": "section",
             "options": [
                 {"value": "single", "label": "Single"},
                 {"value": "relaxed", "label": "Relaxed",
                  "recommended": True},
                 {"value": "double", "label": "Double"}]},
            {"id": "font-size", "type": "slider",
             "label": "Font size",
             "help": "Base size for body text.",
             "min": 12, "max": 24, "step": 1,
             "unit": "px", "default": 16},
            {"id": "extras", "type": "multi",
             "label": "Extra tools",
             "help": "Optional tools pinned beside the "
                     "reader.",
             "options": [
                 {"value": "bookmarks",
                  "label": "Bookmarks"},
                 {"value": "highlights",
                  "label": "Highlights"},
                 {"value": "notes", "label": "Notes"},
                 {"value": "sharing",
                  "label": "Sharing"}],
             "default": ["bookmarks"]},
            {"id": "display-name", "type": "input-text",
             "label": "Display name",
             "help": "Shown next to shared highlights.",
             "default": ""},
            {"id": "refresh-interval",
             "type": "input-number",
             "label": "Refresh interval",
             "help": "Minutes between automatic syncs.",
             "default": 30},
        ],
    }


def derive_state_schema(spec) -> dict:
    """The spec's choices as a registry state_schema, in
    the validators' vocabulary (toggle / select / text /
    number). `multi` is excluded — it has no registry
    field type. Raises KitError when the result would not
    pass check_state_schema."""
    schema = {}
    for choice in spec.get("choices") or []:
        cid = choice.get("id")
        ctype = choice.get("type")
        label = choice.get("label") or cid
        if ctype == "toggle":
            schema[cid] = {"type": "toggle",
                           "question": label}
        elif ctype == "single":
            field = {"type": "select",
                     "options": [o["value"] for o in
                                 choice.get("options")
                                 or []],
                     "question": label}
            for opt in choice.get("options") or []:
                if opt.get("recommended"):
                    field["recommended"] = opt["value"]
                    break
            schema[cid] = field
        elif ctype in ("slider", "input-number"):
            schema[cid] = {"type": "number",
                           "question": label}
        elif ctype == "input-text":
            schema[cid] = {"type": "text",
                           "question": label}
        # multi: no registry equivalent — excluded.
    problem = val_mod.check_state_schema(schema)
    if problem:
        raise KitError(
            f"derived state schema is invalid: {problem}")
    return schema


def render_index(template_text, spec) -> str:
    """The kit HTML with its embedded spec replaced by
    this spec's JSON. KitError when the template carries
    no ck-spec element."""
    payload = json.dumps(spec, indent=2,
                         ensure_ascii=False)
    # A literal "</script>" inside a spec string would
    # end the element early; "<\/script>" is the same
    # JSON string once parsed.
    payload = payload.replace("</", "<\\/")
    out, n = _CK_SPEC_RE.subn(
        lambda m: m.group(1) + "\n" + payload + "\n"
        + m.group(3),
        template_text, count=1)
    if n == 0:
        raise KitError(
            "kit template has no ck-spec script element "
            "to embed the spec into")
    return out


def _read_template(template_dir) -> str:
    path = Path(template_dir) / "kit.html"
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        raise KitError(
            f"cannot read kit template {path}: {e}") \
            from e


def with_default_back(spec) -> dict:
    """The spec with a back control stamped from the
    environment when the spec declares none (byte-route
    plan): the control's target is data recorded in the
    spec at stamp time, and the only default is the
    BACK_HREF_ENV override — tracked code carries no
    target of its own. An explicit spec value — including
    a deliberate custom target — is preserved verbatim,
    and with no override set a spec without a back keeps
    none: the page renders no back control."""
    if spec.get("back"):
        return spec
    href = os.environ.get(BACK_HREF_ENV) or DEFAULT_BACK_HREF
    if not href:
        return spec
    return {**spec, "back": {"label": DEFAULT_BACK_LABEL,
                             "href": href}}


def create_kit(db_path, layout, slug, *, title=None,
               spec=None, template_dir, owner_thread=None,
               owner_label=None, plan_ref=None,
               deploy_class="standard") -> dict:
    """Stamp out a kit artifact entry: register it (kind
    "artifact", main_file index.html, derived
    state_schema), render index.html from the template,
    and keep spec.json beside it. An existing slug is
    refused by add_entry and propagates.

    The default spec is the template's spec.demo.json —
    the one demo source, identical to the spec embedded
    in kit.html as shipped; demo_spec() is its in-code
    mirror (a test pins the two equal) and the fallback
    when a template dir carries no demo file."""
    if spec is None:
        demo_file = Path(template_dir) / "spec.demo.json"
        spec = load_spec(demo_file) \
            if demo_file.is_file() else demo_spec()
    spec = with_default_back(spec)
    errors = validate_spec(spec)
    if errors:
        raise KitError("invalid spec: "
                       + "; ".join(errors))
    template = _read_template(template_dir)
    entry = reg.add_entry(
        db_path, layout, slug,
        title=title or spec.get("title"),
        kind="artifact", main_file="index.html",
        state_schema=derive_state_schema(spec),
        plan_ref=plan_ref,
        owner_thread=owner_thread, owner_label=owner_label,
        deploy_class=deploy_class)
    entry_dir = Path(entry["entry_dir"])
    write_text(entry_dir / "index.html",
               render_index(template, spec))
    write_text(entry_dir / "spec.json",
               json.dumps(spec, indent=2,
                          ensure_ascii=False) + "\n")
    # add_entry fingerprinted the placeholder main file;
    # accept the rendered file as the entry's content.
    return reg.verify_entry(db_path, slug, actor="cli",
                            accept_drift=True)


def build_kit(db_path, layout, slug, *,
              template_dir) -> dict:
    """Re-render an existing kit entry's index.html from
    its spec.json (after edits), refresh its derived
    state_schema, and restamp its content hash."""
    entry = reg.get_entry(db_path, slug)
    if not entry.get("entry_dir"):
        raise KitError(
            f"{slug}: entry has no entry dir to build in")
    entry_dir = Path(entry["entry_dir"])
    spec_path = entry_dir / "spec.json"
    if not spec_path.is_file():
        raise KitError(
            f"{slug}: no spec.json in {entry_dir}")
    spec = load_spec(spec_path)
    errors = validate_spec(spec)
    if errors:
        raise KitError("invalid spec: "
                       + "; ".join(errors))
    template = _read_template(template_dir)
    schema = derive_state_schema(spec)
    if schema != entry.get("state_schema"):
        reg.set_state_schema(db_path, slug, schema,
                             actor="cli")
    write_text(entry_dir / "index.html",
               render_index(template, spec))
    built = reg.verify_entry(db_path, slug, actor="cli",
                             accept_drift=True)
    return {"slug": slug,
            "sha256": built["content_sha256"]}
