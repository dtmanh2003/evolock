"""Biểu đồ Canvas: vẽ đúng số phần tử, không lỗi khi dữ liệu rỗng/cực đoan."""

import tkinter as tk
import unittest

from evolock.ui.charts import BarChart, HBarChart, ProgressBar

THEME = {"card": "#1C2636", "track": "#2C394C", "text": "#F1F5F9", "dim": "#A7B4C8",
         "accent": "#B7ABFF", "good": "#8DD9BE", "warn": "#f9e2af"}


class ChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as exc:  # CI không có màn hình
            raise unittest.SkipTest(f"Tk unavailable: {exc}")
        # Canvas chỉ có kích thước thật khi cửa sổ được hiển thị → đặt ngoài màn hình.
        cls.root.geometry("700x700+6000+0")

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def draw(self, widget, width=600, height=200):
        widget.pack()
        widget.config(width=width, height=height)
        self.root.update_idletasks()
        self.root.update()
        widget.redraw()

    def texts(self, canvas):
        return [canvas.itemcget(i, "text") for i in canvas.find_all() if canvas.type(i) == "text"]

    def test_bar_chart_draws_one_bar_per_nonzero_value(self):
        chart = BarChart(self.root, THEME, unit="分")
        chart.set([("a", 10), ("b", 0), ("c", 30)], goal=20)
        self.draw(chart)
        bars = [i for i in chart.find_all() if chart.type(i) == "rectangle"]
        self.assertEqual(len(bars), 2)
        shown = self.texts(chart)
        self.assertIn("10", shown)
        self.assertIn("30", shown)
        self.assertIn("20分", shown)  # đường mục tiêu có nhãn

    def test_bar_chart_shows_empty_message_for_no_data_or_all_zero(self):
        chart = BarChart(self.root, THEME)
        chart.empty_text = "なし"
        chart.set([("a", 0), ("b", 0)])
        self.draw(chart)
        self.assertEqual(self.texts(chart), ["なし"])
        chart.set([])
        chart.redraw()
        self.assertEqual(self.texts(chart), ["なし"])

    def test_bar_chart_survives_a_tiny_window(self):
        chart = BarChart(self.root, THEME)
        chart.set([("a", 5)])
        self.draw(chart, width=10, height=10)  # không ném lỗi

    def test_horizontal_chart_drops_zero_rows_and_truncates_long_labels(self):
        chart = HBarChart(self.root, THEME, unit="回")
        chart.set([("RiotClientServices.exe", 3), ("chrome.exe", 6), ("none.exe", 0)])
        self.draw(chart, width=400, height=120)
        shown = self.texts(chart)
        self.assertNotIn("none.exe", shown)
        self.assertTrue(any(t.endswith("…") for t in shown))
        self.assertIn("6回", shown)
        self.assertIn("3回", shown)

    def test_horizontal_chart_grows_with_rows(self):
        chart = HBarChart(self.root, THEME)
        chart.set([(f"app{i}", i + 1) for i in range(5)])
        self.assertGreater(int(chart.cget("height")), 60)

    def test_progress_bar_clamps_fraction(self):
        bar = ProgressBar(self.root, THEME)
        bar.set(5)
        self.assertEqual(bar.fraction, 1.0)
        bar.set(-1)
        self.assertEqual(bar.fraction, 0.0)
        self.draw(bar, width=200, height=10)


if __name__ == "__main__":
    unittest.main()
