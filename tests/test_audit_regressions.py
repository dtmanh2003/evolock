"""Regression coverage for the seven findings in the 2026-11-13 audit.

All processes, AI and GUI objects are fake. Storage/lock checks use temp files.
"""
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

from evolock import paths
from evolock.integrations import instance, watchdog
from evolock.services import blocker, gamification
from evolock.storage import config, history
from evolock.ui import app


def fake_blocker():
    obj = blocker.Blocker.__new__(blocker.Blocker)
    obj.running = True
    obj._lock = threading.Lock()
    obj._stop_event = threading.Event()
    obj._thread = None
    obj._cached_blocked = ['chrome.exe', 'example.exe']
    obj.smart_enabled = False
    obj.screen_enabled = False
    obj.screen_ollama_model = ''
    obj.screen_api_key = ''
    obj.screen = MagicMock(consecutive_errors=0, verdict='ok')
    obj.screen.classify.return_value = (True, 'study')
    obj.smart = MagicMock(ready=True)
    obj.whitelist = MagicMock()
    obj.whitelist.is_whitelisted.return_value = False
    obj.on_kill_callback = MagicMock()
    obj.on_allow_callback = MagicMock()
    obj._title_laziness = {}
    return obj


def fake_app():
    obj = app.EvoLockApp.__new__(app.EvoLockApp)
    for name in ('root', 'cfg', 'blocker', 'study_timer', 'unlock_timer',
                 'status_var', 'status_label', 'timer_var', 'timer_label',
                 'btn_main', 'settings_msg', '_reset_timers', '_log',
                 '_refresh_blocked_list', '_refresh_history_display',
                 '_record_study_session', '_run_analysis'):
        setattr(obj, name, MagicMock())
    obj._get_unlock_seconds = lambda: 60
    obj._get_study_seconds = lambda: 60
    obj._tray_icon = None
    obj._unlock_started_at = None
    obj._study_started_at = None
    return obj


class BlockerRegressionTests(unittest.TestCase):
    def scan(self, obj, process, titles=None):
        event = obj._stop_event
        with patch.object(blocker, 'get_pid_to_title', return_value=titles or {}), \
             patch.object(blocker.psutil, 'process_iter', return_value=[process]), \
             patch.object(event, 'wait', side_effect=lambda _: event.set()):
            obj._loop(event)

    def test_both_ai_disabled_enforces_browser_blocklist(self):
        obj = fake_blocker()
        process = MagicMock(info={'name': 'chrome.exe', 'pid': 123})
        self.scan(obj, process)
        process.kill.assert_called_once_with()

    def test_failed_screen_with_smart_disabled_falls_back_to_blocklist(self):
        obj = fake_blocker()
        obj.screen_enabled = True
        obj.screen_ollama_model = 'fake-model'
        obj.screen.consecutive_errors = blocker.ScreenClassifier.ERROR_FALLBACK_THRESHOLD
        process = MagicMock(info={'name': 'chrome.exe', 'pid': 123})
        self.scan(obj, process)
        process.kill.assert_called_once_with()

    def test_working_screen_study_verdict_still_allows_browser(self):
        obj = fake_blocker()
        obj.screen_enabled = True
        obj.screen_ollama_model = 'fake-model'
        process = MagicMock(info={'name': 'chrome.exe', 'pid': 123})
        self.scan(obj, process)
        process.kill.assert_not_called()

    def test_smart_reference_exception_still_allowed(self):
        obj = fake_blocker()
        obj.smart_enabled = True
        process = MagicMock(info={'name': 'chrome.exe', 'pid': 123})
        self.scan(obj, process, {123: 'Python - Stack Overflow'})
        process.kill.assert_not_called()

    def test_unlisted_and_unnamed_processes_are_ignored(self):
        for name in ('unlisted.exe', None):
            with self.subTest(name=name):
                process = MagicMock(info={'name': name, 'pid': 123})
                self.scan(fake_blocker(), process)
                process.kill.assert_not_called()

    def test_stop_during_classification_prevents_kill(self):
        obj = fake_blocker()
        obj.smart_enabled = True
        obj._get_title_tracker('chrome.exe').score = 60
        def classify(_):
            obj.stop()
            return False, 0, 1
        obj.smart.is_study.side_effect = classify
        process = MagicMock(info={'name': 'chrome.exe', 'pid': 123})
        self.scan(obj, process, {123: 'Game video'})
        process.kill.assert_not_called()
        obj.on_kill_callback.assert_not_called()

    def test_removed_app_cannot_be_killed_from_stale_scan(self):
        obj = fake_blocker()
        process = MagicMock(info={'name': 'chrome.exe', 'pid': 123})
        obj._cached_blocked = []
        self.assertFalse(obj._kill_if_active(process, obj._stop_event))
        process.kill.assert_not_called()

    def test_restart_cannot_revive_old_inflight_scan(self):
        obj = fake_blocker()
        obj.smart_enabled = True
        obj._get_title_tracker('chrome.exe').score = 60
        old_event = obj._stop_event
        entered, release = threading.Event(), threading.Event()
        def classify(_):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test synchronization timed out')
            return False, 0, 1
        obj.smart.is_study.side_effect = classify
        process = MagicMock(info={'name': 'chrome.exe', 'pid': 123})
        with patch.object(blocker, 'get_pid_to_title', return_value={123: 'Game video'}), \
             patch.object(blocker.psutil, 'process_iter', return_value=[process]):
            worker = threading.Thread(target=obj._loop, args=(old_event,), daemon=True)
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                obj.stop()
                with patch.object(blocker.threading, 'Thread') as new_thread:
                    obj.start()
                self.assertIsNot(old_event, obj._stop_event)
                self.assertTrue(old_event.is_set())
                self.assertFalse(obj._stop_event.is_set())
                new_thread.return_value.start.assert_called_once_with()
            finally:
                release.set()
                worker.join(5)
                obj.stop()
        self.assertFalse(worker.is_alive())
        process.kill.assert_not_called()


