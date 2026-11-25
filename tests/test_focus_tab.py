"""Tab 集中: thanh tiến độ phiên, tô sáng mức đang chọn."""

import unittest
from unittest.mock import MagicMock

from evolock.ui import app


def make_ui():
    ui = app.EvoLockApp.__new__(app.EvoLockApp)
    ui.timer_var = MagicMock()
    ui.session_bar = MagicMock()
    return ui


class CountdownTests(unittest.TestCase):
    def test_countdown_updates_digits_and_progress(self):
        ui = make_ui()
        ui._show_countdown(900, 1500)
        ui.timer_var.set.assert_called_once_with("15:00")
        ui.session_bar.set.assert_called_once_with(0.4)

    def test_progress_reaches_full_when_time_is_up(self):
        ui = make_ui()
        ui._show_countdown(0, 1500)
        ui.session_bar.set.assert_called_once_with(1)

    def test_zero_total_does_not_divide_by_zero(self):
        ui = make_ui()
        ui._show_countdown(0, 0)
        ui.session_bar.set.assert_not_called()

    def test_missing_bar_is_tolerated(self):
        ui = app.EvoLockApp.__new__(app.EvoLockApp)
        ui.timer_var = MagicMock()
        ui._show_countdown(60, 120)   # không có session_bar → không lỗi
        ui._reset_session_bar()

    def test_reset_clears_the_bar(self):
        ui = make_ui()
        ui._reset_session_bar()
        ui.session_bar.set.assert_called_once_with(0)


class PresetHighlightTests(unittest.TestCase):
    def setUp(self):
        self.ui = app.EvoLockApp.__new__(app.EvoLockApp)
        self.buttons = {key: MagicMock() for key in ((25, 5), (50, 10), (90, 15))}
        self.ui._preset_buttons = self.buttons
        self.ui.study_min_var = MagicMock()
        self.ui.unlock_min_var = MagicMock()

    def select(self, study, rest):
        self.ui.study_min_var.get.return_value = study
        self.ui.unlock_min_var.get.return_value = rest
        self.ui._highlight_presets()

    def selected(self, key):
        return self.buttons[key].config.call_args.kwargs["bg"] == app.PURPLE

    def test_matching_preset_is_highlighted_and_others_are_not(self):
        self.select("50", "10")
        self.assertTrue(self.selected((50, 10)))
        self.assertFalse(self.selected((25, 5)))
        self.assertFalse(self.selected((90, 15)))

    def test_custom_values_highlight_nothing(self):
        self.select("30", "30")
        self.assertFalse(any(self.selected(key) for key in self.buttons))

    def test_invalid_input_does_not_crash(self):
        self.select("abc", "")
        self.assertFalse(any(self.selected(key) for key in self.buttons))

    def test_no_buttons_is_a_noop(self):
        ui = app.EvoLockApp.__new__(app.EvoLockApp)
        ui._highlight_presets()


if __name__ == "__main__":
    unittest.main()
