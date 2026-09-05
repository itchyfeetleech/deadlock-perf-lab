import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from deadlock_perf_lab.analysis import analyze, bootstrap_ci
from deadlock_perf_lab.cli import main
from deadlock_perf_lab.imports import import_capture, review_run
from deadlock_perf_lab.profiles import add_profile, catalog, validate_autoexec
from deadlock_perf_lab.report import bundle, generate_report
from deadlock_perf_lab.runner import run_session
from deadlock_perf_lab.storage import LabError, read_json, write_json
from deadlock_perf_lab.workspace import initialize, make_plan, verify_plan
from tests.helpers import mangohud


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace with spaces"
        with patch("deadlock_perf_lab.workspace.discover_install", return_value=None):
            initialize(self.workspace)
        config = read_json(self.workspace / "lab.json")
        config["scenario"].update(sample_s=1, warmup_s=0, cooldown_s=0, settle_s=0)
        config["conditions"] = {"resolution": "1920x1080", "graphics": "test fixture", "notes": "test conditions"}
        write_json(self.workspace / "lab.json", config)

    def demo(self, rounds=5):
        session, plan = make_plan(self.workspace, ["fps-unlock"], rounds, 47, demo=True)
        with contextlib.redirect_stdout(io.StringIO()):
            run_session(self.workspace, session)
        return session, plan

    def test_rounds_bracketed_and_seed_reproducible(self):
        _, a = make_plan(self.workspace, ["fps-unlock", "cap-144"], 5, 47, demo=True)
        _, b = make_plan(self.workspace, ["fps-unlock", "cap-144"], 5, 47, demo=True)
        self.assertEqual(a["schedule"], b["schedule"])
        for r in range(1,6):
            cases = [s["case"] for s in a["schedule"] if s["round"] == r]
            self.assertEqual(cases[0], "baseline")
            self.assertEqual(cases[-1], "baseline")
            self.assertEqual(len(cases), 4)

    def test_demo_through_report_and_allowlisted_export(self):
        session, plan = self.demo()
        result = analyze(session)
        self.assertEqual(result["valid_runs"], 15)
        self.assertEqual(result["comparisons"][0]["verdict"], "demo")
        self.assertIsNotNone(result["comparisons"][0]["ci95_pct"])
        # Files outside the explicit report allowlist must stay local.
        (session / "private.env").write_text("secret")
        output = generate_report(session)
        self.assertIn("DEMO DATA", output.read_text())
        self.assertNotIn(str(Path.home()), output.read_text())
        archive = bundle(session, self.root / "report.zip")
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(set(z.namelist()), {"index.html", "summary.json", "summary.md", "runs.csv"})
        with self.assertRaises(LabError):
            run_session(self.workspace, session)

    def test_plan_tampering_and_mixed_evidence_rejected(self):
        session, plan = self.demo()
        changed = dict(plan, seed=999)
        with self.assertRaisesRegex(LabError, "Plan changed"):
            verify_plan(changed)
        path = next((session / "runs").glob("*/result.json"))
        record = read_json(path)
        record["synthetic"] = False
        write_json(path, record)
        result = analyze(session)
        self.assertEqual(result["valid_runs"], 14)
        self.assertIn("mixed synthetic", str(result["excluded"]))

    def test_raw_changes_invalidate_result(self):
        session, _ = self.demo()
        raw = next((session / "runs").glob("*/capture.csv"))
        raw.write_text(raw.read_text() + "\n")
        self.assertIn("raw capture changed", str(analyze(session)["excluded"]))

    def test_context_mismatch_excluded(self):
        session, _ = self.demo()
        path = next((session / "runs").glob("*/result.json"))
        record = read_json(path)
        record["context_key"] = "different-resolution"
        write_json(path, record)
        self.assertIn("incompatible benchmark", str(analyze(session)["excluded"]))

    def test_import_order_reuse_conditions_and_operator_review(self):
        add_profile(self.workspace, {"id":"shadows-low", "kind":"manual", "description":"Set shadows low"})
        session, plan = make_plan(self.workspace, ["shadows-low"], 1, 47, manual=True)
        source = mangohud(self.root / "raw.csv", [5.] * 300)
        with self.assertRaisesRegex(LabError, "Next planned"):
            import_capture(session, source, "shadows-low", 1, interval_ms=0)
        run = import_capture(session, source, "baseline", 1, interval_ms=0)
        with self.assertRaisesRegex(LabError, "already imported"):
            import_capture(session, source, "shadows-low", 1, interval_ms=0)
        review_run(session, run.name, "Confirmed the intended replay camera and settings for this capture.")
        self.assertFalse(analyze(session)["runs"][0]["quality_blockers"])
        mangohud(source, [4.] * 350, system="Linux,Other CPU,GPU,32G,kernel,driver,performance")
        with self.assertRaisesRegex(LabError, "metadata differs"):
            import_capture(session, source, "shadows-low", 1, interval_ms=0)
        with self.assertRaisesRegex(LabError, "Manual plans"):
            run_session(self.workspace, session)

    def test_invalid_capture_cannot_create_success_result(self):
        add_profile(self.workspace, {"id":"manual", "kind":"manual", "description":"test"})
        session, _ = make_plan(self.workspace, ["manual"], 1, 47, manual=True)
        source = self.root / "bad.csv"
        source.write_text("oops")
        with self.assertRaises(LabError):
            import_capture(session, source, "baseline", 1, interval_ms=0)
        self.assertEqual(list((session / "runs").glob("*/result.json")), [])

    def test_custom_profile_is_copied_and_actions_rejected(self):
        validate_autoexec('fps_max "144"\n// comment\nr_farz 6000')
        for content in ('fps_max 0; connect x', 'exec other.cfg', 'bind x quit', 'demo_pause 1'):
            with self.subTest(content=content), self.assertRaises(LabError):
                validate_autoexec(content)
        profiles = catalog()
        self.assertEqual(len(profiles), 10)
        self.assertIn("GameInfo", profiles["community-sqooky"]["content"])

    def test_html_escapes_profile_labels_and_script_breakouts(self):
        session, plan = self.demo()
        # Modify via a fresh valid plan hash to model an operator-created label.
        from deadlock_perf_lab.storage import fingerprint
        plan["profiles"]["fps-unlock"]["name"] = '</script><script>alert("bad")</script>'
        plan["context"]["conditions"]["notes"] = "</script><script>alert('note')</script>"
        plan["plan_sha256"] = fingerprint({k:v for k,v in plan.items() if k != "plan_sha256"})
        write_json(session / "plan.json", plan)
        page = generate_report(session).read_text()
        self.assertNotIn('<script>alert("bad")', page)
        self.assertNotIn("<script>alert('note')", page)

    def test_cli_returns_actionable_errors(self):
        with contextlib.redirect_stderr(io.StringIO()) as output:
            result = main(["--workspace", str(self.workspace), "plan", "--rounds", "0"])
        self.assertEqual(result, 1)
        self.assertIn("rounds", output.getvalue())

    def test_bootstrap_is_reproducible_and_no_false_small_n_precision(self):
        self.assertIsNone(bootstrap_ci([3, 4]))
        self.assertEqual(bootstrap_ci([4, 5, 6, 7, 8]), bootstrap_ci([4, 5, 6, 7, 8]))

    def manual_experiment(self, *, drift=False):
        add_profile(self.workspace, {"id":"treatment", "kind":"manual", "name":"Treatment", "description":"Controlled treatment"})
        session, plan = make_plan(self.workspace, ["treatment"], 5, 47, manual=True)
        for item in plan["schedule"]:
            ft = (5 if item["case"] == "baseline" else 4.4) + item["index"] * .0001
            if drift and item["case"] == "baseline":
                ft += item["round"] * .3
            source = mangohud(self.root / f"source-{item['index']}.csv", [ft] * 300)
            run = import_capture(session, source, item["case"], item["round"], interval_ms=0)
            review_run(session, run.name, "Checked intended settings, camera and replay progression on this trial.")
        return session

    def test_stable_complete_real_experiment_can_establish_direction(self):
        session = self.manual_experiment()
        result = analyze(session)
        self.assertEqual(result["comparisons"][0]["verdict"], "improved")
        self.assertGreater(result["comparisons"][0]["ci95_pct"][0], 3)
        self.assertEqual(len(result["comparisons"][0]["paired_rounds"]), 5)

    def test_drift_blocks_apparent_improvement(self):
        session = self.manual_experiment(drift=True)
        result = analyze(session)
        self.assertEqual(result["comparisons"][0]["verdict"], "inconclusive")
        self.assertIn("Baseline stability", str(result["comparisons"][0]["reasons"]))

    def test_missing_closing_control_blocks_direction(self):
        session = self.manual_experiment()
        last = sorted((session / "runs").glob("*/result.json"))[-1]
        last.unlink()
        result = analyze(session)
        self.assertEqual(result["comparisons"][0]["verdict"], "inconclusive")
        self.assertEqual(len(result["comparisons"][0]["paired_rounds"]), 4)

    def test_screen_preset_is_fast_and_does_not_edit_workspace(self):
        before = (self.workspace / "lab.json").read_bytes()
        _, plan = make_plan(self.workspace, ["cap-*"], 1, 47, demo=True, preset="screen")
        self.assertEqual(plan["context"]["scenario"]["sample_s"], 10)
        self.assertEqual(plan["context"]["scenario"]["warmup_s"], 5)
        self.assertEqual(len(plan["schedule"]), 4)
        self.assertEqual((self.workspace / "lab.json").read_bytes(), before)
        self.assertEqual(plan["preset"], "screen")