class SessionRegressionTests(unittest.TestCase):
    def test_blocklist_removal_requires_authorization_in_protected_states(self):
        for state in ('studying', 'locked'):
            for authorized in (False, True):
                with self.subTest(state=state, authorized=authorized):
                    obj = fake_app()
                    obj.state = state
                    obj._check_override = MagicMock(return_value=authorized)
                    with patch.object(app, 'load_blocked_apps', return_value=['example.exe']), \
                         patch.object(app, 'save_blocked_apps') as save:
                        obj._remove_blocked_app('example.exe')
                    obj._check_override.assert_called_once_with(action='manage_blocklist')
                    self.assertEqual(save.call_count, int(authorized))
                    self.assertEqual(obj.blocker.reload_blocked_apps.call_count, int(authorized))

    def test_idle_blocklist_can_be_edited(self):
        obj = fake_app()
        obj.state = 'idle'
        obj._check_override = MagicMock()
        with patch.object(app, 'load_blocked_apps', return_value=['example.exe']), \
             patch.object(app, 'save_blocked_apps') as save:
            obj._remove_blocked_app('example.exe')
        save.assert_called_once_with([])
        obj._check_override.assert_not_called()

    def test_management_code_does_not_consume_session_or_log_false_stop(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(config, 'CONFIG_FILE', Path(directory) / 'config.json'):
            obj = fake_app()
            obj.cfg = config.Config()
            obj.cfg.set_session_code('123456')
            obj.override_log = MagicMock()
            with patch.object(app, 'ask_override', return_value={'code': '123456'}):
                self.assertTrue(obj._check_override('manage_blocklist'))
            self.assertTrue(obj.cfg.verify_session_code('123456'))
            obj.override_log.log.assert_not_called()

    def test_invalid_management_code_denied(self):
        obj = fake_app()
        obj.cfg.verify_session_code.return_value = False
        with patch.object(app, 'ask_override', return_value={'code': 'invalid'}), \
             patch.object(app.messagebox, 'showerror'):
            self.assertFalse(obj._check_override('manage_blocklist'))
        obj.cfg.clear_session_code.assert_not_called()

    def test_local_management_uses_password(self):
        obj = fake_app()
        obj.cfg.get.return_value = ''
        obj._check_password = MagicMock(return_value=False)
        self.assertFalse(obj._check_override('manage_blocklist'))
        obj._check_password.assert_called_once_with('manage_blocklist')

    def test_resuming_study_closes_play_interval_once(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(history, 'HISTORY_FILE', Path(directory) / 'history.json'):
            obj = fake_app()
            obj.history = history.HistoryManager()
            obj._unlock_started_at = datetime.now() - timedelta(minutes=10)
            obj._begin_studying_state(60)
            self.assertIsNone(obj._unlock_started_at)
            obj._record_play_session()
            self.assertEqual(len(obj.history.sessions), 1)
            self.assertEqual(obj.history.sessions[0].session_type, 'play')
            self.assertEqual(obj.history.sessions[0].duration_minutes, 10)

    def test_task_unlock_closes_previous_play_interval_before_restarting(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(history, 'HISTORY_FILE', Path(directory) / 'history.json'):
            obj = fake_app()
            obj.history = history.HistoryManager()
            previous = datetime.now() - timedelta(minutes=10)
            obj._unlock_started_at = previous
            obj._enter_unlocked()
            self.assertGreater(obj._unlock_started_at, previous)
            self.assertEqual(len(obj.history.sessions), 1)
            self.assertEqual(obj.history.sessions[0].duration_minutes, 10)


class DayRolloverTests(unittest.TestCase):
    def test_idle_ui_refreshes_at_day_change_only(self):
        obj = fake_app()
        obj.game = SimpleNamespace(stats=SimpleNamespace(today_date=str(date.today() - timedelta(days=1))))
        obj._refresh_stats = MagicMock()
        obj._refresh_day()
        obj._refresh_stats.assert_called_once_with()
        obj._refresh_history_display.assert_called_once_with()
        obj.game.stats.today_date = str(date.today())
        obj._refresh_day()
        self.assertEqual(obj._refresh_stats.call_count, 1)

    def test_new_day_resets_minutes_before_study_and_task_rewards(self):
        for action in ('study', 'task'):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as directory, \
                 patch.object(gamification, 'STATS_FILE', Path(directory) / 'stats.json'), \
                 patch.object(gamification, 'date', wraps=date) as clock:
                clock.today.return_value = date(2026, 11, 12)
                game = gamification.GameManager()
                game.on_study_complete(50)
                clock.today.return_value = date(2026, 11, 13)
                if action == 'study':
                    result = game.on_study_complete(10)
                else:
                    result = game.on_task_complete()
                self.assertEqual(game.stats.today_date, '2026-11-13')
                self.assertEqual(game.stats.today_study_minutes, 10 if action == 'study' else 0)
                self.assertNotIn('study_60min', game.stats.unlocked_achievements)
                self.assertEqual(game.stats.streak, 2)
                self.assertEqual(result['checkin_exp'], 10)
                self.assertEqual(game.on_task_complete()['checkin_exp'], 0)
                self.assertEqual(gamification.GameManager().stats.today_date, '2026-11-13')


class InstanceAndWatchdogTests(unittest.TestCase):
    def test_lock_rejects_second_process_then_allows_after_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'instance.lock'
            owner = instance.InstanceLock(path)
            env = dict(os.environ, PYTHONPATH=str(paths.PROJECT_ROOT))
            code = ('from pathlib import Path; import sys; '
                    'from evolock.integrations.instance import InstanceLock; '
                    'guard=InstanceLock(Path(sys.argv[1])); print(guard.acquire())')
            self.assertTrue(owner.acquire())
            try:
                result = subprocess.run([sys.executable, '-B', '-c', code, str(path)],
                                        env=env, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), 'False')
            finally:
                owner.release()
            result = subprocess.run([sys.executable, '-B', '-c', code, str(path)],
                                    env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'True')
            # Child exits without explicit release: Windows releases its handle.
            self.assertTrue(owner.acquire())
            owner.release()

    def test_duplicate_gui_never_initializes_data_managers(self):
        with patch.object(app, 'InstanceLock') as guard, patch.object(app.tk, 'Tk'), \
             patch.object(app, 'EvoLockApp') as gui, patch.object(app.messagebox, 'showinfo'):
            guard.return_value.acquire.return_value = False
            app.main()
            gui.assert_not_called()

    def test_gui_initialization_failure_releases_instance(self):
        with patch.object(app, 'InstanceLock') as guard, patch.object(app.tk, 'Tk'), \
             patch.object(app, 'EvoLockApp', side_effect=RuntimeError('fixture')):
            guard.return_value.acquire.return_value = True
            with self.assertRaises(RuntimeError):
                app.main()
            guard.return_value.release.assert_called_once_with()

    def test_watchdog_detects_module_script_flags_and_relative_paths(self):
        cases = [
            ([sys.executable, '-m', 'evolock'], paths.PROJECT_ROOT, True),
            ([sys.executable, '-B', '-m', 'evolock'], paths.PROJECT_ROOT, True),
            ([sys.executable, '-X', 'utf8', '-m', 'evolock'], paths.PROJECT_ROOT, True),
            ([sys.executable, str(paths.MAIN_SCRIPT)], paths.PROJECT_ROOT.parent, True),
            ([sys.executable, '-B', 'main.py'], paths.PROJECT_ROOT, True),
            ([sys.executable, 'main.py'], paths.PROJECT_ROOT.parent, False),
            ([sys.executable, '-m', 'evolock'], paths.PROJECT_ROOT.parent, False),
            ([sys.executable, '-c', 'print(1)', str(paths.MAIN_SCRIPT)], paths.PROJECT_ROOT, False),
        ]
        for command, cwd, expected in cases:
            with self.subTest(command=command, cwd=cwd):
                proc = SimpleNamespace(info={'cmdline': command}, cwd=lambda: str(cwd))
                with patch.object(watchdog, 'is_instance_running', return_value=False), \
                     patch.object(watchdog.psutil, 'process_iter', return_value=[proc]):
                    self.assertEqual(watchdog._is_running(), expected)

    def test_watchdog_prefers_live_instance_lock(self):
        with patch.object(watchdog, 'is_instance_running', return_value=True), \
             patch.object(watchdog.psutil, 'process_iter') as processes:
            self.assertTrue(watchdog._is_running())
            processes.assert_not_called()


if __name__ == '__main__':
    unittest.main()
