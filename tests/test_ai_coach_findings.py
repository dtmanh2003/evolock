"""AI Coach: cửa sổ phân tích, gộp đợt xao nhãng, findings do code tính, fallback offline."""

import unittest
import urllib.error
from datetime import date
from unittest import mock

from evolock.services import ai_coach
from evolock.storage.activity_log import ActivityEvent
from evolock.storage.history import Session
from evolock.storage.override_log import OverrideRecord

TODAY = date(2026, 11, 13)


def study(day, start="09:00", minutes=30):
    return Session("study", start, "10:00", minutes, day)


def ev(day, hhmm, app="chrome.exe", kind="warn"):
    return ActivityEvent(hhmm, day, kind, app, "x")


def ovr(day, hhmm, reason="急用", planned=60, actual=20):
    return OverrideRecord(day, hhmm, reason, "", planned, actual)


class SelectWindowTests(unittest.TestCase):
    def test_recent_week_is_not_stale(self):
        sessions = [study("2026-11-12")]
        w = ai_coach.select_window(sessions, today=TODAY)
        self.assertFalse(w["stale"])
        self.assertEqual(len(w["sessions"]), 1)

    def test_falls_back_to_last_active_week(self):
        sessions = [study("2026-09-20"), study("2026-09-24"), study("2026-09-01")]
        w = ai_coach.select_window(sessions, today=TODAY)
        self.assertTrue(w["stale"])
        self.assertEqual(str(w["end"]), "2026-09-24")
        self.assertEqual(w["days_ago"], 50)
        self.assertEqual(len(w["sessions"]), 2)  # 09-01 nằm ngoài 7 ngày

    def test_no_history_at_all(self):
        w = ai_coach.select_window([], today=TODAY)
        self.assertFalse(w["stale"])
        self.assertEqual(w["sessions"], [])


class EpisodeTests(unittest.TestCase):
    def test_consecutive_scans_merge_into_one_episode(self):
        # Mỗi lần quét 3 giây ghi 1 sự kiện: 100 sự kiện cùng phút = 1 đợt.
        events = [ev("2026-09-20", "10:15") for _ in range(100)]
        self.assertEqual(len(ai_coach._episodes(events)), 1)

    def test_gap_or_other_app_starts_new_episode(self):
        events = [
            ev("2026-09-20", "10:00"),
            ev("2026-09-20", "10:01", kind="kill"),
            ev("2026-09-20", "10:30"),            # cách xa -> đợt mới
            ev("2026-09-20", "10:31", app="steam.exe"),  # app khác -> đợt mới
        ]
        eps = ai_coach._episodes(events)
        self.assertEqual(len(eps), 3)
        self.assertTrue(eps[0]["killed"])

    def test_bad_timestamp_is_ignored(self):
        self.assertEqual(ai_coach._episodes([ev("2026-09-20", "??")]), [])


class FindingsTests(unittest.TestCase):
    def setUp(self):
        self.sessions = [study("2026-11-10", "09:00", 60), study("2026-11-11", "09:30", 30)]
        self.window = ai_coach.select_window(self.sessions, today=TODAY)

    def test_staleness_finding_comes_first(self):
        old = [study("2026-09-24")]
        w = ai_coach.select_window(old, today=TODAY)
        f = ai_coach.compute_findings(old, w, [], [], 120)
        self.assertIn("50日前", f[0]["fact"])

    def test_numbers_come_from_code_not_raw_event_count(self):
        events = [ev("2026-11-10", "13:00") for _ in range(460)]
        f = ai_coach.compute_findings(self.sessions, self.window, events, [], 120)
        text = "\n".join(x["fact"] for x in f)
        self.assertIn("1回", text)        # 460 sự kiện thô = 1 đợt
        self.assertNotIn("460", text)

    def test_morning_concentration_detected(self):
        f = ai_coach.compute_findings(self.sessions, self.window, [], [], 120)
        self.assertTrue(any("朝" in x["fact"] and "100%" in x["fact"] for x in f))

    def test_override_denominator_omitted_when_more_stops_than_sessions(self):
        overrides = [ovr("2026-11-10", "09:10") for _ in range(5)]
        f = ai_coach.compute_findings(self.sessions, self.window, [], overrides, 120)
        fact = next(x["fact"] for x in f if "早く学習を終え" in x["fact"])
        self.assertIn("5回", fact)
        self.assertNotIn("回中", fact)

    def test_records_outside_window_are_excluded(self):
        overrides = [ovr("2026-01-01", "09:10")]
        f = ai_coach.compute_findings(self.sessions, self.window, [], overrides, 120)
        self.assertFalse(any("早く学習を終え" in x["fact"] for x in f))


