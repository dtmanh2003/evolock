import json
from pathlib import Path
import tempfile
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from evolock.storage import config, tasks, history, activity_log, override_log, pw_log, json_file
from evolock.services import timer, blocker, gamification
from evolock.ui import app


class StorageTests(unittest.TestCase):
    def test_corrupt_files_are_not_reset(self):
        cases = [(config, 'CONFIG_FILE', config.Config), (tasks, 'TASKS_FILE', tasks.TaskManager),
                 (history, 'HISTORY_FILE', history.HistoryManager),
                 (activity_log, 'ACTIVITY_FILE', activity_log.ActivityLogger),
                 (override_log, 'OVERRIDE_FILE', override_log.OverrideLogger),
                 (pw_log, 'PW_LOG_FILE', pw_log.PasswordLogger),
                 (gamification, 'STATS_FILE', gamification.GameManager),
                 (blocker, 'BLOCKED_FILE', blocker.load_blocked_apps),
                 (blocker, 'WHITELIST_FILE', blocker.WhitelistManager)]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'data.json'
            for module, key, constructor in cases:
                for content in ('{broken', '[]'):
                    with self.subTest(key=key, content=content), patch.object(module, key, path):
                        path.write_text(content)
                        with self.assertRaises(json_file.DataFileError):
                            constructor()
                        self.assertEqual(path.read_text(), content)

    def test_failed_replace_preserves_original_and_backup(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'data.json'
            path.write_text('{"value": 1}')
            replace = json_file.os.replace
            def fail_destination(source, destination):
                if destination == path:
                    raise OSError('simulated disk failure')
                replace(source, destination)
            with patch.object(json_file.os, 'replace', side_effect=fail_destination):
                with self.assertRaises(json_file.DataFileError):
                    json_file.atomic_write_text(path, '{"value": 2}')
            self.assertEqual(json.loads(path.read_text()), {'value': 1})
            self.assertEqual(json.loads(path.with_name('data.json.bak').read_text()), {'value': 1})
            self.assertEqual(list(Path(d).glob('*.tmp')), [])

    def test_corruption_after_load_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as d, patch.object(config, 'CONFIG_FILE', Path(d)/'config.json'):
            cfg = config.Config()
            config.CONFIG_FILE.write_text('{broken')
            with self.assertRaises(json_file.DataFileError):
                cfg.set('daily_goal_minutes', 100)
            self.assertEqual(config.CONFIG_FILE.read_text(), '{broken')


class TimerTests(unittest.TestCase):
    def test_timer_rounds_up_and_finishes_at_deadline(self):
        ticks, done = [], MagicMock()
        obj = timer.CountdownTimer(2, ticks.append, done)
        obj.running = True
        with patch.object(timer.time, 'monotonic', side_effect=[0.01, 0.02, 1.0, 1.01, 2.0]), \
             patch.object(obj._cancel, 'wait'):
            obj._loop(obj._cancel, 2.0)
        self.assertEqual(ticks, [2, 1, 0])
        done.assert_called_once_with()

    def test_double_start_is_idempotent_and_restart_cancels_old_generation(self):
        obj = timer.CountdownTimer(60)
        with patch.object(timer.threading, 'Thread') as thread:
            obj.start()
            old = obj._cancel
            obj.start()
            self.assertEqual(thread.call_count, 1)
            obj.stop()
            obj.start()
            self.assertEqual(thread.call_count, 2)
            self.assertTrue(old.is_set())
            self.assertFalse(obj._cancel.is_set())
            obj.stop()

    def test_queued_callbacks_are_discarded_after_stop(self):
        queued = []
        done, tick = MagicMock(), MagicMock()
        obj = timer.CountdownTimer(0, tick, done, queued.append)
        with patch.object(timer.threading, 'Thread'):
            obj.start()
        obj._loop(obj._cancel, 0)
        self.assertEqual(len(queued), 2)
        obj.stop()
        for callback in queued:
            callback()
        done.assert_not_called()
        tick.assert_not_called()

    def test_completion_delivered_once(self):
        done, tick = MagicMock(), MagicMock()
        obj = timer.CountdownTimer(0, tick, done)
        with patch.object(timer.threading, 'Thread'):
            obj.start()
        obj._loop(obj._cancel, 0)
        done.assert_called_once_with()
        tick.assert_called_once_with(0)
        self.assertFalse(obj.running)


class AISettingsTests(unittest.TestCase):
    def test_preferences_persist_and_backend_changes_respect_them(self):
        with tempfile.TemporaryDirectory() as d, patch.object(config, 'CONFIG_FILE', Path(d)/'config.json'):
            cfg = config.Config()
            cfg.set('screen_enabled', False)
            cfg.set('smart_enabled', False)
            obj = app.EvoLockApp.__new__(app.EvoLockApp)
            obj.cfg = config.Config()
            obj.blocker = MagicMock(screen_ollama_model='vision-model', screen_api_key='')
            obj.screen_ai_var = MagicMock()
            obj._sync_screen_settings()
            self.assertFalse(obj.blocker.screen_enabled)
            self.assertFalse(obj.cfg.get('smart_enabled'))
            obj.cfg.set('screen_enabled', True)
            obj.cfg.set('screen_consent_destination', 'local')
            obj.api_key_var = MagicMock()
            obj.api_key_var.get.return_value = ''
            obj._log = MagicMock()
            obj._refresh_screen_ai_status = MagicMock()
            obj._save_api_key()
            self.assertTrue(obj.blocker.screen_enabled)
            obj.screen_ai_var.set.assert_called_with(True)
            obj.blocker.screen_ollama_model = ''
            obj._sync_screen_settings()
            self.assertFalse(obj.blocker.screen_enabled)


class DateWindowTests(unittest.TestCase):
    def test_all_logs_use_exact_calendar_window(self):
        cases = [(history.HistoryManager, 'sessions'), (activity_log.ActivityLogger, 'events'),
                 (override_log.OverrideLogger, 'records'), (pw_log.PasswordLogger, 'events')]
        entries = [SimpleNamespace(date=str(date.today() - timedelta(days=i))) for i in range(-1, 9)]
        for cls, field in cases:
            with self.subTest(manager=cls.__name__):
                obj = cls.__new__(cls)
                setattr(obj, field, entries)
                self.assertEqual(len(obj.last_n_days(7)), 7)
                self.assertEqual([e.date for e in obj.last_n_days(1)], [str(date.today())])
                self.assertEqual(obj.last_n_days(0), [])
                self.assertEqual(obj.last_n_days(-1), [])


if __name__ == '__main__':
    unittest.main()
