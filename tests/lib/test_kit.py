"""Choice-kit tests (choice-kit plan Step 3): spec
validation, state-schema derivation, template embedding,
and the create/build round-trip against a temp registry.
The template fixture is a stub carrying the one ck-spec
element the real kit.html contract guarantees."""

import json
import os
import re
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from lib import kit
from lib import registry as reg
from lib.validators import check_state_schema

STUB_TEMPLATE = (
    "<!DOCTYPE html>\n<html><body>\n"
    '<script type="application/json" id="ck-spec">\n'
    '{"id": "stub", "title": "Stub"}\n'
    "</script>\n</body></html>\n")

_CK_SPEC_RE = re.compile(
    r'<script type="application/json" id="ck-spec">'
    r"(.*?)</script>", re.DOTALL)


def embedded_spec(html):
    m = _CK_SPEC_RE.search(html)
    assert m, "no ck-spec element in rendered page"
    return json.loads(m.group(1))


def minimal_spec(**overrides):
    spec = {"id": "mini-study", "title": "Mini study",
            "sections": [], "choices": []}
    spec.update(overrides)
    return spec


class TestValidateSpec(unittest.TestCase):
    def test_demo_spec_is_valid(self):
        self.assertEqual(kit.validate_spec(kit.demo_spec()),
                         [])

    def test_demo_spec_exercises_every_mechanism(self):
        spec = kit.demo_spec()
        types = {c["type"] for c in spec["choices"]}
        self.assertEqual(types, set(kit.SPEC_TYPES))
        self.assertTrue(any(
            s.get("controls") for s in spec["sections"]))
        self.assertTrue(any(
            c.get("place") == "section"
            for c in spec["choices"]))
        self.assertTrue(any(
            s.get("fb") for s in spec["sections"]))

    def test_spec_must_be_object_with_id_and_title(self):
        self.assertTrue(kit.validate_spec(["nope"]))
        self.assertTrue(kit.validate_spec({"title": "x"}))
        self.assertTrue(kit.validate_spec({"id": "x"}))
        self.assertTrue(kit.validate_spec(
            minimal_spec(id="Not A Slug")))

    def test_duplicate_choice_id(self):
        spec = minimal_spec(choices=[
            {"id": "a", "type": "toggle", "label": "A"},
            {"id": "a", "type": "toggle", "label": "A2"}])
        errors = kit.validate_spec(spec)
        self.assertTrue(any("duplicate" in e
                            for e in errors), errors)

    def test_unknown_type(self):
        spec = minimal_spec(choices=[
            {"id": "a", "type": "dial", "label": "A"}])
        errors = kit.validate_spec(spec)
        self.assertTrue(any("type" in e for e in errors),
                        errors)

    def test_single_and_multi_need_unique_options(self):
        for ctype in ("single", "multi"):
            spec = minimal_spec(choices=[
                {"id": "a", "type": ctype, "label": "A"}])
            errors = kit.validate_spec(spec)
            self.assertTrue(any("options" in e
                                for e in errors), errors)
            dup = minimal_spec(choices=[
                {"id": "a", "type": ctype, "label": "A",
                 "options": [{"value": "x"},
                             {"value": "x"}]}])
            errors = kit.validate_spec(dup)
            self.assertTrue(any("unique" in e
                                for e in errors), errors)

    def test_slider_bounds(self):
        bad = minimal_spec(choices=[
            {"id": "a", "type": "slider", "label": "A",
             "min": 10, "max": 10}])
        self.assertTrue(kit.validate_spec(bad))
        worse = minimal_spec(choices=[
            {"id": "a", "type": "slider", "label": "A",
             "min": "low", "max": 10}])
        self.assertTrue(kit.validate_spec(worse))
        good = minimal_spec(choices=[
            {"id": "a", "type": "slider", "label": "A",
             "min": 0, "max": 5}])
        self.assertEqual(kit.validate_spec(good), [])

    def test_section_controls_must_name_a_choice(self):
        spec = minimal_spec(
            sections=[{"id": "s", "heading": "S",
                       "controls": ["ghost"]}],
            choices=[{"id": "a", "type": "toggle",
                      "label": "A"}])
        errors = kit.validate_spec(spec)
        self.assertTrue(any("undeclared" in e
                            for e in errors), errors)
        spec["sections"][0]["controls"] = ["a"]
        self.assertEqual(kit.validate_spec(spec), [])

    def test_place_must_be_section(self):
        spec = minimal_spec(choices=[
            {"id": "a", "type": "toggle", "label": "A",
             "place": "header"}])
        self.assertTrue(kit.validate_spec(spec))


