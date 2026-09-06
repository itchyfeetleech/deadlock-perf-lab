import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deadlock_perf_lab.runner import run_live, run_session, stop_owned, verify_assignments, wait_startup_replay
from deadlock_perf_lab.storage import LabError, read_json, write_json
from deadlock_perf_lab.planning import make_plan
from deadlock_perf_lab.workspace import initialize
from deadlock_perf_lab.vconsole import HEADER, VConsole
from tests.helpers import mangohud


class FakeConsole:
    def __init__(self, path, *args, **kwargs):
        self.path = path
        path.write_text("fake console\n")
    def close(self):
        pass
    def drain(self):
        pass
    def send(self, command):
        pass
    def read(self, timeout=0):
        return []
    def wait_for(self, phrase, timeout=0):
        return "sv_cheats = false" if "sv_cheats" in phrase else phrase
    def command_wait(self, command, phrase, timeout=0):
        return phrase
    def exchange(self, commands, timeout=5):
        for command in commands:
            self.send(command)
        return ["sv_cheats = false"] if "sv_cheats" in commands else []


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.install = self.root / "Steam/game-install"
        (self.install / "game/citadel/cfg").mkdir(parents=True)
        self.gi = self.install / "game/citadel/gameinfo.gi"
        self.gi.write_text('GameInfo { "game" "test" }')
        self.existing = self.install / "game/citadel/cfg/autoexec_dpl.cfg"
        self.existing.write_text("user's pre-existing lab file\n")
        replay = self.install / "game/citadel/replay.dem"
        replay.write_bytes(b"dummy local replay")
        initialize(self.workspace, str(self.install), str(replay))
        config = read_json(self.workspace / "lab.json")
        config["scenario"].update(sample_s=1, warmup_s=0, settle_s=0, cooldown_s=0, player="1")
        config["conditions"] = {"resolution":"1920x1080"}
        write_json(self.workspace / "lab.json", config)
        self.session, self.plan = make_plan(self.workspace, ["community-boot"], 1, 47, experimental=True)
        # Keep coverage of older frozen plans that start replay via VConsole.
        self.plan['context']['scenario']['replay_launch'] = 'console'
        self.item = self.plan["schedule"][1]
        self.directory = self.session / "runs/002-community-boot"
        self.directory.mkdir(parents=True)
        self.alive = {}
        self.env = patch.dict("os.environ", {"XDG_CACHE_HOME": str(self.root / "cache")})
        self.env.start()
        self.addCleanup(self.env.stop)

    def launch(self, args, **kwargs):
        self.launch_args = args
        self.run_capture_conf = (self.workspace / "capture.conf").read_bytes()
        self.alive[12345] = "987"
        mangohud(self.directory / "capture/deadlock_fixture.csv", [5.] * 1000)

    def stop(self, processes):
        self.assertEqual(processes, {12345:"987"})
        self.alive.clear()

    def test_real_runner_orchestration_restores_and_hashes_final_raw(self):
        original = self.gi.read_bytes()
        config = (self.workspace / "capture.conf").read_bytes()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch("deadlock_perf_lab.runner.game_processes", side_effect=lambda: dict(self.alive)))
            stack.enter_context(patch("deadlock_perf_lab.runner.subprocess.Popen", side_effect=self.launch))
            stack.enter_context(patch("deadlock_perf_lab.runner.VConsole", FakeConsole))
            stack.enter_context(patch("deadlock_perf_lab.runner.pause"))
            stack.enter_context(patch("deadlock_perf_lab.runner.last_elapsed", return_value=1))
            stack.enter_context(patch("deadlock_perf_lab.runner.stop_owned", side_effect=self.stop))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            result = run_live(self.workspace, self.session, self.plan, self.item, self.directory)
        self.assertTrue(all(v >= 0 for v in result["phase_timings_s"].values()))
        self.assertIn("shutdown", result["phase_timings_s"])
        self.assertIn("restore", result["phase_timings_s"])
        self.assertEqual(read_json(self.directory / "timings.json"), result["phase_timings_s"])
        self.assertEqual(result["metrics"]["avg_fps"], 200)
        self.assertEqual(self.gi.read_bytes(), original)
        self.assertEqual((self.workspace / "capture.conf").read_bytes(), config)
        self.assertEqual(self.existing.read_text(), "user's pre-existing lab file\n")
        self.assertIn("-insecure", self.launch_args)
        self.assertEqual(read_json(self.directory / "transaction.json")["state"], "restored")
        self.assertFalse(list((self.root / "cache").rglob("*.json")))

    def test_missing_capture_fails_and_restores_instead_of_generating_fps(self):
        original = self.gi.read_bytes()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch("deadlock_perf_lab.runner.game_processes", side_effect=lambda: dict(self.alive)))
            stack.enter_context(patch("deadlock_perf_lab.runner.subprocess.Popen", side_effect=self.launch))
            stack.enter_context(patch("deadlock_perf_lab.runner.VConsole", FakeConsole))
            stack.enter_context(patch("deadlock_perf_lab.runner.pause"))
            stack.enter_context(patch("deadlock_perf_lab.runner.capture_file", side_effect=LabError("missing capture")))
            stack.enter_context(patch("deadlock_perf_lab.runner.stop_owned", side_effect=self.stop))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            with self.assertRaisesRegex(LabError, "missing capture"):
                run_live(self.workspace, self.session, self.plan, self.item, self.directory)
        self.assertEqual(self.gi.read_bytes(), original)
        self.assertEqual(read_json(self.directory / "transaction.json")["state"], "restored")

    def test_existing_game_refused_before_any_write(self):
        with patch("deadlock_perf_lab.runner.game_processes", return_value={12345:"987"}):
            with self.assertRaisesRegex(LabError, "already running"):
                run_live(self.workspace, self.session, self.plan, self.item, self.directory)
        self.assertFalse((self.directory / "transaction.json").exists())

    def test_cancel_during_steam_launch_waits_for_late_game_before_restoring(self):
        checks = 0
        original = self.gi.read_bytes()

        def discover():
            nonlocal checks
            checks += 1
            if checks == 2:
                raise KeyboardInterrupt
            return dict(self.alive) if checks >= 4 else {}

        def stop(processes):
            self.assertNotEqual(self.gi.read_bytes(), original)
            self.stop(processes)

        with contextlib.ExitStack() as stack:
            stack.enter_context(patch('deadlock_perf_lab.runner.game_processes', side_effect=discover))
            stack.enter_context(patch('deadlock_perf_lab.runner.subprocess.Popen', side_effect=self.launch))
            stack.enter_context(patch('deadlock_perf_lab.runner.stop_owned', side_effect=stop))
            stack.enter_context(patch('deadlock_perf_lab.runner.time.sleep'))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            with self.assertRaises(KeyboardInterrupt):
                run_live(self.workspace, self.session, self.plan, self.item, self.directory)
        self.assertGreaterEqual(checks, 4)
        self.assertFalse(self.alive)
        self.assertEqual(self.gi.read_bytes(), original)
        self.assertEqual(read_json(self.directory / 'transaction.json')['state'], 'restored')

    def test_reused_pid_never_signaled(self):
        with patch("deadlock_perf_lab.runner.game_processes", return_value={12345:"NEW"}), patch("os.kill") as kill:
            stop_owned({12345:"OLD"})
        kill.assert_not_called()

    def test_cancellation_persists_failure_without_metrics(self):
        # Use a fresh session so the existing fixture run directory is irrelevant.
        session, _ = make_plan(self.workspace, ["fps-unlock"], 1, 47, demo=True)
        with patch("deadlock_perf_lab.runner.run_demo", side_effect=KeyboardInterrupt), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(KeyboardInterrupt):
                run_session(self.workspace, session)
        result = read_json(next((session / "runs").glob("*/result.json")))
        self.assertEqual(result["status"], "cancelled")
        self.assertNotIn("metrics", result)
        self.assertEqual(read_json(session / "status.json")["state"], "cancelled")

    def test_per_run_capture_keeps_display_for_autostart(self):
        # MangoHud 0.8.4 runs its autostart check inside the overlay update
        # path, which no_display skips until logging is already active: the
        # two combined mean logging never starts.
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch("deadlock_perf_lab.runner.game_processes", side_effect=lambda: dict(self.alive)))
            stack.enter_context(patch("deadlock_perf_lab.runner.subprocess.Popen", side_effect=self.launch))
            stack.enter_context(patch("deadlock_perf_lab.runner.VConsole", FakeConsole))
            stack.enter_context(patch("deadlock_perf_lab.runner.pause"))
            stack.enter_context(patch("deadlock_perf_lab.runner.last_elapsed", return_value=1))
            stack.enter_context(patch("deadlock_perf_lab.runner.stop_owned", side_effect=self.stop))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            run_live(self.workspace, self.session, self.plan, self.item, self.directory)
        self.assertIn(b"autostart_log=1", self.run_capture_conf)
        self.assertNotIn(b"no_display", self.run_capture_conf)

    def test_replay_waits_for_signon_before_first_seek(self):
        # Readiness must be an engine signal, not a blind fixed delay.
        events = []

        class RecordingConsole(FakeConsole):
            def wait_for(self, phrase, timeout=0):
                events.append(("wait", phrase))
                return super().wait_for(phrase, timeout)

            def send(self, command):
                events.append(("cmd", command))

            def command_wait(self, command, phrase, timeout=0):
                events.append(("cmd", command))
                return phrase

        def record_pause(seconds, console=None, processes=None):
            events.append(("pause", seconds))

        with contextlib.ExitStack() as stack:
            stack.enter_context(patch("deadlock_perf_lab.runner.game_processes", side_effect=lambda: dict(self.alive)))
            stack.enter_context(patch("deadlock_perf_lab.runner.subprocess.Popen", side_effect=self.launch))
            stack.enter_context(patch("deadlock_perf_lab.runner.VConsole", RecordingConsole))
            stack.enter_context(patch("deadlock_perf_lab.runner.pause", side_effect=record_pause))
            stack.enter_context(patch("deadlock_perf_lab.runner.last_elapsed", return_value=1))
            stack.enter_context(patch("deadlock_perf_lab.runner.stop_owned", side_effect=self.stop))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            run_live(self.workspace, self.session, self.plan, self.item, self.directory)
        playdemo_at = next(i for i, e in enumerate(events) if e[0] == "cmd" and e[1].startswith("playdemo"))
        seek_at = next(i for i, e in enumerate(events) if e[0] == "cmd" and e[1].startswith("demo_gototick"))
        settle_at = next(i for i, e in enumerate(events) if e == ("wait", 'Signon traffic "DEMO"'))
        self.assertLess(playdemo_at, settle_at)
        self.assertLess(settle_at, seek_at)
        self.assertNotIn(("pause", 20), events)

    def test_startup_replay_path_is_in_cfg_and_signon_precedes_seek(self):
        self.plan['context']['scenario']['replay_launch'] = 'startup'
        self.plan['context']['scenario']['replay_command'] = 'replays/a replay.dem'
        events = []

        def launch(args, **kwargs):
            self.launch(args, **kwargs)
            content = self.existing.read_text()
            self.assertIn('playdemo "replays/a replay.dem"', content)
            self.assertIn('echo DPL_REPLAY_', content)
            self.assertNotIn('+playdemo', args)

        class RecordingConsole(FakeConsole):
            def command_wait(self, command, phrase, timeout=0):
                events.append(command)
                return phrase

        with contextlib.ExitStack() as stack:
            stack.enter_context(patch('deadlock_perf_lab.runner.game_processes', side_effect=lambda: dict(self.alive)))
            stack.enter_context(patch('deadlock_perf_lab.runner.subprocess.Popen', side_effect=launch))
            stack.enter_context(patch('deadlock_perf_lab.runner.VConsole', RecordingConsole))
            stack.enter_context(patch('deadlock_perf_lab.runner.wait_startup_replay', side_effect=lambda *a: events.append('signon')))
            stack.enter_context(patch('deadlock_perf_lab.runner.pause'))
            stack.enter_context(patch('deadlock_perf_lab.runner.last_elapsed', return_value=1))
            stack.enter_context(patch('deadlock_perf_lab.runner.stop_owned', side_effect=self.stop))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            run_live(self.workspace, self.session, self.plan, self.item, self.directory)
        self.assertEqual(events[0], 'signon')
        self.assertTrue(events[1].startswith('demo_gototick'))
        self.assertFalse(any(e.startswith('playdemo') for e in events))


