import json
import math
from pathlib import Path
import tempfile
import unittest

from deadlock_perf_lab.capture import read_mangohud
from deadlock_perf_lab.metrics import percentile, summarize
from deadlock_perf_lab.storage import LabError
from tests.helpers import mangohud


class MetricsTests(unittest.TestCase):
    def test_slowest_fraction_is_not_percentile_inverse(self):
        frames = [5.] * 990 + [10.] * 9 + [1000.]
        result = summarize(frames)
        self.assertAlmostEqual(result["avg_fps"], 1000 / 6.04)
        self.assertAlmostEqual(result["low_1_fps"], 1000 / 109)
        self.assertNotEqual(result["low_1_fps"], result["p99_inverse_fps"])
        self.assertEqual(result["max_frame_ms"], 1000)
        self.assertEqual(result["stalls_over_100ms"], 1)
        self.assertEqual(result["low_01_fps"], 1)

    def test_percentile_definition_and_short_tail(self):
        self.assertEqual(percentile([10, 20, 30, 40], .5), 25)
        self.assertIsNone(summarize([5.] * 99)["low_01_fps"])
        self.assertIsNone(summarize([5.] * 100, per_frame=False)["low_1_fps"])

    def test_nonfinite_and_invalid_never_reach_json(self):
        for value in (0, -1, math.nan, math.inf):
            with self.subTest(value=value), self.assertRaises(LabError):
                summarize([5.] * 20 + [value])


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "capture.csv"

    def test_normal_and_versioned_headers(self):
        for versioned in (False, True):
            mangohud(self.path, [5.] * 1000, versioned=versioned)
            result = read_mangohud(self.path, interval_ms=0)
            self.assertAlmostEqual(result.metrics()["avg_fps"], 200)
            self.assertEqual(result.metadata["system"]["cpu"], "CPU")
            json.dumps(result.metrics(), allow_nan=False)

    def test_window_excludes_loading_but_retains_in_window_stall(self):
        mangohud(self.path, [1000.] + [5.] * 1000 + [700.] + [5.] * 1000)
        capture = read_mangohud(self.path, start_s=2, duration_s=7, interval_ms=0)
        self.assertEqual(capture.metrics()["max_frame_ms"], 700)
        self.assertNotIn(1000, capture.frames)
        self.assertGreaterEqual(capture.times[0], 2)
        self.assertLess(capture.times[-1], 9)

    def test_interval_samples_cannot_be_relabelled_per_frame(self):
        mangohud(self.path, [5.] * 400, interval_ms=100)
        with self.assertRaisesRegex(LabError, "Declared per-frame"):
            read_mangohud(self.path, interval_ms=0)
        capture = read_mangohud(self.path, interval_ms=100)
        self.assertIsNone(capture.metrics()["low_1_fps"])
        self.assertTrue(capture.warnings)

    def test_unknown_interval_conservative(self):
        mangohud(self.path, [5.] * 100)
        self.assertFalse(read_mangohud(self.path).metadata["per_frame"])

    def test_partial_window_rejected(self):
        mangohud(self.path, [5.] * 100)
        with self.assertRaisesRegex(LabError, "does not cover"):
            read_mangohud(self.path, duration_s=30, interval_ms=0)

    def test_nan_rows_counted_and_reported(self):
        mangohud(self.path, [5.] * 100)
        self.path.write_text(self.path.read_text() + "200,nan,0\n200,inf,0\n200,-1,0\n")
        capture = read_mangohud(self.path, interval_ms=0)
        self.assertEqual(capture.metadata["invalid_rows"], 3)
        self.assertIn("Excluded 3", capture.warnings[0])

    def test_reset_log_rejected(self):
        mangohud(self.path, [5.] * 100)
        line = self.path.read_text().splitlines()[3]
        self.path.write_text(self.path.read_text() + line + "\n")
        with self.assertRaisesRegex(LabError, "backwards"):
            read_mangohud(self.path, interval_ms=0)

    def test_reordered_columns_and_bom(self):
        self.path.write_text("\ufeffelapsed,frametime,fps\n" + "\n".join(f"{i*5_000_000},5,200" for i in range(1,101)))
        self.assertEqual(read_mangohud(self.path, interval_ms=0).metrics()["avg_fps"], 200)

    def test_summary_csv_rejected(self):
        self.path.write_text("Average FPS,1% Min FPS\n200,170\n")
        with self.assertRaisesRegex(LabError, "Not a MangoHud"):
            read_mangohud(self.path)
