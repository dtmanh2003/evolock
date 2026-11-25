"""Regression checks for package imports, entry points, and relocated data.

All write checks use temporary files; no user settings or credentials are changed.
"""

import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from evolock import paths
from evolock.integrations import protection, watchdog
from evolock.services import blocker, gamification
from evolock.storage import activity_log, config, history, override_log, pw_log, tasks


class ProjectStructureTests(unittest.TestCase):
    def test_imports_work_outside_project_directory(self):
        env = dict(os.environ, PYTHONPATH=str(paths.PROJECT_ROOT), PYTHONDONTWRITEBYTECODE="1")
        code = (
            "from evolock.ui.app import EvoLockApp; "
            "from evolock.services.timer import CountdownTimer; "
            "from evolock.integrations.watchdog import MAIN; "
            "from evolock.paths import MAIN_SCRIPT; "
            "assert MAIN == str(MAIN_SCRIPT)"
        )
        with tempfile.TemporaryDirectory() as cwd:
            result = subprocess.run(
                [sys.executable, "-c", code], cwd=cwd, env=env,
                capture_output=True, text=True, timeout=30,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_launchers_delegate_without_starting_gui_or_watchdog(self):
        with patch("evolock.ui.app.main") as launch:
            runpy.run_path(str(paths.MAIN_SCRIPT), run_name="__main__")
            launch.assert_called_once_with()
        with patch("evolock.ui.app.main") as launch:
            runpy.run_module("evolock.__main__", run_name="__main__")
            launch.assert_called_once_with()
        with patch("evolock.integrations.watchdog.main") as launch:
            runpy.run_path(str(paths.PROJECT_ROOT / "watchdog.py"), run_name="__main__")
            launch.assert_called_once_with()

    def test_data_and_asset_paths_are_centralized(self):
        files = [
            config.CONFIG_FILE, tasks.TASKS_FILE, history.HISTORY_FILE,
            gamification.STATS_FILE, activity_log.ACTIVITY_FILE,
            override_log.OVERRIDE_FILE, pw_log.PW_LOG_FILE,
            blocker.BLOCKED_FILE, blocker.WHITELIST_FILE,
        ]
        for file in files:
            with self.subTest(file=file.name):
                self.assertEqual(file.parent, paths.DATA_DIR)
                self.assertTrue(file.is_absolute())
        self.assertTrue(paths.MASCOT_FRAMES_DIR.is_dir())
        self.assertTrue(list(paths.MASCOT_FRAMES_DIR.glob("anim*_*.png")))
        self.assertEqual(
            protection._startup_cmd(), f'"{sys.executable}" "{paths.MAIN_SCRIPT}"',
        )
        self.assertEqual(watchdog.MAIN_ABS, str(paths.MAIN_SCRIPT))

    def test_configuration_and_tasks_round_trip_in_isolated_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(config, "CONFIG_FILE", Path(directory) / "config.json"):
                cfg = config.Config()
                cfg.set_password("test-password")
                cfg.set_session_code("123456")
                loaded = config.Config()
                self.assertTrue(loaded.verify_password("test-password"))
                self.assertFalse(loaded.verify_password("incorrect"))
                self.assertTrue(loaded.verify_session_code("123456"))
                loaded.clear_session_code()
                self.assertFalse(config.Config().verify_session_code("123456"))
            with patch.object(tasks, "TASKS_FILE", Path(directory) / "tasks.json"):
                manager = tasks.TaskManager()
                task = manager.add("Read a chapter", tasks.TASK_TYPES[0])
                manager.complete(task.id)
                loaded = tasks.TaskManager()
                self.assertEqual(len(loaded.tasks), 1)
                self.assertTrue(loaded.tasks[0].completed)

    def test_history_stats_and_logs_round_trip_in_isolated_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(history, "HISTORY_FILE", root / "history.json"):
                end = datetime.now()
                history.HistoryManager().log("study", end - timedelta(minutes=10), end)
                self.assertEqual(history.HistoryManager().today_study_minutes(), 10)
            with patch.object(gamification, "STATS_FILE", root / "stats.json"):
                gamification.GameManager().on_study_complete(10)
                self.assertEqual(gamification.GameManager().stats.total_study_minutes, 10)
            with patch.object(activity_log, "ACTIVITY_FILE", root / "activity_log.json"):
                activity_log.ActivityLogger().log("warn", "example.exe", "test")
                self.assertEqual(activity_log.ActivityLogger().events[0].kind, "warn")
            with patch.object(override_log, "OVERRIDE_FILE", root / "overrides.json"):
                override_log.OverrideLogger().log("test", "note", 30, 10)
                self.assertEqual(override_log.OverrideLogger().records[0].actual_minutes, 10)
            with patch.object(pw_log, "PW_LOG_FILE", root / "pw_log.json"):
                pw_log.PasswordLogger().log("password", "stop_study")
                self.assertEqual(pw_log.PasswordLogger().summary()["total_password_stops"], 1)

    def test_blocklist_and_whitelist_round_trip_in_isolated_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(blocker, "BLOCKED_FILE", root / "blocked.json"):
                blocker.save_blocked_apps(["example.exe", "EXAMPLE.exe", ""])
                self.assertEqual(blocker.load_blocked_apps(), ["example.exe"])
            with patch.object(blocker, "WHITELIST_FILE", root / "whitelist.json"):
                manager = blocker.WhitelistManager()
                manager.add("Example Learning Channel")
                self.assertTrue(blocker.WhitelistManager().is_whitelisted("Example Learning Channel"))


if __name__ == "__main__":
    unittest.main()
