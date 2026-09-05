import unittest

from deadlock_perf_lab.storage import LabError
from deadlock_perf_lab.sweep import variants

BASE = '''GameInfo {
Other { fps_max "999" }
ConVars {
    fps_max "144" // retain this comment
    some_flag "true"
}
}'''


class SweepTests(unittest.TestCase):
    def test_changes_only_the_requested_section(self):
        result = variants(BASE, [{"id":"cap-test","cvar":"fps_max","value":"165"}])[0]
        self.assertEqual(result["content"], BASE.replace('fps_max "144"', 'fps_max "165"'))
        self.assertEqual(result["base_value"], "144")

    def test_adds_unset_convar_inside_block(self):
        result = variants(BASE, [{"id":"distance","cvar":"r_farz","value":"6000"}])[0]
        self.assertIn('r_farz "6000"', result["content"])
        self.assertEqual(result["base_value"], None)

    def test_noop_and_boolean_alias_noop_rejected(self):
        for cvar, value in (("fps_max", "144.0"), ("some_flag", "1")):
            with self.assertRaisesRegex(LabError, "unchanged config"):
                variants(BASE, [{"id":"noop","cvar":cvar,"value":value}])

    def test_duplicate_definition_rejected(self):
        with self.assertRaisesRegex(LabError, "multiple times"):
            variants(BASE.replace('some_flag "true"', 'fps_max "240"'), [{"id":"duplicate","cvar":"fps_max","value":"165"}])

    def test_command_injection_rejected(self):
        with self.assertRaises(LabError):
            variants(BASE, [{"id":"bad","cvar":"fps_max","value":"0; connect example"}])