class TestDemoParity(unittest.TestCase):
    def test_demo_spec_matches_shipped_template_file(self):
        demo_file = Path(__file__).resolve().parents[2] \
            / "templates" / "choice-kit" / "spec.demo.json"
        if not demo_file.is_file():
            self.skipTest("template demo spec not present")
        with open(demo_file, encoding="utf-8") as f:
            shipped = json.load(f)
        self.assertEqual(kit.demo_spec(), shipped)


class TestLoadSpec(unittest.TestCase):
    def test_roundtrip_and_errors(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "spec.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(kit.demo_spec(), f)
            self.assertEqual(kit.load_spec(path)["id"],
                             "reading-app-settings-study")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{not json")
            with self.assertRaises(kit.KitError):
                kit.load_spec(path)
            with self.assertRaises(kit.KitError):
                kit.load_spec(Path(td) / "missing.json")


class TestDeriveStateSchema(unittest.TestCase):
    def test_all_types_mapped_or_excluded(self):
        schema = kit.derive_state_schema(kit.demo_spec())
        self.assertEqual(schema["dark-mode"]["type"],
                         "toggle")
        self.assertEqual(schema["layout"]["type"],
                         "select")
        self.assertEqual(schema["layout"]["options"],
                         ["comfortable", "compact", "list"])
        self.assertEqual(schema["font-size"]["type"],
                         "number")
        self.assertEqual(schema["refresh-interval"]["type"],
                         "number")
        self.assertEqual(schema["display-name"]["type"],
                         "text")
        self.assertNotIn("extras", schema)  # multi
        for field in schema.values():
            self.assertTrue(field["question"])

    def test_recommended_carried(self):
        schema = kit.derive_state_schema(kit.demo_spec())
        self.assertEqual(schema["layout"]["recommended"],
                         "compact")
        self.assertEqual(
            schema["line-spacing"]["recommended"],
            "relaxed")

    def test_result_passes_check_state_schema(self):
        schema = kit.derive_state_schema(kit.demo_spec())
        self.assertIsNone(check_state_schema(schema))


class TestRenderIndex(unittest.TestCase):
    def test_spec_replaced_and_reparseable(self):
        spec = kit.demo_spec()
        out = kit.render_index(STUB_TEMPLATE, spec)
        self.assertEqual(embedded_spec(out), spec)
        self.assertNotIn('"stub"', out)

    def test_missing_element_refused(self):
        with self.assertRaises(kit.KitError):
            kit.render_index("<html>no spec here</html>",
                             kit.demo_spec())


class KitFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "workbench" / "registry.db"
        self.layout = (self.root / "workbench" / "entries",
                       self.root / "workbench" / "archive")
        reg.init_registry(self.db)
        self.template_dir = self.root / "templates"
        self.template_dir.mkdir()
        with open(self.template_dir / "kit.html", "w",
                  encoding="utf-8") as f:
            f.write(STUB_TEMPLATE)
        # Hermetic back-default state: an ambient
        # WB_KIT_BACK_HREF on the machine running the
        # suite must not leak a stamped back into the
        # no-override tests. The env-override test sets
        # the variable itself, inside this patch.
        self._env_patch = unittest.mock.patch.dict(os.environ)
        self._env_patch.start()
        os.environ.pop(kit.BACK_HREF_ENV, None)

    def tearDown(self):
        self._env_patch.stop()
        self.tmp.cleanup()

    def create(self, slug="settings-study", **kw):
        kw.setdefault("template_dir", self.template_dir)
        return kit.create_kit(self.db, self.layout, slug,
                              **kw)


class TestCreateKit(KitFixture):
    def test_entry_shape_and_files(self):
        e = self.create()
        self.assertEqual(e["kind"], "artifact")
        self.assertEqual(e["main_file"], "index.html")
        entry_dir = Path(e["entry_dir"])
        index = entry_dir / "index.html"
        spec_file = entry_dir / "spec.json"
        self.assertTrue(index.is_file())
        self.assertTrue(spec_file.is_file())
        with open(index, encoding="utf-8") as f:
            page = f.read()
        self.assertEqual(embedded_spec(page)["id"],
                         "reading-app-settings-study")
        with open(spec_file, encoding="utf-8") as f:
            saved = json.load(f)
        # No back is stamped by default: tracked code
        # carries no back target, and the fixture sets no
        # environment override — the saved spec is the
        # demo spec exactly, back absent.
        self.assertEqual(saved, kit.demo_spec())
        self.assertNotIn("back", saved)
        self.assertEqual(e["content_sha256"],
                         reg.sha256_file(index))
        self.assertIsNotNone(e["state_schema"])
        self.assertNotIn("extras", e["state_schema"])

    def test_back_absent_without_override(self):
        # The back control's target is data recorded at
        # stamp time (byte-route plan): the only default
        # is the environment override, and tracked code
        # carries no target of its own — with no override
        # set (the fixture guarantees this), a spec
        # without a back keeps none, in both spec.json
        # and the page: the kit renders no back control.
        self.assertIsNone(kit.DEFAULT_BACK_HREF)
        e = self.create()
        entry_dir = Path(e["entry_dir"])
        with open(entry_dir / "spec.json",
                  encoding="utf-8") as f:
            saved = json.load(f)
        self.assertNotIn("back", saved)
        with open(entry_dir / "index.html",
                  encoding="utf-8") as f:
            page_spec = embedded_spec(f.read())
        self.assertNotIn("back", page_spec)

    def test_back_spec_value_preserved(self):
        spec = minimal_spec(
            back={"label": "← Home",
                  "href": "https://example.invalid/home"})
        e = self.create("custom-back", spec=spec)
        with open(Path(e["entry_dir"]) / "spec.json",
                  encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["back"], spec["back"])

    def test_back_env_override(self):
        # The environment override is the one default a
        # stamp applies: with it set, a spec without its
        # own back gains the override's target in both
        # spec.json and the page.
        with unittest.mock.patch.dict(
                os.environ,
                {kit.BACK_HREF_ENV:
                 "https://example.invalid/viewer"}):
            e = self.create("env-back")
        entry_dir = Path(e["entry_dir"])
        with open(entry_dir / "spec.json",
                  encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(
            saved["back"],
            {"label": kit.DEFAULT_BACK_LABEL,
             "href": "https://example.invalid/viewer"})
        with open(entry_dir / "index.html",
                  encoding="utf-8") as f:
            page_spec = embedded_spec(f.read())
        self.assertEqual(page_spec["back"], saved["back"])

    def test_back_malformed_refused(self):
        with self.assertRaises(kit.KitError):
            self.create("bad-back",
                        spec=minimal_spec(back={"label": "x"}))
        with self.assertRaises(kit.KitError):
            self.create("bad-back-2",
                        spec=minimal_spec(back="https://x"))

    def test_real_template_carries_the_control(self):
        # The shipped kit.html renders the back link from
        # the spec (byte-route plan): the control exists in
        # the runtime, ahead of the title, top-targeted.
        template = (Path(__file__).resolve().parent.parent
                    .parent / "templates" / "choice-kit"
                    / "kit.html")
        html = template.read_text(encoding="utf-8")
        self.assertIn("spec.back", html)
        self.assertIn('"a", "ck-back"', html)
        self.assertIn('"_top"', html)

    def test_supplied_spec_and_title(self):
        spec = minimal_spec(
            id="custom-study", title="Custom study",
            choices=[{"id": "ok", "type": "toggle",
                      "label": "OK?"}])
        e = self.create("custom", spec=spec,
                        title="Custom title")
        self.assertEqual(e["title"], "Custom title")
        self.assertEqual(
            e["state_schema"],
            {"ok": {"type": "toggle", "question": "OK?"}})

    def test_existing_slug_refused(self):
        self.create()
        with self.assertRaises(reg.RegistryError):
            self.create()

    def test_invalid_spec_refused(self):
        with self.assertRaises(kit.KitError):
            self.create("bad",
                        spec=minimal_spec(choices=[
                            {"id": "a", "type": "dial",
                             "label": "A"}]))


class TestBuildKit(KitFixture):
    def test_rebuild_after_spec_edit_changes_hash(self):
        e = self.create()
        entry_dir = Path(e["entry_dir"])
        spec = kit.load_spec(entry_dir / "spec.json")
        spec["title"] = "Renamed study"
        for c in spec["choices"]:
            if c["id"] == "display-name":
                c["label"] = "Shown name"
        with open(entry_dir / "spec.json", "w",
                  encoding="utf-8") as f:
            json.dump(spec, f)
        result = kit.build_kit(self.db, self.layout,
                               "settings-study",
                               template_dir=self.template_dir)
        self.assertEqual(result["slug"], "settings-study")
        self.assertNotEqual(result["sha256"],
                            e["content_sha256"])
        self.assertEqual(
            result["sha256"],
            reg.sha256_file(entry_dir / "index.html"))
        with open(entry_dir / "index.html",
                  encoding="utf-8") as f:
            page = f.read()
        self.assertEqual(embedded_spec(page)["title"],
                         "Renamed study")
        entry = reg.get_entry(self.db, "settings-study")
        self.assertEqual(
            entry["state_schema"]["display-name"]
            ["question"],
            "Shown name")

    def test_missing_entry_refused(self):
        with self.assertRaises(reg.RegistryError):
            kit.build_kit(self.db, self.layout, "ghost",
                          template_dir=self.template_dir)

    def test_missing_spec_refused(self):
        e = reg.add_entry(self.db, self.layout, "bare",
                          kind="artifact",
                          main_file="index.html")
        with self.assertRaises(kit.KitError):
            kit.build_kit(self.db, self.layout, "bare",
                          template_dir=self.template_dir)


if __name__ == "__main__":
    unittest.main()