class AnalyzeTests(unittest.TestCase):
    def test_empty_sessions_returns_offline_without_model_call(self):
        with mock.patch.object(ai_coach, "_ollama_analyze") as m:
            out = ai_coach.analyze("", [], ollama_model="qwen")
        m.assert_not_called()
        self.assertIn("学習データがありません", out)

    def test_ollama_unreachable_falls_back_to_offline_report(self):
        sessions = [study("2026-11-12")]
        with mock.patch.object(ai_coach, "_ollama_analyze",
                               side_effect=urllib.error.URLError("down")):
            out = ai_coach.analyze("", sessions, ollama_model="qwen")
        self.assertIn("Ollamaに接続できません", out)
        self.assertIn("学習分析レポート", out)

    def test_prompt_contains_findings_and_forbids_inference(self):
        sessions = [study("2026-11-12")]
        window = ai_coach.select_window(sessions, today=TODAY)
        findings = [{"fact": "テスト事実123", "hint": "テストヒント"}]
        prompt = ai_coach._assemble_prompt(sessions, window, findings, None, None, 0, 120)
        self.assertIn("テスト事実123", prompt)
        self.assertIn("テストヒント", prompt)
        self.assertIn("推測", ai_coach.COACH_SYSTEM_PROMPT)

    def test_offline_report_includes_findings_section(self):
        sessions = [study("2026-11-12")]
        window = ai_coach.select_window(sessions, today=TODAY)
        out = ai_coach._offline_analyze(
            sessions, window=window,
            findings=[{"fact": "事実A", "hint": "提案A"}])
        self.assertIn("事実A", out)
        self.assertIn("提案A", out)


class ChartDataTests(unittest.TestCase):
    def test_daily_series_covers_every_day_of_the_window(self):
        sessions = [study("2026-11-10", "09:00", 60), study("2026-11-12", "20:00", 30)]
        window = ai_coach.select_window(sessions, today=TODAY)
        data = ai_coach.compute_chart_data(sessions, window, [], [], 120)
        self.assertEqual(len(data["daily"]), 7)
        by_label = dict(data["daily"])
        self.assertEqual(by_label["11/10"], 60)
        self.assertEqual(by_label["11/11"], 0)
        self.assertEqual(by_label["11/12"], 30)
        self.assertEqual(data["totals"]["study_minutes"], 90)
        self.assertEqual(data["totals"]["active_days"], 2)
        self.assertEqual(data["totals"]["goal_days"], 0)

    def test_time_of_day_and_distractions_are_bucketed(self):
        sessions = [study("2026-11-10", "09:00", 60)]
        window = ai_coach.select_window(sessions, today=TODAY)
        events = [ev("2026-11-10", "13:00") for _ in range(50)] + [
            ev("2026-11-11", "21:00", app="steam.exe", kind="kill")]
        data = ai_coach.compute_chart_data(sessions, window, events, [ovr("2026-11-10", "09:10")], 120)
        self.assertEqual(dict(data["study_by_bucket"])["朝"], 60)
        self.assertEqual(dict(data["distraction_by_bucket"])["午後"], 1)  # 50件の生イベント = 1回
        self.assertEqual(dict(data["distraction_by_bucket"])["夜"], 1)
        self.assertEqual(data["distraction_by_app"][0][1], 1)
        self.assertEqual(data["totals"]["episodes"], 2)
        self.assertEqual(data["totals"]["kills"], 1)
        self.assertEqual(data["totals"]["early_stops"], 1)

    def test_empty_history_still_produces_a_valid_structure(self):
        window = ai_coach.select_window([], today=TODAY)
        data = ai_coach.compute_chart_data([], window, [], [], 120)
        self.assertEqual(len(data["daily"]), 7)
        self.assertEqual(data["distraction_by_app"], [])


class CleanCoachTextTests(unittest.TestCase):
    BAD = (
        "1. **状況のまとめ**\n\n今週の学習は21分でした。朝に集中が途切れています。\n\n"
        "2. **行動提案**\n   -\n**朝は短くする**：朝は15分から始めてみましょう。\n   -\n"
        "**夜に移す**：夜に学習を移してみましょう。朝は15分から始めてみましょう。\n\n"
        "3. **励まし**\n\n頑張ってください！頑張ってください！"
    )

    def test_markdown_headings_and_numbers_are_removed(self):
        out = ai_coach.clean_coach_text(self.BAD)
        for noise in ("**", "1.", "2.", "3.", "状況のまとめ", "行動提案"):
            self.assertNotIn(noise, out)

    def test_repeated_sentences_appear_once(self):
        out = ai_coach.clean_coach_text(self.BAD)
        self.assertEqual(out.count("朝は15分から始めてみましょう。"), 1)
        self.assertEqual(out.count("頑張ってください！"), 1)

    def test_bullets_become_separate_lines_and_numbers_are_kept(self):
        out = ai_coach.clean_coach_text(self.BAD)
        self.assertIn("・朝は短くする：", out)
        self.assertIn("・夜に移す：", out)
        self.assertIn("21分", out)

    def test_empty_input(self):
        self.assertEqual(ai_coach.clean_coach_text(""), "")
        self.assertEqual(ai_coach._tidy("**"), "**")  # 空になる時は元の文を返す


if __name__ == "__main__":
    unittest.main()
