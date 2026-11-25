"""Biểu đồ nhẹ vẽ bằng tkinter.Canvas (không cần matplotlib).

Mỗi widget tự vẽ lại khi đổi kích thước, nên dùng được trong tab cuộn và cửa sổ
nhỏ mà không bị cắt. Màu lấy từ dict `theme` do giao diện truyền vào để không
phụ thuộc ngược vào ui/app.py.

theme keys: card, track, text, dim, accent, good, warn
"""

import tkinter as tk

from evolock.i18n import tr

FONT = "Yu Gothic UI"


def _fmt(value: float) -> str:
    return str(int(round(value)))


class BarChart(tk.Canvas):
    """Cột dọc theo thứ tự thời gian, có đường mục tiêu tùy chọn."""

    def __init__(self, parent, theme: dict, height: int = 180, unit: str = "",
                 color: str | None = None):
        super().__init__(parent, height=height, bg=theme["card"], highlightthickness=0)
        self.theme = theme
        self.unit = unit
        self.color = color or theme["accent"]
        self.data: list[tuple[str, float]] = []
        self.goal: float | None = None
        self.empty_text = tr("データがありません")
        self.bind("<Configure>", lambda e: self.redraw())

    def set(self, data, goal=None):
        self.data = list(data)
        self.goal = goal
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 40 or h < 40:
            return
        t = self.theme
        if not self.data or max(v for _, v in self.data) <= 0:
            self.create_text(w / 2, h / 2, text=self.empty_text, fill=t["dim"],
                             font=(FONT, 10))
            return
        left, right, top, bottom = 14, 14, 26, 26
        plot_h = h - top - bottom
        peak = max(max(v for _, v in self.data), self.goal or 0)
        slot = (w - left - right) / len(self.data)
        bar_w = min(46, slot * 0.58)
        base = h - bottom
        self.create_line(left, base, w - right, base, fill=t["track"])
        if self.goal:
            y = base - self.goal / peak * plot_h
            self.create_line(left, y, w - right, y, fill=t["warn"], dash=(4, 3))
            self.create_text(w - right, y - 8, text=f"{_fmt(self.goal)}{self.unit}",
                             fill=t["warn"], font=(FONT, 8), anchor="e")
        for i, (label, value) in enumerate(self.data):
            cx = left + slot * (i + 0.5)
            bar_h = value / peak * plot_h
            if value > 0:
                self.create_rectangle(cx - bar_w / 2, base - bar_h, cx + bar_w / 2, base,
                                      fill=self.color, outline="")
                self.create_text(cx, base - bar_h - 8, text=_fmt(value), fill=t["text"],
                                 font=(FONT, 9, "bold"))
            else:
                self.create_line(cx - bar_w / 2, base - 1, cx + bar_w / 2, base - 1,
                                 fill=t["track"], width=2)
            self.create_text(cx, base + 12, text=label, fill=t["dim"], font=(FONT, 8))


class HBarChart(tk.Canvas):
    """Thanh ngang có nhãn bên trái và giá trị bên phải — dùng cho xếp hạng."""

    ROW = 30

    def __init__(self, parent, theme: dict, unit: str = "", color: str | None = None):
        super().__init__(parent, height=60, bg=theme["card"], highlightthickness=0)
        self.theme = theme
        self.unit = unit
        self.color = color or theme["accent"]
        self.data: list[tuple[str, float]] = []
        self.empty_text = tr("データがありません")
        self.bind("<Configure>", lambda e: self.redraw())

    def set(self, data):
        self.data = [(k, v) for k, v in data if v > 0]
        self.config(height=max(60, len(self.data) * self.ROW + 16))
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 60:
            return
        t = self.theme
        if not self.data:
            self.create_text(w / 2, h / 2, text=self.empty_text, fill=t["dim"], font=(FONT, 10))
            return
        label_w, value_w, pad = min(200, w * 0.38), 56, 14
        track_x0, track_x1 = pad + label_w, w - pad - value_w
        peak = max(v for _, v in self.data)
        max_chars = max(6, int((label_w - 8) / 7.5))
        for i, (label, value) in enumerate(self.data):
            cy = 8 + self.ROW * i + self.ROW / 2
            # 長い名前は省略して1行に収める（折り返すと下の行に重なる）
            shown = label if len(label) <= max_chars else label[:max_chars - 1] + "…"
            self.create_text(pad, cy, text=shown, fill=t["text"], font=(FONT, 9), anchor="w")
            self.create_rectangle(track_x0, cy - 6, track_x1, cy + 6, fill=t["track"], outline="")
            if track_x1 > track_x0:
                self.create_rectangle(track_x0, cy - 6,
                                      track_x0 + (track_x1 - track_x0) * value / peak, cy + 6,
                                      fill=self.color, outline="")
            self.create_text(w - pad, cy, text=f"{_fmt(value)}{self.unit}", fill=t["text"],
                             font=(FONT, 9, "bold"), anchor="e")


class ProgressBar(tk.Canvas):
    """Thanh tiến độ phẳng với nhãn phần trăm bên phải."""

    def __init__(self, parent, theme: dict, height: int = 14, color: str | None = None,
                 bg: str | None = None):
        super().__init__(parent, height=height, bg=bg or theme["card"], highlightthickness=0)
        self.theme = theme
        self.color = color or theme["accent"]
        self.fraction = 0.0
        self.bind("<Configure>", lambda e: self.redraw())

    def set(self, fraction: float):
        self.fraction = max(0.0, min(1.0, fraction))
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20:
            return
        self.create_rectangle(0, 0, w, h, fill=self.theme["track"], outline="")
        if self.fraction > 0:
            self.create_rectangle(0, 0, max(2, w * self.fraction), h, fill=self.color, outline="")
