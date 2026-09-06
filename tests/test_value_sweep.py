from collections import Counter
from pathlib import Path
import tempfile
import unittest

from deadlock_perf_lab.storage import read_json
from deadlock_perf_lab.workspace import initialize
from scripts.prepare_value_sweep import prepare


class ValueSweepTests(unittest.TestCase):
    def test_schedule_has_unique_indices_and_reuses_identical_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install = root / 'game'
            citadel = install / 'game/citadel'
            citadel.mkdir(parents=True)
            (citadel / 'gameinfo.gi').write_text('GameInfo { ConVars { foo 1 bar 2 } }')
            (citadel / 'replay.dem').write_bytes(b'fixture')
            workspace = root / 'workspace'
            initialize(workspace, str(install), 'replay.dem')
            matrix = root / 'matrix.csv'
            matrix.write_text('id,cvar,value\nvalue-a,foo,3\nvalue-b,bar,4\n')
            for _ in range(2):
                session = prepare(workspace, matrix)
                plan = read_json(session / 'plan.json')
                self.assertEqual([i['index'] for i in plan['schedule']], list(range(1, 10)))
                self.assertEqual(Counter(i['case'] for i in plan['schedule']),
                                 {'baseline': 3, 'value-a': 3, 'value-b': 3})
                for number in range(1, 4):
                    cases = [i['case'] for i in plan['schedule'] if i['round'] == number]
                    self.assertEqual(cases[number - 1], 'baseline')
                    self.assertEqual(set(cases), {'baseline', 'value-a', 'value-b'})
                self.assertEqual(read_json(session / 'status.json')['state'], 'planned')
            self.assertEqual((citadel / 'gameinfo.gi').read_text(), 'GameInfo { ConVars { foo 1 bar 2 } }')
