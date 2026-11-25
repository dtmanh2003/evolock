"""Tích hợp: dựng cả EvoLockApp thật (Tk thật, dữ liệu tạm) và chạy các luồng chính.

An toàn: Blocker bị thay bằng mock (không bao giờ đóng tiến trình thật), không có khay hệ
thống, không gửi mail/gọi AI thật, mọi file dữ liệu trỏ vào thư mục tạm.
"""

import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from evolock import i18n
from evolock.integrations import session_code
from evolock.services import blocker as blocker_module
from evolock.services import gamification
from evolock.storage import (activity_log, config, history, override_log, pw_log, site_labels, tasks)
from evolock.ui import app

DATA_FILES = [
    (blocker_module, "BLOCKED_FILE", "blocked.json"),
    (blocker_module, "WHITELIST_FILE", "whitelist.json"),
    (gamification, "STATS_FILE", "stats.json"),
    (activity_log, "ACTIVITY_FILE", "activity_log.json"),
    (config, "CONFIG_FILE", "config.json"),
    (history, "HISTORY_FILE", "history.json"),
    (override_log, "OVERRIDE_FILE", "overrides.json"),
    (pw_log, "PW_LOG_FILE", "pw_log.json"),
    (tasks, "TASKS_FILE", "tasks.json"),
    (site_labels, "LABELS_FILE", "site_labels.json"),
]


class AppIntegrationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        for module, name, filename in DATA_FILES:
            patcher = patch.object(module, name, Path(directory.name) / filename)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(i18n.set_language, "ja")

        self.blocker = MagicMock()
        self.blocker.screen_enabled = False
        self.blocker.screen_ollama_model = ""
        self.blocker.screen_api_key = ""
        self.blocker.labels = site_labels.SiteLabels()
        for target, value in (("Blocker", MagicMock(return_value=self.blocker)),
                              ("TRAY_AVAILABLE", False), ("MASCOT_AVAILABLE", False),
                              ("is_in_startup", MagicMock(return_value=False)),
                              ("load_blocked_apps", MagicMock(return_value=[]))):
            patcher = patch.object(app, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable: {exc}")
        self.root.geometry("640x820+6000+0")  # ngoài màn hình
        self.addCleanup(self._close)
        self.ui = app.EvoLockApp(self.root)

    def _close(self):
        for timer in (self.ui.study_timer, self.ui.unlock_timer):
            if timer:
                timer.stop()
        self.root.update()  # xử lý nốt các callback đồng hồ đang chờ trước khi đóng
        self.root.destroy()

    def pump(self, until, timeout=6.0):
        """Chạy vòng lặp chính của Tk như app thật (luồng nền gọi root.after cần mainloop)
        cho tới khi `until()` đúng hoặc hết thời gian."""
        deadline = time.monotonic() + timeout

        def check():
            if until() or time.monotonic() > deadline:
                self.root.quit()
            else:
                self.root.after(20, check)

        self.root.after(0, check)
        self.root.mainloop()
        return until()

    # ── Dựng giao diện ──────────────────────────────────────────────
    def test_all_five_tabs_are_built(self):
        self.assertEqual(len(self.ui.nb.tabs()), 5)
        self.assertEqual(self.ui.state, "idle")

    def test_every_tab_can_be_selected_and_drawn(self):
        for index in range(5):
            self.ui.nb.select(index)
            self.root.update()

    # ── Nhiệm vụ ────────────────────────────────────────────────────
    def test_adding_and_completing_a_task_unlocks_and_awards_exp(self):
        self.ui.task_name_var.set("英語")
        self.ui._add_task()
        self.assertEqual([t.name for t in self.ui.task_mgr.pending()], ["英語"])
        task = self.ui.task_mgr.pending()[0]
        with patch.object(app.messagebox, "askyesno", return_value=True):
            self.ui._confirm_complete(task.id, task.name)
        self.assertEqual(self.ui.task_mgr.pending(), [])
        self.assertEqual(self.ui.state, "unlocked")
        self.assertGreater(self.ui.game.stats.exp + self.ui.game.stats.level, 1)

    # ── Phiên học ───────────────────────────────────────────────────
    def test_study_session_runs_ticks_the_progress_bar_and_stops(self):
        self.ui.study_min_var.set("1")
        self.ui.unlock_min_var.set("1")
        self.ui._on_main_btn()
        self.assertEqual(self.ui.state, "studying")
        self.blocker.start.assert_called_once()
        self.assertTrue(self.pump(lambda: self.ui.session_bar.fraction > 0, timeout=4))
        self.assertLess(self.ui.session_bar.fraction, 1)
        self.assertNotEqual(self.ui.timer_var.get(), "01:00")
        self.ui._confirm_early_stop = lambda: True  # không mở hộp thoại thật
        self.ui._on_main_btn()
        self.assertEqual(self.ui.state, "idle")
        self.blocker.stop.assert_called()
        self.assertEqual(self.ui.session_bar.fraction, 0)

    def test_invalid_minutes_are_rejected_without_starting(self):
        self.ui.study_min_var.set("0")
        self.ui._on_main_btn()
        self.assertEqual(self.ui.state, "idle")
        self.blocker.start.assert_not_called()

    # ── Gmail ───────────────────────────────────────────────────────
    def test_gmail_mode_emails_a_code_before_the_session_starts(self):
        self.ui.cfg.set("gmail_address", "parent@gmail.com")
        self.ui.cfg.set("gmail_protection_enabled", True)
        self.ui.study_min_var.set("1")
        sent = []

        def fake_send(address, code, minutes):
            sent.append((address, code, minutes))
            return True, ""

        with patch.object(config.Config, "has_gmail_configured", return_value=True), \
                patch.object(session_code, "send_code_email", side_effect=fake_send):
            self.ui._on_main_btn()
            self.assertTrue(self.pump(lambda: self.ui.state == "studying"))
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][0], "parent@gmail.com")
        self.assertRegex(sent[0][1], r"^\d{6}$")
        self.assertTrue(self.ui._has_session_code())
        self.assertTrue(self.ui._session_protected)

    def test_gmail_failure_can_be_cancelled_and_no_session_starts(self):
        self.ui.cfg.set("gmail_address", "parent@gmail.com")
        self.ui.cfg.set("gmail_protection_enabled", True)
        self.ui._ask_send_failed = MagicMock(return_value="cancel")
        with patch.object(config.Config, "has_gmail_configured", return_value=True), \
                patch.object(session_code, "send_code_email", return_value=(False, "offline")):
            self.ui._on_main_btn()
            self.assertTrue(self.pump(lambda: self.ui._ask_send_failed.called))
        self.assertEqual(self.ui.state, "idle")
        self.blocker.start.assert_not_called()

    # ── Cài đặt người gửi (nội bộ) ──────────────────────────────────
    def test_sender_setup_is_visible_only_while_no_client_exists(self):
        with patch.object(app.gmail_oauth, "has_client", return_value=False):
            self.assertTrue(self.ui._show_sender_setup())
        with patch.object(app.gmail_oauth, "has_client", return_value=True):
            self.assertFalse(self.ui._show_sender_setup())
            self.ui.cfg.set("developer_mode", True)
            self.assertTrue(self.ui._show_sender_setup())

    def test_login_button_appears_only_when_a_client_exists_and_not_yet_signed_in(self):
        self.ui.cfg.set("gmail_address", "parent@gmail.com")
        with patch.object(app.gmail_oauth, "has_client", return_value=True),                 patch.object(app.gmail_oauth, "is_connected", return_value=False):
            self.ui._refresh_gmail_status()
            self.assertTrue(self.ui.oauth_login_btn.winfo_manager())
        with patch.object(app.gmail_oauth, "has_client", return_value=True),                 patch.object(app.gmail_oauth, "is_connected", return_value=True):
            self.ui._refresh_gmail_status()
            self.assertFalse(self.ui.oauth_login_btn.winfo_manager())

    # ── Trang AI không chắc ─────────────────────────────────────────
    def test_unsure_site_is_listed_and_labelling_it_saves_the_decision(self):
        self.ui.blocker.labels.add_pending("lofi radio", "Lofi radio - YouTube")
        self.ui._refresh_site_labels()
        texts = [w.cget("text") for w in self.ui.site_review_frame.winfo_children()[0].winfo_children()]
        self.assertTrue(any("Lofi radio" in t for t in texts))
        with patch.object(self.ui, "_check_password", return_value=True):
            self.ui._label_site("lofi radio", "study")
        self.assertEqual(self.ui.blocker.labels.label_for("lofi radio"), "study")
        self.assertEqual(self.ui.blocker.labels.pending_items(), [])

    def test_labelling_needs_the_emailed_code_and_is_refused_without_it(self):
        self.ui.blocker.labels.add_pending("lofi radio", "Lofi radio - YouTube")
        with patch.object(self.ui, "_check_password", return_value=False):
            self.ui._label_site("lofi radio", "study")
        self.assertIsNone(self.ui.blocker.labels.label_for("lofi radio"))

    # ── Ngôn ngữ ────────────────────────────────────────────────────
    def test_changing_language_is_saved_for_the_next_launch(self):
        self.ui.language_var.set("Tiếng Việt")
        with patch.object(app.messagebox, "showinfo") as info:
            self.ui._change_language()
        self.assertEqual(config.Config().get("language"), "vi")
        self.assertIn("khởi động lại", info.call_args.args[1])

    # ── AI Coach ────────────────────────────────────────────────────
    def test_coach_analysis_updates_the_comment_and_remembers_the_language(self):
        with patch.object(app.ai_coach, "analyze", return_value="良い調子です。") as analyze:
            self.ui._run_analysis()
            self.assertTrue(self.pump(lambda: not self.ui._coach_busy))
        self.assertEqual(self.ui.coach_comment.cget("text"), "良い調子です。")
        self.assertEqual(analyze.call_args.kwargs["language"], "ja")
        self.assertEqual(config.Config().get("coach_last_language"), "ja")

    def test_coach_failure_shows_a_message_and_recovers(self):
        with patch.object(app.ai_coach, "analyze", side_effect=RuntimeError("boom")):
            self.ui._run_analysis()
            self.assertTrue(self.pump(lambda: not self.ui._coach_busy))
        self.assertIn("分析できませんでした", self.ui.coach_comment.cget("text"))
        self.assertEqual(str(self.ui.coach_btn.cget("state")), "normal")


if __name__ == "__main__":
    unittest.main()
