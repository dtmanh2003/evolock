import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from evolock.storage import config, tasks
from evolock.ui.app import EvoLockApp
from evolock.services import blocker
from test_audit_regressions import fake_blocker


class StorageTests(unittest.TestCase):
    def test_failed_save_restores_config_and_task_ids(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(config, 'CONFIG_FILE', Path(tmp) / 'config.json'), \
             patch.object(tasks, 'TASKS_FILE', Path(tmp) / 'tasks.json'):
            cfg = config.Config()
            cfg.set('daily_goal_minutes', 60)
            with patch.object(config, 'atomic_write_text', side_effect=OSError):
                with self.assertRaises(OSError):
                    cfg.set('daily_goal_minutes', 90)
            self.assertEqual(cfg.get('daily_goal_minutes'), 60)
            manager = tasks.TaskManager()
            first = manager.add('Example', 'study')
            with patch.object(tasks, 'atomic_write_text', side_effect=OSError):
                with self.assertRaises(OSError):
                    manager.complete(first.id)
                self.assertFalse(manager.tasks[0].completed)
                with self.assertRaises(OSError):
                    manager.add('Failed', 'study')
            self.assertEqual(manager.add('Next', 'study').id, 2)
            self.assertEqual(len(manager.tasks), 2)

    def test_invalid_json_fields_are_rejected_without_rewriting(self):
        for data in ({'tasks': ''}, {'tasks': [{'id': 'bad', 'name': 'X', 'task_type': 'study'}]},
                     {'tasks': [{'id': 1, 'name': 'X', 'task_type': 'study', 'completed': 'false'}]}):
            with self.subTest(data=data), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'tasks.json'
                text = json.dumps(data)
                path.write_text(text)
                with patch.object(tasks, 'TASKS_FILE', path), self.assertRaises((ValueError, RuntimeError)):
                    tasks.TaskManager()
                self.assertEqual(path.read_text(), text)


class CoachTests(unittest.TestCase):
    def make_app(self):
        obj = EvoLockApp.__new__(EvoLockApp)
        for name in ('cfg', 'coach_btn', '_set_coach_text', 'coach_time_var', 'root', '_log', 'nb'):
            setattr(obj, name, MagicMock())
        return obj

    def test_busy_manual_does_not_start_another_request(self):
        obj = self.make_app()
        obj._coach_busy = True
        with patch('evolock.ui.app.threading.Thread') as thread:
            obj._run_analysis()
        thread.assert_not_called()

    def test_preparation_failure_releases_button_and_keeps_cache(self):
        obj = self.make_app()
        obj.cfg.get.side_effect = RuntimeError('private details')
        obj._run_analysis()
        self.assertFalse(obj._coach_busy)
        obj.cfg.set_many.assert_not_called()
        obj.coach_btn.config.assert_called_with(state='normal', text='今すぐ分析')

    def test_save_failure_releases_busy_and_auto_does_not_switch_tab(self):
        obj = self.make_app()
        obj._coach_busy = True
        obj.cfg.set_many.side_effect = OSError
        obj._finish_analysis('Result', auto=True)
        self.assertFalse(obj._coach_busy)
        obj.nb.select.assert_not_called()

    def test_automatic_requests_coalesce(self):
        obj = self.make_app()
        obj._coach_busy = True
        obj._run_analysis(auto=True)
        obj._run_analysis(auto=True)
        with patch.object(obj, '_run_analysis') as run:
            obj._finish_analysis('Result')
        run.assert_called_once_with(auto=True)

    def test_backend_exception_is_reported_and_releases_busy(self):
        obj = self.make_app()
        for name in ('history', 'pw_logger', 'task_mgr', 'game', 'activity_log', 'override_log'):
            setattr(obj, name, MagicMock())
        obj.history.sessions = []
        obj.cfg.get.return_value = ''
        obj.root.after.side_effect = lambda delay, callback: callback()
        with patch('evolock.ui.app.threading.Thread') as thread, \
             patch('evolock.ui.app.ai_coach.analyze', side_effect=RuntimeError) as analyze:
            thread.return_value.start.side_effect = lambda: thread.call_args.kwargs['target']()
            obj._run_analysis()
            analyze.assert_called_once()
        self.assertFalse(obj._coach_busy)
        obj.cfg.set_many.assert_not_called()


class BrowserTests(unittest.TestCase):
    def test_titleless_browser_root_is_blocked_but_renderer_is_not(self):
        for args, expected in [(['chrome.exe'], True), (['chrome.exe', '--type=renderer'], False)]:
            obj = fake_blocker()
            obj.smart_enabled = True
            proc = MagicMock(info={'name': 'chrome.exe', 'pid': 123})
            proc.cmdline.return_value = args
            event = obj._stop_event
            with patch.object(blocker, 'get_pid_to_title', return_value={}), \
                 patch.object(blocker.psutil, 'process_iter', return_value=[proc]), \
                 patch.object(event, 'wait', side_effect=lambda _: event.set()):
                obj._loop(event)
            self.assertEqual(proc.kill.called, expected)