class ProtocolTests(unittest.TestCase):
    def test_startup_recovers_signon_from_current_marker_only(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as root:
            log = Path(root) / 'console.log'
            console = Mock(log=Path(root) / 'vconsole.log')
            console.read.return_value = []
            log.write_text('DPL_REPLAY_old\nplaying demo from old\nSignon traffic "DEMO"\n')
            def read(timeout):
                log.write_text(log.read_text() + 'DPL_REPLAY_new\nplaying demo from current\nSignon traffic "DEMO"\n')
                return []
            console.read.side_effect = read
            wait_startup_replay(console, log, 'DPL_REPLAY_new', timeout=1)
            self.assertIn('current', console.log.read_text())
            self.assertNotIn('playing demo from old', console.log.read_text())

    def test_stale_startup_signon_does_not_satisfy_current_launch(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as root:
            log = Path(root) / 'console.log'
            log.write_text('DPL_REPLAY_old\nplaying demo from old\nSignon traffic "DEMO"\n')
            console = Mock()
            console.read.return_value = ['Signon traffic "DEMO"']
            with self.assertRaisesRegex(LabError, 'signon'):
                wait_startup_replay(console, log, 'DPL_REPLAY_new', timeout=.01)

    def test_batch_readback_flags_missing_and_mismatched_values(self):
        from unittest.mock import Mock
        console = Mock()
        console.exchange.return_value = ['sv_cheats = false', 'fps_max = 120', 'r_shadows = true']
        blockers = verify_assignments(console, 'sv_cheats 0\nfps_max 144\nr_shadows 1\nhidden_cvar 0')
        self.assertEqual(len(blockers), 2)
        self.assertIn('requested 144, read back 120', blockers[0])
        self.assertIn('hidden_cvar: no readback', blockers[1])
        console.exchange.assert_called_once_with(['sv_cheats', 'fps_max', 'r_shadows', 'hidden_cvar'])

    def test_batch_transport_failure_is_not_treated_as_hidden_cvar(self):
        from unittest.mock import Mock
        console = Mock()
        console.exchange.side_effect = LabError('missing barrier')
        with self.assertRaisesRegex(LabError, 'missing barrier'):
            verify_assignments(console, 'hidden_cvar 0')

    def test_exchange_waits_for_unique_barrier_not_stale_echo(self):
        from unittest.mock import Mock
        client = object.__new__(VConsole)
        client.drain = Mock()
        commands = []
        client.send = commands.append
        def read(timeout):
            return ['DPL_ACK_stale', 'fps_max = 144', commands[-1].removeprefix('echo ')]
        client.read = read
        self.assertEqual(client.exchange(['hidden_cvar', 'fps_max']), ['DPL_ACK_stale', 'fps_max = 144'])
        self.assertEqual(commands[:2], ['hidden_cvar', 'fps_max'])
        self.assertTrue(commands[-1].startswith('echo DPL_ACK_'))
        client.drain.assert_called_once()

    def test_exchange_missing_barrier_fails(self):
        from unittest.mock import Mock
        client = object.__new__(VConsole)
        client.drain, client.send, client.read = Mock(), Mock(), Mock(return_value=[])
        with self.assertRaisesRegex(LabError, 'acknowledge'):
            client.exchange(['fps_max'], timeout=0)

    def test_fragmented_tcp_packets_are_reassembled(self):
        import socket
        with tempfile.TemporaryDirectory() as root:
            left, right = socket.socketpair()
            self.addCleanup(left.close)
            self.addCleanup(right.close)
            client = object.__new__(VConsole)
            client.socket = left
            client.buffer = bytearray()
            client.messages = []
            client.log = Path(root) / "console.log"
            body = b"\0" * 28 + b"fps_max = 144\0"
            packet = HEADER.pack(b"PRNT", 0, HEADER.size + len(body), 0) + body
            right.sendall(packet[:8])
            self.assertEqual(client.read(0), [])
            right.sendall(packet[8:])
            self.assertEqual(client.read(0), ["fps_max = 144"])

    def test_protocol_rejects_short_header_length(self):
        import socket
        with tempfile.TemporaryDirectory() as root:
            left, right = socket.socketpair()
            self.addCleanup(left.close)
            self.addCleanup(right.close)
            client = object.__new__(VConsole)
            client.socket, client.buffer, client.messages = left, bytearray(), []
            client.log = Path(root) / "log"
            right.sendall(HEADER.pack(b"PRNT", 0, 2, 0))
            with self.assertRaisesRegex(LabError, "packet size"):
                client.read(0)
