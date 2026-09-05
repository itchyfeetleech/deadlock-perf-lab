import unittest

from deadlock_perf_lab.analysis import aggregate_metrics


class ReportingTests(unittest.TestCase):
    def test_capture_means_do_not_weight_long_runs_more(self):
        records = [{"metrics": {"avg_fps": 100, "low_1_fps": 80, "samples": 1000}},
                   {"metrics": {"avg_fps": 200, "low_1_fps": 120, "samples": 10000}}]
        metrics = aggregate_metrics(records)
        self.assertEqual(metrics["avg_fps"], 150)
        self.assertEqual(metrics["low_1_fps"], 100)

    def test_missing_tail_measurement_is_not_partial_or_zero(self):
        records = [{"metrics": {"avg_fps": 100, "low_1_fps": 80}},
                   {"metrics": {"avg_fps": 100, "low_1_fps": None}}]
        self.assertIsNone(aggregate_metrics(records)["low_1_fps"])
        self.assertIsNone(aggregate_metrics([])["avg_fps"])
