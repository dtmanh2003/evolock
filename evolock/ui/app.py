from copy import deepcopy
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog, filedialog
from datetime import datetime, timedelta
import os
import threading
import re
import random
import math

from evolock.services.blocker import Blocker, load_blocked_apps, save_blocked_apps, list_running_apps
from evolock.services.timer import CountdownTimer, fmt_time
from evolock.storage.tasks import TaskManager, TASK_TYPES
from evolock.services.gamification import GameManager, ACHIEVEMENTS
from evolock.storage.config import Config
from evolock.storage.json_file import DataFileError
from evolock.storage.history import HistoryManager
from evolock.integrations.protection import add_to_startup, remove_from_startup, is_in_startup
from evolock.storage.pw_log import PasswordLogger
from evolock.storage.activity_log import ActivityLogger
from evolock.storage.override_log import OverrideLogger
from evolock.integrations import session_code, gmail_oauth
from evolock.integrations.instance import InstanceLock
from evolock.services import ai_coach
from evolock.ui.charts import BarChart, HBarChart, ProgressBar
from evolock.paths import MASCOT_FRAMES_DIR
from evolock import i18n
from evolock.i18n import tr

# ── Optional tray ─────────────────────────────────────────────────
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

# ── Optional mascot (実イラストのチビ鍵キャラ、アニメーション付き) ──────
try:
    from PIL import Image as _MImage, ImageTk as _MImageTk
    MASCOT_AVAILABLE = True
except ImportError:
    MASCOT_AVAILABLE = False

MASCOT_LINES = [
    "一緒に頑張ろう！",
    "誘惑に負けないで！",
    "ここは今、我慢のしどころ！",
    "集中、応援してる！",
    "あと少し、いける！",
    "君ならできる！",
]

MASCOT_DISPLAY_H = 56  # キャンバスの高さ(76px)に収まるサイズ


def _load_mascot_frame_sets() -> list:
    """mascot_frames/anim{1,2,3}_00〜09.png（実イラスト、事前に抽出済み）を
    アニメーションごとに分けて読み込む — 複数あれば方向転換のたびにランダムで
    切り替えて単調にならないようにする。無ければ空リスト。"""
    if not MASCOT_FRAMES_DIR.exists():
        return []
    prefixes = sorted({f.name.rsplit("_", 1)[0] for f in MASCOT_FRAMES_DIR.glob("*_*.png")})
    sets = []
    for prefix in prefixes:
        files = sorted(MASCOT_FRAMES_DIR.glob(f"{prefix}_*.png"))
        frames = []
        for f in files:
            img = _MImage.open(f).convert("RGBA")
            w, h = img.size
            new_w = int(w * MASCOT_DISPLAY_H / h)
            frames.append(img.resize((new_w, MASCOT_DISPLAY_H), _MImage.LANCZOS))
        if frames:
            sets.append(frames)
    return sets

# ── Colors ────────────────────────────────────────────────────────
BG     = "#111827"
BG2    = "#1C2636"
BG3    = "#2C394C"
FG     = "#F1F5F9"
FG_DIM = "#A7B4C8"
PURPLE = "#B7ABFF"
GREEN  = "#8DD9BE"
RED    = "#f38ba8"
YELLOW = "#f9e2af"
BLUE   = "#89b4fa"
CHART_THEME = {"card": BG2, "track": BG3, "text": FG, "dim": FG_DIM,
               "accent": PURPLE, "good": GREEN, "warn": YELLOW}

# ── Font ──────────────────────────────────────────────────────────
F_UI   = "Yu Gothic UI"
F_MONO = "Consolas"

DEFAULT_STUDY_MIN  = 30
DEFAULT_UNLOCK_MIN = 30


# ── Tray icon ─────────────────────────────────────────────────────
def _make_tray_image(locked: bool) -> "Image.Image":
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = (243, 139, 168) if locked else (166, 227, 161)
    draw.ellipse([4, 4, 60, 60], fill=color)
    draw.rectangle([22, 34, 42, 52], fill=(30, 30, 46))
    arc_color = (30, 30, 46)
    if locked:
        draw.arc([22, 20, 42, 42], 180, 360, fill=arc_color, width=4)
    else:
        draw.arc([28, 14, 48, 36], 180, 360, fill=arc_color, width=4)
    return img


# ── Password dialog ───────────────────────────────────────────────
def ask_password(parent: tk.Tk, title=tr("パスワードを入力"), hint: str = "",
                 masked: bool = True) -> str | None:
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg=BG)
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.transient(parent)

    tk.Label(dlg, text=title, font=(F_UI, 11, "bold"),
             bg=BG, fg=PURPLE).pack(pady=(16, 8), padx=24)

    if hint:
        tk.Label(dlg, text=hint, wraplength=340, justify="left", bg=BG, fg=FG_DIM,
                 font=(F_UI, 9)).pack(padx=24, pady=(0, 12))
    var = tk.StringVar()
    entry = tk.Entry(dlg, textvariable=var, show="*" if masked else "", width=20,
                     font=(F_MONO, 12), bg=BG3, fg=FG,
                     insertbackground=FG, relief="flat", justify="center")
    entry.pack(padx=24, pady=(0, 12))
    entry.focus_set()

    result = [None]

    def _ok(e=None):
        result[0] = var.get()
        dlg.destroy()

    def _cancel(e=None):
        dlg.destroy()

    entry.bind("<Return>", _ok)
    entry.bind("<Escape>", _cancel)

    btn_frame = tk.Frame(dlg, bg=BG)
    btn_frame.pack(pady=(0, 8))
    tk.Button(btn_frame, text=tr("コードを確認"), font=(F_UI, 10, "bold"),
              bg=GREEN, fg=BG, relief="flat", padx=16, pady=4,
              command=_ok).pack(side="left", padx=4)
    tk.Button(btn_frame, text=tr("キャンセル"), font=(F_UI, 10),
              bg=BG3, fg=FG, relief="flat", padx=12, pady=4,
              command=_cancel).pack(side="left", padx=4)

    dlg.wait_window()
    return result[0]


def ask_override(parent: tk.Tk) -> dict | None:
    """Dialog dừng học sớm có chủ ý: chọn lý do + ghi chú + nhập mã từ Gmail.
    Trả về {"reason", "note", "code"} hoặc None nếu hủy."""
    dlg = tk.Toplevel(parent)
    dlg.title(tr("学習を止める"))
    dlg.configure(bg=BG)
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.transient(parent)

    tk.Label(dlg, text=tr("⏸ 本当に今、止めますか？"), font=(F_UI, 12, "bold"),
             bg=BG, fg=PURPLE).pack(pady=(18, 4), padx=28)
    tk.Label(dlg, text=tr("Gmailに送られたコードが必要です。"),
             font=(F_UI, 8), bg=BG, fg=FG_DIM).pack(padx=28, pady=(0, 12))

    tk.Label(dlg, text=tr("理由:"), font=(F_UI, 9, "bold"), bg=BG, fg=FG
             ).pack(anchor="w", padx=28)
    # 画面には翻訳した理由を出すが、記録（override_log）には元の日本語を保存する
    reason_labels = {tr(r): r for r in session_code.REASONS}
    reason_var = tk.StringVar(value=tr(session_code.REASONS[0]))
    reason_menu = ttk.Combobox(dlg, textvariable=reason_var, state="readonly",
                                values=list(reason_labels), width=22, font=(F_UI, 10))
    reason_menu.pack(padx=28, pady=(4, 10), anchor="w")

    tk.Label(dlg, text=tr("メモ（任意）:"), font=(F_UI, 9, "bold"), bg=BG, fg=FG
             ).pack(anchor="w", padx=28)
    note_var = tk.StringVar()
    tk.Entry(dlg, textvariable=note_var, width=30, font=(F_UI, 10),
              bg=BG3, fg=FG, insertbackground=FG, relief="flat"
              ).pack(padx=28, pady=(4, 10), anchor="w")

    tk.Label(dlg, text=tr("Gmailで受け取ったコード:"), font=(F_UI, 9, "bold"), bg=BG, fg=FG
             ).pack(anchor="w", padx=28)
    code_var = tk.StringVar()
    code_entry = tk.Entry(dlg, textvariable=code_var, width=12, font=(F_MONO, 14),
                          bg=BG3, fg=GREEN, insertbackground=FG, relief="flat",
                          justify="center")
    code_entry.pack(padx=28, pady=(4, 14), anchor="w")
    code_entry.focus_set()

    result = [None]

    def _ok(e=None):
        result[0] = {
            "reason": reason_labels.get(reason_var.get(), session_code.REASONS[0]),
            "note": note_var.get().strip(),
            "code": code_var.get().strip(),
        }
        dlg.destroy()

    def _cancel(e=None):
        dlg.destroy()

    code_entry.bind("<Return>", _ok)
    dlg.bind("<Escape>", _cancel)

    btn_frame = tk.Frame(dlg, bg=BG)
    btn_frame.pack(pady=(0, 18))
    tk.Button(btn_frame, text=tr("止める"), font=(F_UI, 10, "bold"),
              bg=RED, fg=BG, relief="flat", padx=16, pady=4,
              command=_ok).pack(side="left", padx=4)
    tk.Button(btn_frame, text=tr("キャンセル — 続ける"), font=(F_UI, 10),
              bg=BG3, fg=FG, relief="flat", padx=12, pady=4,
              command=_cancel).pack(side="left", padx=4)

    dlg.wait_window()
    return result[0]


# ── Main App ──────────────────────────────────────────────────────
class EvoLockApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("EvoLock")
        self.root.geometry("640x820")
        self.root.minsize(560, 620)
        self.root.resizable(True, True)
        self.root.configure(bg=BG)

        self.cfg      = Config()
        i18n.set_language(self.cfg.get("language"))  # 以降のtr()はこの言語で表示する
        self.blocker  = Blocker(
            on_kill_callback=lambda items: self.root.after(0, self._on_kill, items),
            on_allow_callback=lambda items: self.root.after(0, self._on_smart_allow, items),
            on_model_ready=self._on_model_ready,
            on_screen_classify=self._on_screen_classify,
        )
        # Sync settings sang blocker ngay khi khởi động
        self.blocker.screen_api_key      = self.cfg.get("anthropic_api_key") or ""
        self.blocker.screen_ollama_model = self.cfg.get("ollama_model") or ""
        self.blocker.smart_enabled = bool(self.cfg.get("smart_enabled"))
        self._sync_screen_settings()
        self.task_mgr  = TaskManager()
        self.game      = GameManager()
        self.history   = HistoryManager()
        self.history.settle_rewards(self.game)
        self.pw_logger = PasswordLogger()
        self.activity_log = ActivityLogger()
        self.override_log = OverrideLogger()

        self.study_timer  = None
        self.unlock_timer = None
        self.state = "idle"  # idle | studying | unlocked | locked

        self._study_started_at  = None
        self._unlock_started_at = None
        self._tray_icon = None

        self._style_ttk()
        self._build_ui()
        self._refresh_blocked_list()
        self._reset_timers()
        self._refresh_task_list()
        self._refresh_stats()
        self._refresh_history_display()
        self._day_after_id = self.root.after(60_000, self._refresh_day)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        if TRAY_AVAILABLE:
            self._start_tray()

    # ── Style ──────────────────────────────────────────────────────

    def _style_ttk(self):
        s = ttk.Style()
        s.theme_use("default")
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=BG2, foreground=FG,
                    padding=[16, 10], font=(F_UI, 10))
        s.map("TNotebook.Tab",
              background=[("selected", BG)],
              foreground=[("selected", PURPLE)])
        s.configure("TFrame", background=BG)
        # 入力欄・選択欄を暗い配色に合わせる（既定の白だと浮いて見える）
        s.configure("TCombobox", fieldbackground=BG3, background=BG3, foreground=FG,
                    arrowcolor=FG, bordercolor=BG3, lightcolor=BG3, darkcolor=BG3,
                    selectbackground=BG3, selectforeground=FG, padding=6)
        s.map("TCombobox",
              fieldbackground=[("readonly", BG3), ("disabled", BG2)],
              foreground=[("readonly", FG)],
              selectbackground=[("readonly", BG3)],
              selectforeground=[("readonly", FG)])
        self.root.option_add("*TCombobox*Listbox.background", BG3)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)
        self.root.option_add("*TCombobox*Listbox.selectBackground", PURPLE)
        self.root.option_add("*TCombobox*Listbox.selectForeground", BG)
        s.configure("EXP.Horizontal.TProgressbar",
                    troughcolor=BG3, background=PURPLE, thickness=8)
        s.configure("Goal.Horizontal.TProgressbar",
                    troughcolor=BG3, background=GREEN, thickness=10)

    # ── Build UI ───────────────────────────────────────────────────

    def _build_ui(self):
        tk.Label(self.root, text="EvoLock", font=(F_UI, 22, "bold"),
                 bg=BG, fg=PURPLE).pack(pady=(14, 0))
        tk.Label(self.root, text=tr("EvoLockがリズムを守り、あなたが目標を叶える。"),
                 font=(F_UI, 9), bg=BG, fg=FG_DIM).pack()

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=14, pady=10)

        tabs = [
            (tr("  集中  "),    self._build_lock_tab),
            (tr("  タスク  "),    self._build_tasks_tab),
            (tr("  記録  "),     self._build_stats_tab),
            (tr("  AIコーチ  "),  self._build_coach_tab),
            (tr("  設定  "),      self._build_settings_tab),
        ]
        self._coach_tab_index = 3
        for label, builder in tabs:
            frame = ttk.Frame(self.nb)
            self.nb.add(frame, text=label)
            content = self._scrollable_tab(frame)
            builder(content)

    # ── Tab: ロック ────────────────────────────────────────────────

    def _scrollable_tab(self, parent):
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        content = tk.Frame(canvas, bg=BG)
        item = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(item, width=event.width))
        # Bind once at the toplevel; route only events from this tab's descendants.
        def wheel(event):
            widget = event.widget
            if isinstance(widget, (tk.Text, tk.Listbox, ttk.Combobox)):
                return
            while widget is not None:
                if widget is content or widget is canvas:
                    if content.winfo_reqheight() > canvas.winfo_height():
                        canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
                    return "break"
                widget = getattr(widget, "master", None)
        self.root.bind("<MouseWheel>", wheel, add="+")
        return content

    def _disclosure(self, parent, title):
        container = tk.Frame(parent, bg=BG)
        container.pack(fill="x", padx=12, pady=(8, 4))
        body = tk.Frame(container, bg=BG)
        def toggle():
            if body.winfo_manager():
                body.pack_forget()
                button.config(text="＋  " + title)
            else:
                body.pack(fill="x", pady=(8, 0))
                button.config(text="−  " + title)
        button = tk.Button(container, text="＋  " + title, command=toggle,
                           bg=BG, fg=FG_DIM, activebackground=BG2, activeforeground=FG,
                           relief="flat", anchor="w", font=(F_UI, 10), pady=8, cursor="hand2")
        button.pack(fill="x")
        return body

    def _highlight_presets(self):
        buttons = getattr(self, "_preset_buttons", None)
        if not buttons:
            return
        try:
            current = (int(self.study_min_var.get()), int(self.unlock_min_var.get()))
        except (ValueError, tk.TclError):
            current = None
        for key, button in buttons.items():
            selected = key == current
            button.config(bg=PURPLE if selected else BG3, fg=BG if selected else FG)

    def _show_countdown(self, remaining: int, total: int):
        """残り時間の数字と、進み具合のバーを同時に更新する。"""
        self.timer_var.set(fmt_time(remaining))
        bar = getattr(self, "session_bar", None)
        if bar is not None and total > 0:
            bar.set(1 - remaining / total)

    def _reset_session_bar(self):
        bar = getattr(self, "session_bar", None)
        if bar is not None:
            bar.set(0)

    def _select_session_preset(self, study, rest):
        if self.state == "studying":
            return
        self.study_min_var.set(str(study))
        self.unlock_min_var.set(str(rest))
        if self.state in ("idle", "locked"):
            self.timer_var.set(fmt_time(study * 60))

    def _build_lock_tab(self, parent):
        hero = tk.Frame(parent, bg=BG2, padx=20, pady=16)
        hero.pack(fill="x", padx=12, pady=(16, 12))
        headline = tk.Label(hero, text=tr("今は、ひとつのことに。"), font=(F_UI, 18, "bold"),
                            bg=BG2, fg=FG, justify="center")
        headline.pack()
        self._auto_wrap(headline, 60)  # 言語によって長さが違うので、幅に合わせて折り返す
        self.status_var = tk.StringVar(value=tr("準備ができたら、集中を始めましょう"))
        self.status_label = tk.Label(hero, textvariable=self.status_var,
                                    font=(F_UI, 10), bg=BG2, fg=FG_DIM, justify="center")
        self.status_label.pack(pady=(8, 0))
        self.timer_var = tk.StringVar(value=fmt_time(DEFAULT_STUDY_MIN * 60))
        tk.Label(hero, textvariable=self.timer_var, font=(F_MONO, 44, "bold"),
                 bg=BG2, fg=FG).pack(pady=(14, 0))
        self.timer_label = tk.Label(hero, text=tr("集中する時間"), font=(F_UI, 10), bg=BG2, fg=FG_DIM)
        self.timer_label.pack()
        # 今のセッションがどこまで進んだかを細いバーで見せる（数字だけより直感的）
        self.session_bar = ProgressBar(hero, CHART_THEME, height=6, color=PURPLE, bg=BG2)
        self.session_bar.pack(fill="x", padx=24, pady=(12, 0))
        self.btn_main = tk.Button(hero, text=tr("学習開始"), command=self._on_main_btn,
                                  font=(F_UI, 12, "bold"), bg=GREEN, fg=BG,
                                  activebackground="#B2E9D5", relief="flat", bd=0,
                                  padx=24, pady=10, cursor="hand2")
        self.btn_main.pack(fill="x", padx=24, pady=(14, 0))

        sf = tk.Frame(parent, bg=BG, padx=16, pady=8)
        sf.pack(fill="x", padx=12)
        tk.Label(sf, text=tr("自分のペースで"), font=(F_UI, 11, "bold"), bg=BG, fg=FG).pack(anchor="w")
        presets = tk.Frame(sf, bg=BG)
        presets.pack(fill="x", pady=(10, 12))
        self._preset_buttons = {}
        for column, (study, rest) in enumerate(((25, 5), (50, 10), (90, 15))):
            button = tk.Button(presets, text=tr("{0}分 / 休憩{1}分").format(study, rest),
                               font=(F_UI, 9), wraplength=170, justify="center",
                               command=lambda a=study, b=rest: self._select_session_preset(a, b),
                               bg=BG3, fg=FG, relief="flat", padx=8, pady=8,
                               cursor="hand2")
            # 3つを同じ幅で横に並べる（長い言語でも右が切れない）
            button.grid(row=0, column=column, sticky="ew",
                        padx=(0 if column == 0 else 4, 0 if column == 2 else 4))
            presets.grid_columnconfigure(column, weight=1, uniform="preset")
            self._preset_buttons[(study, rest)] = button
        custom = tk.Frame(sf, bg=BG)
        custom.pack(anchor="w")
        self.study_min_var = tk.StringVar(value=str(DEFAULT_STUDY_MIN))
        self.unlock_min_var = tk.StringVar(value=str(DEFAULT_UNLOCK_MIN))
        # 手入力でも、今の設定と同じプリセットがあれば強調表示する
        self.study_min_var.trace_add("write", lambda *_: self._highlight_presets())
        self.unlock_min_var.trace_add("write", lambda *_: self._highlight_presets())
        for label, variable in ((tr("集中"), self.study_min_var), (tr("休憩"), self.unlock_min_var)):
            tk.Label(custom, text=label, font=(F_UI, 10), bg=BG, fg=FG_DIM).pack(side="left", padx=(0, 8))
            tk.Entry(custom, textvariable=variable, width=5, justify="center",
                     font=(F_MONO, 11), bg=BG2, fg=FG, insertbackground=FG,
                     relief="flat").pack(side="left", ipady=5)
            tk.Label(custom, text=tr("分"), font=(F_UI, 10), bg=BG, fg=FG_DIM).pack(side="left", padx=(6, 20))
        self.settings_msg = tk.Label(sf, text="", font=(F_UI, 9), bg=BG, fg=FG_DIM)
        self.settings_msg.pack(anchor="w", pady=(6, 0))

        goal_frame = tk.Frame(parent, bg=BG2, padx=18, pady=14)
        goal_frame.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(goal_frame, text=tr("今日の積み重ね"), font=(F_UI, 11, "bold"), bg=BG2, fg=FG).pack(anchor="w")
        self.goal_var = tk.StringVar(value="")
        tk.Label(goal_frame, textvariable=self.goal_var, font=(F_UI, 10), bg=BG2, fg=FG_DIM).pack(anchor="w", pady=(5, 8))
        self.goal_bar = ProgressBar(goal_frame, CHART_THEME, height=8, color=GREEN, bg=BG2)
        self.goal_bar.pack(fill="x")
        self._highlight_presets()
        self._build_mascot_strip(parent)
        history_body = self._disclosure(parent, tr("今日のセッション"))
        self.hist_frame = tk.Frame(history_body, bg=BG2)
        self.hist_frame.pack(fill="x")
        details = self._disclosure(parent, tr("動作の詳細"))
        self.ai_status_var = tk.StringVar(value=tr("準備中..."))
        tk.Label(details, textvariable=self.ai_status_var, font=(F_UI, 9), bg=BG, fg=FG_DIM,
                 wraplength=480, justify="left").pack(anchor="w", pady=(0, 8))
        self.log = scrolledtext.ScrolledText(details, height=5, font=(F_MONO, 9),
                                            bg=BG2, fg=FG_DIM, relief="flat", state="disabled", wrap="word")
        self.log.pack(fill="x", pady=(0, 12))

    # ── Mascot (歩き回る応援キャラ) ──────────────────────────────────

    def _build_mascot_strip(self, parent):
        if not MASCOT_AVAILABLE:
            return
        frame_sets = _load_mascot_frame_sets()
        if not frame_sets:
            return  # mascot_frames/ が無い環境ではキャラなしで正常動作

        self._mascot_after_id = None
        strip = tk.Canvas(parent, height=76, bg=BG, highlightthickness=0)
        strip.pack(fill="x", padx=12, pady=(2, 4))
        self.mascot_canvas = strip

        # 複数アニメーション（anim1/2/3）をそれぞれ右向き・左向きで用意 —
        # 方向転換のたびにランダムで切り替えて単調にならないようにする。
        self._mascot_sets_right = [
            [_MImageTk.PhotoImage(f) for f in frames] for frames in frame_sets
        ]
        self._mascot_sets_left = [
            [_MImageTk.PhotoImage(f.transpose(_MImage.FLIP_LEFT_RIGHT)) for f in frames]
            for frames in frame_sets
        ]
        self._mascot_set_idx = 0

        self._mascot_x = 30.0
        self._mascot_dir = 1
        self._mascot_tick_n = 0
        self._mascot_bubble_left = 0

        # 「短く歩いて自然に消え、しばらくしてランダムな位置・アニメーションで
        # 再登場する」を繰り返す — ずっと同じ往復より単調にならない。
        self._mascot_phase = "walk"       # "walk" | "hidden"
        self._mascot_phase_tick = 0
        self._mascot_walk_ticks = 220     # ~15.4秒歩いたら消える（頻繁な明滅は逆に気が散るため長め）
        self._mascot_hide_ticks = 0       # 消えている間の長さ（hidden移行時に決定）

        self.mascot_img_id = strip.create_image(
            30, 68, anchor="s", image=self._mascot_sets_right[0][0])
        self.mascot_bubble_bg_id = strip.create_rectangle(
            0, 0, 0, 0, fill=BG3, outline="", state="hidden")
        self.mascot_bubble_txt_id = strip.create_text(
            30, 8, text="", font=(F_UI, 8), fill=FG, anchor="n", width=160)

        strip.bind("<Configure>", lambda e: None)
        self._mascot_tick()

    def _mascot_tick(self):
        if not hasattr(self, "mascot_canvas"):
            return
        strip = self.mascot_canvas
        try:
            w = strip.winfo_width()
        except tk.TclError:
            return  # ウィンドウが閉じられた
        if w <= 1:
            w = 440

        self._mascot_tick_n += 1
        self._mascot_phase_tick += 1

        if self._mascot_phase == "hidden":
            if self._mascot_phase_tick >= self._mascot_hide_ticks:
                # 再登場 — ランダムな位置・向き・アニメーションで。
                self._mascot_x = random.uniform(30, max(31.0, w - 30))
                self._mascot_dir = random.choice((-1, 1))
                self._mascot_set_idx = random.randrange(len(self._mascot_sets_right))
                strip.itemconfig(self.mascot_img_id, state="normal")
                self._mascot_phase = "walk"
                self._mascot_phase_tick = 0
            self._mascot_after_id = self.root.after(70, self._mascot_tick)
            return

        # phase == "walk"
        self._mascot_x += 1.1 * self._mascot_dir
        if self._mascot_x > w - 20.0:
            self._mascot_x = w - 20.0
            self._mascot_dir = -1
            self._mascot_set_idx = random.randrange(len(self._mascot_sets_right))
        elif self._mascot_x < 20.0:
            self._mascot_x = 20.0
            self._mascot_dir = 1
            self._mascot_set_idx = random.randrange(len(self._mascot_sets_right))

        sets = self._mascot_sets_right if self._mascot_dir > 0 else self._mascot_sets_left
        frames = sets[self._mascot_set_idx]
        # 3ティックごとに次のコマへ — 10コマで約2.1秒の弾むループ
        frame_idx = (self._mascot_tick_n // 3) % len(frames)
        bob = math.sin(self._mascot_tick_n * 0.15) * 2
        strip.itemconfig(self.mascot_img_id, image=frames[frame_idx])
        strip.coords(self.mascot_img_id, self._mascot_x, 68 + bob)

        # 応援バブル：時々ランダムに表示
        if self._mascot_bubble_left > 0:
            self._mascot_bubble_left -= 1
            strip.coords(self.mascot_bubble_txt_id, self._mascot_x, 4)
            bbox = strip.bbox(self.mascot_bubble_txt_id)
            if bbox:
                strip.coords(self.mascot_bubble_bg_id,
                             bbox[0] - 8, bbox[1] - 4, bbox[2] + 8, bbox[3] + 4)
            if self._mascot_bubble_left == 0:
                strip.itemconfig(self.mascot_bubble_bg_id, state="hidden")
                strip.itemconfig(self.mascot_bubble_txt_id, text="")
        elif self._mascot_tick_n % 20 == 0 and random.random() < 0.35:
            line = tr(random.choice(MASCOT_LINES))
            strip.itemconfig(self.mascot_bubble_txt_id, text=line)
            strip.itemconfig(self.mascot_bubble_bg_id, state="normal")
            strip.tag_raise(self.mascot_bubble_txt_id)
            self._mascot_bubble_left = 32  # ~2.2秒表示

        if self._mascot_phase_tick >= self._mascot_walk_ticks:
            # 短い距離を歩いたら自然に消える。
            strip.itemconfig(self.mascot_img_id, state="hidden")
            strip.itemconfig(self.mascot_bubble_bg_id, state="hidden")
            strip.itemconfig(self.mascot_bubble_txt_id, text="")
            self._mascot_bubble_left = 0
            self._mascot_phase = "hidden"
            self._mascot_phase_tick = 0
            self._mascot_hide_ticks = random.randint(15, 35)  # ~1.1〜2.5秒後に再登場

        self._mascot_after_id = self.root.after(70, self._mascot_tick)

    def _stop_mascot(self):
        if getattr(self, "_mascot_after_id", None):
            try:
                self.root.after_cancel(self._mascot_after_id)
            except Exception:
                pass
            self._mascot_after_id = None

    # ── Tab: タスク ────────────────────────────────────────────────

    def _build_tasks_tab(self, parent):
        form = tk.Frame(parent, bg=BG2, pady=12)
        form.pack(fill="x", pady=(8, 0))
        form.grid_columnconfigure(1, weight=1)

        tk.Label(form, text=tr("タスク名"), font=(F_UI, 10),
                 bg=BG2, fg=FG_DIM).grid(row=0, column=0, padx=(16, 10), sticky="w")
        self.task_name_var = tk.StringVar()
        self.task_name_combo = ttk.Combobox(
            form, textvariable=self.task_name_var, width=22,
            font=(F_UI, 11), state="normal")
        self.task_name_combo.grid(row=0, column=1, padx=(0, 6), pady=5, sticky="ew")
        self.task_name_combo.bind("<Return>", lambda e: self._add_task())

        tk.Button(form, text="🗑", font=(F_UI, 10),
                  bg=BG3, fg=RED, relief="flat", padx=8, pady=4, cursor="hand2",
                  command=self._open_suggestion_manager
                  ).grid(row=0, column=2, padx=(0, 10), pady=5)

        tk.Label(form, text=tr("種類"), font=(F_UI, 10),
                 bg=BG2, fg=FG_DIM).grid(row=1, column=0, padx=(16, 10), sticky="w")
        self.task_type_var = tk.StringVar(value=TASK_TYPES[0])
        # 種類を変えるたびに、その種類で過去に使ったタスク名を候補として出す
        # — 毎回同じ名前を打ち直さなくて済むように。
        self.task_type_var.trace_add("write", lambda *_: self._refresh_task_name_suggestions())
        # 保存する種類は日本語のまま、画面の選択肢だけ翻訳する
        type_labels = {tr(t): t for t in TASK_TYPES}
        self.task_type_label_var = tk.StringVar(value=tr(self.task_type_var.get()))
        self.task_type_label_var.trace_add(
            "write", lambda *_: self.task_type_var.set(
                type_labels.get(self.task_type_label_var.get(), TASK_TYPES[0])))
        om = tk.OptionMenu(form, self.task_type_label_var, *type_labels)
        om.config(bg=BG3, fg=FG, activebackground=BG3, activeforeground=FG,
                  font=(F_UI, 10), relief="flat", borderwidth=0,
                  highlightthickness=0, padx=10, pady=4)
        om["menu"].config(bg=BG3, fg=FG, font=(F_UI, 10))
        om.grid(row=1, column=1, sticky="w", padx=(0, 6), pady=5)
        self._refresh_task_name_suggestions()

        tk.Button(form, text=tr("＋ 追加"), font=(F_UI, 11, "bold"),
                  bg=BLUE, fg=BG, activebackground="#74c7ec",
                  relief="flat", padx=18, pady=8, cursor="hand2",
                  command=self._add_task
                  ).grid(row=0, column=3, rowspan=2, padx=(4, 16), pady=5, sticky="ns")

        hdr = tk.Frame(parent, bg=BG)
        hdr.pack(fill="x", padx=16, pady=(16, 6))
        tk.Label(hdr, text=tr("タスク一覧"), font=(F_UI, 13, "bold"),
                 bg=BG, fg=FG).pack(side="left")
        self.task_count_var = tk.StringVar(value="")
        tk.Label(hdr, textvariable=self.task_count_var, font=(F_UI, 10),
                 bg=BG, fg=FG_DIM).pack(side="right")

        # タブ全体がすでにスクロールするので、一覧は入れ子のスクロールを持たない
        # （幅いっぱいに広がり、白いスクロールバーも出ない）。
        self.task_list_frame = tk.Frame(parent, bg=BG)
        self.task_list_frame.pack(fill="x", padx=12, pady=(0, 8))

        tk.Label(parent, text=tr("本日の完了"), font=(F_UI, 12, "bold"),
                 bg=BG, fg=FG).pack(anchor="w", padx=16, pady=(6, 0))
        self.done_frame = tk.Frame(parent, bg=BG)
        self.done_frame.pack(fill="x", padx=12, pady=(4, 14))

    # ── 共通のカード部品 ───────────────────────────────────────────

    def _card(self, parent, title: str | None = None, pady=(0, 10)):
        outer = tk.Frame(parent, bg=BG2)
        outer.pack(fill="x", padx=12, pady=pady)
        if title:
            tk.Label(outer, text=title, font=(F_UI, 11, "bold"), bg=BG2, fg=FG,
                     anchor="w").pack(fill="x", padx=14, pady=(12, 6))
        body = tk.Frame(outer, bg=BG2)
        body.pack(fill="x", padx=14, pady=(0, 12) if title else (12, 12))
        return body

    def _auto_wrap(self, label, margin: int = 30):
        """ウィンドウ幅に合わせて文章を折り返す（固定幅だと切れる／余るため）。"""
        label.master.bind(
            "<Configure>",
            lambda e, l=label: l.config(wraplength=max(160, e.width - margin)), add="+")

    def _kpi_grid(self, parent, items, columns: int = 2) -> dict:
        """数字を大きく見せるタイル。items = [(key, ラベル, 色)] → {key: StringVar}"""
        grid = tk.Frame(parent, bg=BG)
        grid.pack(fill="x", padx=8, pady=(0, 6))
        variables = {}
        for i, (key, label, color) in enumerate(items):
            tile = tk.Frame(grid, bg=BG2)
            tile.grid(row=i // columns, column=i % columns, sticky="nsew", padx=4, pady=4)
            grid.grid_columnconfigure(i % columns, weight=1, uniform="kpi")
            tk.Label(tile, text=label, font=(F_UI, 9), bg=BG2, fg=FG_DIM,
                     anchor="w").pack(fill="x", padx=14, pady=(12, 0))
            var = tk.StringVar(value="—")
            tk.Label(tile, textvariable=var, font=(F_UI, 20, "bold"), bg=BG2, fg=color,
                     anchor="w").pack(fill="x", padx=14, pady=(0, 12))
            variables[key] = var
        return variables

    # ── Tab: 記録 ──────────────────────────────────────────────────

    def _build_stats_tab(self, parent):
        hero = tk.Frame(parent, bg=BG2)
        hero.pack(fill="x", padx=12, pady=(14, 8))
        top = tk.Frame(hero, bg=BG2)
        top.pack(fill="x", padx=18, pady=(16, 0))
        self.level_var = tk.StringVar()
        tk.Label(top, textvariable=self.level_var, font=(F_UI, 26, "bold"),
                 bg=BG2, fg=FG).pack(side="left")
        self.rank_var = tk.StringVar()
        tk.Label(top, textvariable=self.rank_var, font=(F_UI, 10, "bold"),
                 bg=BG, fg=PURPLE, padx=10, pady=3).pack(side="left", padx=(12, 0), pady=(10, 0))
        self.exp_bar = ProgressBar(hero, CHART_THEME, height=10)
        self.exp_bar.pack(fill="x", padx=18, pady=(12, 6))
        self.exp_var = tk.StringVar()
        tk.Label(hero, textvariable=self.exp_var, font=(F_UI, 9), bg=BG2, fg=FG_DIM,
                 anchor="w").pack(fill="x", padx=18, pady=(0, 16))

        self._stat_boxes = self._kpi_grid(parent, [
            ("streak", tr("連続日数"), YELLOW), ("tasks", tr("完了したタスク"), GREEN),
            ("today", tr("本日の学習"), PURPLE), ("total", tr("累計の学習"), BLUE)])

        body = self._card(parent, tr("直近7日の学習時間"))
        self.week_chart = BarChart(body, CHART_THEME, height=170, unit=tr("分"), color=PURPLE)
        self.week_chart.empty_text = tr("この7日間の学習記録はまだありません")
        self.week_chart.pack(fill="x")

        self.ach_title_var = tk.StringVar(value=tr("実績"))
        tk.Label(parent, textvariable=self.ach_title_var, font=(F_UI, 12, "bold"),
                 bg=BG, fg=FG).pack(anchor="w", padx=16, pady=(8, 4))
        self.ach_frame = tk.Frame(parent, bg=BG)
        self.ach_frame.pack(fill="x", padx=8, pady=(0, 16))

    # ── Tab: AIコーチ ──────────────────────────────────────────────

    def _build_coach_tab(self, parent):
        head = tk.Frame(parent, bg=BG)
        head.pack(fill="x", padx=16, pady=(14, 2))
        tk.Label(head, text=tr("学習のふりかえり"), font=(F_UI, 14, "bold"),
                 bg=BG, fg=FG).pack(side="left")
        self.coach_btn = tk.Button(
            head, text=tr("今すぐ分析"), font=(F_UI, 10, "bold"),
            bg=PURPLE, fg=BG, activebackground="#b4befe",
            relief="flat", padx=16, pady=6, cursor="hand2",
            command=self._run_analysis)
        self.coach_btn.pack(side="right")

        sub = tk.Frame(parent, bg=BG)
        sub.pack(fill="x", padx=16, pady=(0, 8))
        self.coach_period_var = tk.StringVar(value="")
        # 右側の「最終分析」を先に配置する（先に確保しないと長い期間の説明に押されて切れる）
        self.coach_time_var = tk.StringVar(value="")
        tk.Label(sub, textvariable=self.coach_time_var, font=(F_UI, 8),
                 bg=BG, fg=FG_DIM).pack(side="right", anchor="n", padx=(8, 0))
        period = tk.Label(sub, textvariable=self.coach_period_var, font=(F_UI, 9),
                          bg=BG, fg=FG_DIM, anchor="w", justify="left")
        period.pack(side="left", fill="x", expand=True)
        self._auto_wrap(period, 190)

        self._coach_kpis = self._kpi_grid(parent, [
            ("study", tr("学習時間"), PURPLE), ("days", tr("学習した日"), GREEN),
            ("focus", tr("集中が途切れた回数"), YELLOW), ("early", tr("途中で止めた回数"), RED)])

        comment = self._card(parent, tr("コーチのコメント"))
        self.coach_comment = tk.Label(comment, text="", font=(F_UI, 11), bg=BG2, fg=FG,
                                      justify="left", anchor="w")
        self.coach_comment.pack(fill="x")
        self._auto_wrap(self.coach_comment, 10)

        body = self._card(parent, tr("日ごとの学習時間"))
        self.coach_daily_chart = BarChart(body, CHART_THEME, height=170, unit=tr("分"), color=PURPLE)
        self.coach_daily_chart.pack(fill="x")
        body = self._card(parent, tr("学習した時間帯"))
        self.coach_study_chart = BarChart(body, CHART_THEME, height=150, unit=tr("分"), color=GREEN)
        self.coach_study_chart.pack(fill="x")
        body = self._card(parent, tr("集中が途切れた時間帯"))
        self.coach_distract_chart = BarChart(body, CHART_THEME, height=150, unit=tr("回"), color=YELLOW)
        self.coach_distract_chart.empty_text = tr("集中が途切れた記録はありません")
        self.coach_distract_chart.pack(fill="x")
        body = self._card(parent, tr("よく開いたアプリ"))
        self.coach_app_chart = HBarChart(body, CHART_THEME, unit=tr("回"), color=RED)
        self.coach_app_chart.empty_text = tr("記録はありません")
        self.coach_app_chart.pack(fill="x")

        # AIが学習か娯楽か判断できなかったサイトをここにまとめる（対応は任意・ブロックはしない）
        body = self._card(parent, tr("AIが判断できなかったサイト"))
        explain = tk.Label(
            body, text=tr("学習か娯楽か判断できなかったサイトです。ブロックはせず、ここに記録しています。"
                          "対応は任意で、「学習」か「娯楽」を選ぶと次からその判断が使われます。"),
            font=(F_UI, 9), bg=BG2, fg=FG_DIM, justify="left", anchor="w")
        explain.pack(fill="x", pady=(0, 6))
        self._auto_wrap(explain, 10)
        self.site_review_frame = tk.Frame(body, bg=BG2)
        self.site_review_frame.pack(fill="x")
        self._refresh_site_labels()

        tk.Label(parent, text=tr("データから分かったこと"), font=(F_UI, 12, "bold"),
                 bg=BG, fg=FG).pack(anchor="w", padx=16, pady=(8, 4))
        self.coach_findings_frame = tk.Frame(parent, bg=BG)
        self.coach_findings_frame.pack(fill="x", padx=8, pady=(0, 16))

        # 前回の分析結果があれば、AIを呼ばずにすぐ表示 — 待たせない。
        cached = self.cfg.get("coach_last_result")
        cached_at = self.cfg.get("coach_last_analyzed_at")
        # 別の言語で作られた分析は混ざって見えるので出さない（再分析で今の言語になる）
        if cached and (self.cfg.get("coach_last_language") or "ja") != i18n.get_language():
            cached = ""
        if cached:
            self._set_coach_text(ai_coach.clean_coach_text(cached) or cached)
            self.coach_time_var.set(tr("最終分析 {0}").format(cached_at))
        else:
            self._set_coach_text(tr("「今すぐ分析」を押すと、コーチがこの期間の様子をコメントします。"))
        self._refresh_coach_dashboard()

    def _refresh_coach_dashboard(self):
        """グラフと「分かったこと」を更新する。AIは使わず、保存済みデータだけで計算する。
        ここでの失敗が他の画面を巻き込まないよう、例外は外に出さない。"""
        try:
            sessions = list(self.history.sessions)
            window = ai_coach.select_window(sessions)
            try:
                goal = int(self.cfg.get("daily_goal_minutes") or 120)
            except (TypeError, ValueError):
                goal = 120
            events = list(self.activity_log.events)
            records = list(self.override_log.records)
            data = ai_coach.compute_chart_data(sessions, window, events, records, goal)
            findings = ai_coach.compute_findings(sessions, window, events, records, goal)

            self.coach_period_var.set(tr("分析期間  {0}").format(ai_coach._period_label(window)))
            totals = data["totals"]
            self._coach_kpis["study"].set(tr("{0}分").format(totals['study_minutes']))
            self._coach_kpis["days"].set(tr("{0}日").format(totals['active_days']))
            self._coach_kpis["focus"].set(tr("{0}回").format(totals['episodes']))
            self._coach_kpis["early"].set(tr("{0}回").format(totals['early_stops']))
            self.coach_daily_chart.set(data["daily"], goal)
            self.coach_study_chart.set([(tr(label), v) for label, v in data["study_by_bucket"]])
            self.coach_distract_chart.set(
                [(tr(label), v) for label, v in data["distraction_by_bucket"]])
            self.coach_app_chart.set(data["distraction_by_app"])

            for widget in self.coach_findings_frame.winfo_children():
                widget.destroy()
            if not findings:
                tk.Label(self.coach_findings_frame, text=tr("まだ分かったことはありません。"),
                         font=(F_UI, 10), bg=BG, fg=FG_DIM).pack(anchor="w", padx=8, pady=6)
            for item in findings:
                card = tk.Frame(self.coach_findings_frame, bg=BG2)
                card.pack(fill="x", padx=4, pady=4)
                tk.Frame(card, bg=PURPLE, width=4).pack(side="left", fill="y")
                inner = tk.Frame(card, bg=BG2)
                inner.pack(side="left", fill="x", expand=True, padx=12, pady=10)
                fact = tk.Label(inner, text=item["fact"], font=(F_UI, 10), bg=BG2, fg=FG,
                                justify="left", anchor="w")
                fact.pack(fill="x")
                self._auto_wrap(fact, 40)
                if item.get("hint"):
                    hint = tk.Label(inner, text="💡 " + item["hint"], font=(F_UI, 9),
                                    bg=BG2, fg=GREEN, justify="left", anchor="w")
                    hint.pack(fill="x", pady=(4, 0))
                    self._auto_wrap(hint, 40)
        except Exception:
            return

    # ── Tab: 設定 ──────────────────────────────────────────────────

    def _change_language(self):
        names = {name: code for code, name in i18n.LANGUAGES.items()}
        code = names.get(self.language_var.get(), i18n.DEFAULT_LANGUAGE)
        if code == i18n.normalize(self.cfg.get("language")):
            return
        self.cfg.set("language", code)
        # 変更後の言語でお知らせする（再起動までは今の言語のまま表示される）
        messagebox.showinfo(
            i18n.translate(code, "言語"),
            i18n.translate(code, "言語を変更しました。EvoLockを再起動すると反映されます。"),
            parent=self.root)

    def _build_settings_tab(self, parent):
        # ── 言語 ───────────────────────────────────────────────────────
        lang_frame = tk.LabelFrame(parent, text=" 言語 / Language / Ngôn ngữ ", bg=BG, fg=FG,
                                   font=(F_UI, 11, "bold"), relief="flat", padx=12, pady=8)
        lang_frame.pack(fill="x", padx=12, pady=(14, 0))
        self.language_var = tk.StringVar(
            value=i18n.LANGUAGES[i18n.normalize(self.cfg.get("language"))])
        language_box = ttk.Combobox(lang_frame, textvariable=self.language_var, state="readonly",
                                    values=list(i18n.LANGUAGES.values()), width=22,
                                    font=(F_UI, 10))
        language_box.pack(anchor="w")
        language_box.bind("<<ComboboxSelected>>", lambda e: self._change_language())

        # ── セッションの保護（Gmailにコードを送る） ─────────────────────
        pw_frame = tk.LabelFrame(parent, text=tr(" セッションの保護 "), bg=BG, fg=FG,
                                 font=(F_UI, 11, "bold"), relief="flat", padx=12, pady=12)
        pw_frame.pack(fill="x", padx=12, pady=(14, 8))
        tk.Label(pw_frame,
                 text=tr("学習を始めるたびに、下のGmailへ6桁のコードを送ります。\n"
                      "早めに終了したり設定を変えるには、そのコードが必要です。"),
                 wraplength=440, justify="left", font=(F_UI, 10), bg=BG, fg=FG_DIM
                 ).pack(anchor="w", pady=(0, 10))

        tk.Label(pw_frame, text=tr("コードを受け取るGmail"), font=(F_UI, 9, "bold"),
                 bg=BG, fg=FG).pack(anchor="w")
        self.gmail_addr_var = tk.StringVar(value=self.cfg.get("gmail_address") or "")
        tk.Entry(pw_frame, textvariable=self.gmail_addr_var,
                 font=(F_UI, 11), bg=BG3, fg=FG, insertbackground=FG, relief="flat"
                 ).pack(fill="x", ipady=7, pady=(4, 8))
        gmail_row = tk.Frame(pw_frame, bg=BG)
        gmail_row.pack(fill="x", pady=(0, 6))
        tk.Button(gmail_row, text=tr("保存"), font=(F_UI, 10, "bold"),
                  bg=GREEN, fg=BG, relief="flat", padx=14, pady=6, cursor="hand2",
                  command=self._save_gmail_settings).pack(side="left", padx=(0, 6))
        self.gmail_test_btn = tk.Button(
            gmail_row, text=tr("📧 テスト送信"), font=(F_UI, 10),
            bg=BG3, fg=PURPLE, relief="flat", padx=12, pady=6, cursor="hand2",
            command=self._test_gmail_send)
        self.gmail_test_btn.pack(side="left", padx=(0, 6))
        tk.Button(gmail_row, text=tr("解除"), font=(F_UI, 10),
                  bg=BG3, fg=RED, relief="flat", padx=12, pady=6, cursor="hand2",
                  command=self._clear_gmail_settings).pack(side="left")

        self.gmail_status_var = tk.StringVar()
        self.gmail_status_label = tk.Label(
            pw_frame, textvariable=self.gmail_status_var, font=(F_UI, 9),
            bg=BG, fg=FG_DIM, justify="left", wraplength=440)
        self.gmail_status_label.pack(anchor="w", pady=(2, 0))

        # 旧方式（自分で決めるローカルコード）。画面には出さない。以前の設定を
        # 持つ人の動作を壊さないために部品だけ残している。
        legacy = tk.Frame(parent)
        self.protection_var = tk.BooleanVar(value=bool(self.cfg.get("protection_enabled")))
        tk.Checkbutton(legacy, variable=self.protection_var, command=self._toggle_protection)
        self.pw_status_var = tk.StringVar()
        tk.Label(legacy, textvariable=self.pw_status_var)
        self.manage_code_btn = tk.Button(legacy, text=tr("保護コードを変更"),
                                         command=self._setup_protection_code)

        # 保存処理が参照する入力欄の値（送信元の設定を隠す場合も空のまま存在する）
        self.oauth_client_id_var = tk.StringVar()
        self.oauth_client_secret_var = tk.StringVar()
        self.gmail_app_pw_var = tk.StringVar()

        # 「Googleでログイン」は誰にでも見える（初回に1回だけ押す）。必要な時だけ表示する。
        self.login_row = tk.Frame(pw_frame, bg=BG)
        self.login_row.pack(fill="x", before=self.gmail_status_label)
        self.oauth_login_btn = tk.Button(
            self.login_row, text=tr("🔐 Googleでログイン"),
            font=(F_UI, 10, "bold"), bg=BG3, fg=GREEN, relief="flat", padx=12, pady=6,
            cursor="hand2", command=self._login_google)

        # ── 送信元の設定（開発者向け） ───────────────────────────────────
        # Client ID/Secretは製品側で用意するもの。同梱済みなら利用者には見せない。
        if self._show_sender_setup():
            sender = self._disclosure(parent, tr("送信元の設定（初回のみ）"))
            sender_frame = tk.Frame(sender, bg=BG)
            sender_frame.pack(fill="x", padx=12, pady=(0, 8))
            tk.Label(sender_frame,
                     text=tr("コードを送るためのGoogleアカウントを1回だけ設定します。\n"
                          "「Googleでログイン」を使うとパスワードは入力しません。"),
                     font=(F_UI, 9), bg=BG, fg=FG_DIM, justify="left"
                     ).pack(anchor="w", pady=(0, 8))

            oauth_row = tk.Frame(sender_frame, bg=BG)
            oauth_row.pack(fill="x", pady=(0, 6))
            tk.Label(oauth_row, text="Client ID:", font=(F_UI, 9), bg=BG, fg=FG
                     ).pack(side="left", padx=(0, 6))
            tk.Entry(oauth_row, textvariable=self.oauth_client_id_var, width=24,
                     font=(F_MONO, 8), bg=BG3, fg=FG, insertbackground=FG, relief="flat"
                     ).pack(side="left", padx=(0, 10), ipady=3)
            tk.Label(oauth_row, text="Secret:", font=(F_UI, 9), bg=BG, fg=FG
                     ).pack(side="left", padx=(0, 6))
            tk.Entry(oauth_row, textvariable=self.oauth_client_secret_var, width=14,
                     font=(F_MONO, 8), bg=BG3, fg=FG, insertbackground=FG,
                     relief="flat", show="●").pack(side="left", ipady=3)

            tk.Button(sender_frame, text=tr("📄 JSONファイルから読み込む"), font=(F_UI, 9),
                      bg=BG3, fg=FG, relief="flat", padx=10, pady=4, cursor="hand2",
                      command=self._import_client_json).pack(anchor="w", pady=(0, 6))

            app_pw_row = tk.Frame(sender_frame, bg=BG)
            app_pw_row.pack(fill="x", pady=(0, 6))
            tk.Label(app_pw_row, text=tr("またはアプリパスワード:"), font=(F_UI, 9), bg=BG, fg=FG
                     ).pack(side="left", padx=(0, 6))
            tk.Entry(app_pw_row, textvariable=self.gmail_app_pw_var, width=20,
                     font=(F_MONO, 9), bg=BG3, fg=FG, insertbackground=FG,
                     relief="flat", show="●").pack(side="left", ipady=3)
            tk.Label(sender_frame,
                     text=tr("入力した情報はWindows資格情報マネージャーに保存され、設定ファイルには書き込まれません。\n"
                          "入力後は上の「保存」を押してください。"),
                     font=(F_UI, 8), bg=BG, fg=FG_DIM, justify="left"
                     ).pack(anchor="w", pady=(4, 0))
        self._refresh_gmail_status()

        st_frame = tk.LabelFrame(parent, text=tr(" 起動 "), bg=BG, fg=FG,
                                 font=(F_UI, 11, "bold"), relief="flat", padx=12, pady=8)
        st_frame.pack(fill="x", padx=12, pady=(8, 4))

        self.startup_var = tk.BooleanVar(value=is_in_startup())
        tk.Checkbutton(st_frame, text=tr("Windows起動時にEvoLockを起動"),
                       variable=self.startup_var, font=(F_UI, 10),
                       bg=BG, fg=FG, selectcolor=BG3, activebackground=BG,
                       command=self._toggle_startup
                       ).pack(anchor="w")

        self.startup_msg = tk.Label(st_frame, text="", font=(F_UI, 8),
                                    bg=BG, fg=GREEN)
        self.startup_msg.pack(anchor="w")

        privacy = tk.LabelFrame(parent, text=tr(" 画面の読み取りとプライバシー "),
                                bg=BG, fg=FG, font=(F_UI, 11, "bold"), relief="flat",
                                padx=12, pady=8)
        privacy.pack(fill="x", padx=12, pady=(8, 12))
        self.screen_ai_var = tk.BooleanVar(value=self.blocker.screen_enabled)
        tk.Checkbutton(privacy, text=tr("学習中の画面をAIで確認する"), variable=self.screen_ai_var,
                       command=self._toggle_screen_ai, bg=BG, fg=FG, selectcolor=BG3,
                       activebackground=BG).pack(anchor="w")
        tk.Label(privacy, text=tr("有効にすると、学習中は画面全体を定期的に読み取ります。\n"
                              "画面にある個人情報も含まれるため、必要なときだけ有効にしてください。\n"
                              "オフでも、登録済みアプリのブロックは動作します。"),
                 bg=BG, fg=FG_DIM, justify="left", wraplength=470).pack(anchor="w", pady=6)
        self.screen_ai_status_var = tk.StringVar()
        tk.Label(privacy, textvariable=self.screen_ai_status_var, bg=BG, fg=FG_DIM,
                 justify="left", wraplength=470).pack(anchor="w")
        self._refresh_screen_ai_status()
        self._refresh_settings()

    # ── Task logic ─────────────────────────────────────────────────

    def _add_task(self):
        name = self.task_name_var.get().strip()
        if not name:
            return
        task_type = self.task_type_var.get()
        self.task_mgr.add(name, task_type)
        self._remember_task_name_suggestion(task_type, name)
        self.task_name_var.set("")
        self._refresh_task_list()
        self._refresh_task_name_suggestions()
        self._log(tr("タスク追加: {0}").format(name))

    def _remember_task_name_suggestion(self, task_type: str, name: str):
        """候補リストに追加 — タスク履歴（統計用）とは別に持つので、候補だけ
        後から削除しても完了実績やStreakには影響しない。"""
        store = self.cfg.get("task_name_suggestions") or {}
        names = store.get(task_type, [])
        if name in names:
            names.remove(name)
        names.append(name)  # 最後尾 = 最新
        store[task_type] = names[-30:]  # 際限なく増えないよう上限
        self.cfg.set("task_name_suggestions", store)

    def _refresh_task_name_suggestions(self):
        """種類ごとの候補（自分で削除できる独立リスト）をコンボボックスに出す
        — 最近使ったものを先頭に。"""
        if not hasattr(self, "task_name_combo"):
            return
        current_type = self.task_type_var.get()
        store = self.cfg.get("task_name_suggestions") or {}
        names = list(reversed(store.get(current_type, [])))  # 新しい順
        self.task_name_combo["values"] = names

    def _open_suggestion_manager(self):
        dlg = tk.Toplevel(self.root)
        dlg.title(tr("タスク名の候補を管理"))
        dlg.geometry("300x360")
        dlg.configure(bg=BG)
        dlg.grab_set()
        dlg.transient(self.root)

        tk.Label(dlg, text=tr("タスク名の候補を管理"), font=(F_UI, 11, "bold"),
                 bg=BG, fg=PURPLE).pack(pady=(16, 2), padx=16, anchor="w")
        tk.Label(dlg, text=tr("種類「{0}」の候補。✕で削除できます。").format(tr(self.task_type_var.get())),
                 font=(F_UI, 8), bg=BG, fg=FG_DIM, wraplength=260, justify="left"
                 ).pack(padx=16, anchor="w", pady=(0, 8))

        list_frame = tk.Frame(dlg, bg=BG)
        list_frame.pack(fill="both", expand=True, padx=16)

        def _populate():
            for w in list_frame.winfo_children():
                w.destroy()
            store = self.cfg.get("task_name_suggestions") or {}
            names = list(reversed(store.get(self.task_type_var.get(), [])))
            if not names:
                tk.Label(list_frame, text=tr("候補がありません。"),
                         font=(F_UI, 9), bg=BG, fg=FG_DIM).pack(anchor="w", pady=8)
                return
            for name in names:
                row = tk.Frame(list_frame, bg=BG2)
                row.pack(fill="x", pady=2)
                tk.Label(row, text=f"  {name}", font=(F_UI, 9),
                         bg=BG2, fg=FG, anchor="w").pack(side="left", fill="x", expand=True)
                tk.Button(row, text="✕", font=(F_UI, 8),
                          bg=BG2, fg=RED, activebackground=BG2,
                          relief="flat", padx=6, pady=2, cursor="hand2",
                          command=lambda n=name: _remove(n)
                          ).pack(side="right", padx=4)

        def _remove(name: str):
            store = self.cfg.get("task_name_suggestions") or {}
            names = store.get(self.task_type_var.get(), [])
            if name in names:
                names.remove(name)
                store[self.task_type_var.get()] = names
                self.cfg.set("task_name_suggestions", store)
            self._refresh_task_name_suggestions()
            _populate()

        _populate()

        tk.Button(dlg, text=tr("閉じる"), font=(F_UI, 9),
                  bg=BG3, fg=FG, relief="flat", padx=12, pady=6, cursor="hand2",
                  command=dlg.destroy
                  ).pack(pady=(8, 16))

    def _confirm_complete(self, task_id: int, task_name: str):
        ok = messagebox.askyesno(
            tr("完了確認"),
            tr("以下のタスクを完了しましたか？\n「{0}」\n\n完了するとアプリのロックが解除されます！").format(task_name),
            parent=self.root)
        if not ok:
            return
        self.task_mgr.complete(task_id)
        self._refresh_task_list()
        self._log(tr("完了: {0} → ロック解除！").format(task_name))
        result = self.game.on_task_complete()
        self._award_and_notify(result)
        self._enter_unlocked_by_task()

    def _enter_unlocked_by_task(self):
        if self.study_timer:
            self.study_timer.stop()
        self._reset_timers()
        self._enter_unlocked()

    def _delete_task(self, task_id: int):
        self.task_mgr.delete(task_id)
        self._refresh_task_list()

    def _refresh_task_list(self):
        for w in self.task_list_frame.winfo_children():
            w.destroy()
        for w in self.done_frame.winfo_children():
            w.destroy()

        pending = self.task_mgr.pending()
        done = self.task_mgr.completed_today()
        self.task_count_var.set(tr("{0}件待機 · {1}件本日完了").format(len(pending), len(done)))

        type_colors = {"学習": PURPLE, "仕事": BLUE, "読書": YELLOW, "運動": GREEN}
        card_bg, card_hover = BG2, "#26334A"

        if not pending:
            empty = tk.Frame(self.task_list_frame, bg=BG2)
            empty.pack(fill="x", padx=8, pady=6)
            tk.Label(empty, text="✓", font=(F_UI, 22), bg=BG2, fg=GREEN).pack(pady=(18, 0))
            tk.Label(empty, text=tr("タスクがありません"), font=(F_UI, 11, "bold"),
                     bg=BG2, fg=FG).pack()
            tk.Label(empty, text=tr("上のフォームからタスクを追加できます"),
                     font=(F_UI, 9), bg=BG2, fg=FG_DIM).pack(pady=(2, 18))
        else:
            for task in pending:
                color = type_colors.get(task.task_type, FG_DIM)
                card = tk.Frame(self.task_list_frame, bg=card_bg)
                card.pack(fill="x", padx=8, pady=4)
                tk.Frame(card, bg=color, width=4).pack(side="left", fill="y")
                body = tk.Frame(card, bg=card_bg)
                body.pack(side="left", fill="both", expand=True, padx=(12, 10), pady=10)

                tid, tname = task.id, task.name
                # 右側のボタンを先に配置 — 長いタスク名に押されて隠れないように。
                done_btn = tk.Button(body, text=tr("✓ 完了"), font=(F_UI, 10, "bold"),
                                     bg=GREEN, fg=BG, activebackground="#94e2d5",
                                     relief="flat", padx=16, pady=5, cursor="hand2",
                                     command=lambda i=tid, n=tname: self._confirm_complete(i, n))
                done_btn.pack(side="right")
                del_btn = tk.Button(body, text="✕", font=(F_UI, 10),
                                    bg=card_bg, fg=FG_DIM, activebackground=BG3,
                                    activeforeground=RED, relief="flat", padx=10, pady=5,
                                    cursor="hand2", bd=0,
                                    command=lambda i=tid: self._delete_task(i))
                del_btn.pack(side="right", padx=(0, 8))
                del_btn.bind("<Enter>", lambda e, b=del_btn: b.config(fg=RED))
                del_btn.bind("<Leave>", lambda e, b=del_btn: b.config(fg=FG_DIM))

                tk.Label(body, text=tr(task.task_type), font=(F_UI, 8, "bold"),
                         bg=BG, fg=color, padx=9, pady=2).pack(side="left")
                name_lbl = tk.Label(body, text=task.name, font=(F_UI, 12),
                                    bg=card_bg, fg=FG, anchor="w", justify="left",
                                    wraplength=260)
                name_lbl.pack(side="left", padx=(12, 8), fill="x", expand=True)

                def _hover(on, card=card, body=body, name_lbl=name_lbl, del_btn=del_btn):
                    bg = card_hover if on else card_bg
                    for w in (card, body, name_lbl, del_btn):
                        w.config(bg=bg)
                for w in (card, body, name_lbl):
                    w.bind("<Enter>", lambda e, h=_hover: h(True), add="+")
                    w.bind("<Leave>", lambda e, h=_hover, c=card: h(
                        c.winfo_containing(e.x_root, e.y_root) is not None
                        and str(c.winfo_containing(e.x_root, e.y_root)).startswith(str(c))),
                        add="+")

        if not done:
            tk.Label(self.done_frame, text=tr("まだ完了したタスクはありません"),
                     font=(F_UI, 9), bg=BG, fg=FG_DIM, anchor="w"
                     ).pack(fill="x", padx=8, pady=4)
        else:
            for task in done:
                line = tk.Frame(self.done_frame, bg=BG2)
                line.pack(fill="x", padx=8, pady=2)
                tk.Label(line, text="✓", font=(F_UI, 10, "bold"), bg=BG2, fg=GREEN
                         ).pack(side="left", padx=(10, 8), pady=6)
                tk.Label(line, text=task.name, font=(F_UI, 10), bg=BG2, fg=FG,
                         anchor="w").pack(side="left", fill="x", expand=True)
                tk.Label(line, text=str(task.completed_at), font=(F_UI, 9),
                         bg=BG2, fg=FG_DIM).pack(side="right", padx=10)

    # ── Stats ──────────────────────────────────────────────────────

    def _refresh_day(self):
        if self.game.stats.today_date != str(datetime.now().date()):
            self._refresh_stats()
            self._refresh_history_display()
        self._day_after_id = self.root.after(60_000, self._refresh_day)

    def _refresh_stats(self):
        self.game._check_streak()
        s = self.game.stats
        exp_now, exp_needed = self.game.get_exp_progress()
        self.rank_var.set(tr(self.game.get_rank()))
        self.level_var.set(f"Level {s.level}")
        remaining = max(0, exp_needed - exp_now)
        self.exp_var.set(tr("{0} / {1} EXP  ・  次のレベルまであと {2}").format(exp_now, exp_needed, remaining))
        self.exp_bar.set(exp_now / exp_needed if exp_needed else 0)
        self._stat_boxes["streak"].set(tr("{0}日").format(s.streak))
        self._stat_boxes["tasks"].set(str(s.total_tasks))
        self._stat_boxes["today"].set(tr("{0}分").format(s.today_study_minutes))
        self._stat_boxes["total"].set(tr("{0}分").format(s.total_study_minutes))

        try:
            today = datetime.now().date()
            by_day: dict[str, int] = {}
            for session in self.history.sessions:
                if session.session_type == "study":
                    by_day[session.date] = by_day.get(session.date, 0) + session.duration_minutes
            days = [today - timedelta(days=6 - i) for i in range(7)]
            try:
                goal = int(self.cfg.get("daily_goal_minutes") or 120)
            except (TypeError, ValueError):
                goal = 120
            self.week_chart.set([(d.strftime("%m/%d"), by_day.get(str(d), 0)) for d in days], goal)
        except Exception:
            pass  # グラフの失敗で統計画面全体を止めない

        for w in self.ach_frame.winfo_children():
            w.destroy()
        unlocked = set(s.unlocked_achievements)
        self.ach_title_var.set(
            tr("実績  {0} / {1}").format(sum(1 for key, _, _ in ACHIEVEMENTS if key in unlocked), len(ACHIEVEMENTS)))
        for i, (key, name, desc) in enumerate(ACHIEVEMENTS):
            done = key in unlocked
            card = tk.Frame(self.ach_frame, bg=BG2)
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=4, pady=4)
            self.ach_frame.grid_columnconfigure(i % 2, weight=1, uniform="ach")
            tk.Frame(card, bg=YELLOW if done else BG3, width=4).pack(side="left", fill="y")
            inner = tk.Frame(card, bg=BG2)
            inner.pack(side="left", fill="both", expand=True, padx=12, pady=10)
            tk.Label(inner, text=("🏆 " if done else "🔒 ") + tr(name), font=(F_UI, 10, "bold"),
                     bg=BG2, fg=YELLOW if done else FG_DIM, anchor="w").pack(fill="x")
            tk.Label(inner, text=tr(desc), font=(F_UI, 8), bg=BG2,
                     fg=FG if done else FG_DIM, anchor="w", justify="left",
                     wraplength=190).pack(fill="x", pady=(2, 0))

    def _award_and_notify(self, result: dict):
        msgs = []
        if result.get("checkin_exp", 0) > 0:
            msgs.append(tr("📅 デイリーボーナス +{0} EXP").format(result['checkin_exp']))
        if result.get("exp", 0) > 0:
            mult = result.get("mult", 1.0)
            mult_str = f" (x{mult})" if mult != 1.0 else ""
            msgs.append(f"+{result['exp']} EXP{mult_str}")
        if result.get("leveled"):
            msgs.append(tr("レベルアップ！→ {0}").format(self.game.stats.level))
        for key in result.get("achievements", []):
            name, _ = self.game.get_achievement_info(key)
            name = tr(name)
            msgs.append(tr("実績解除: {0}！").format(name))
        if msgs:
            self._log("  ".join(msgs))
        self._refresh_stats()

    # ── History display ────────────────────────────────────────────

    def _refresh_history_display(self):
        for w in self.hist_frame.winfo_children():
            w.destroy()

        sessions = self.history.today()
        if not sessions:
            tk.Label(self.hist_frame, text=tr("  本日のセッションはまだありません。"),
                     font=(F_UI, 9), bg=BG2, fg=FG_DIM
                     ).pack(anchor="w", padx=8, pady=4)
        else:
            for s in sessions[-5:]:
                icon  = "📚" if s.session_type == "study" else "🎮"
                label = tr("学習") if s.session_type == "study" else tr("プレイ")
                color = GREEN if s.session_type == "study" else BLUE
                tk.Label(self.hist_frame,
                         text=tr("  {0} {1}  {2}–{3}  ({4}分)").format(icon, label, s.start_time, s.end_time, s.duration_minutes),
                         font=(F_UI, 9), bg=BG2, fg=color, anchor="w"
                         ).pack(fill="x", padx=4, pady=1)

        # 1日の目標は設定画面では変えない（目安の分析はAIコーチの役割）。
        try:
            goal = int(self.cfg.get("daily_goal_minutes") or 120)
        except (TypeError, ValueError):
            goal = 120
        studied = self.history.today_study_minutes()
        pct = min(100, int(studied / goal * 100)) if goal > 0 else 0
        self.goal_var.set(tr("📚 本日の目標: {0} / {1}分  ({2}%)").format(studied, goal, pct))
        self.goal_bar.set(pct / 100)

    # ── AI Coach ───────────────────────────────────────────────────

    def _run_analysis(self, auto: bool = False):
        if getattr(self, "_coach_busy", False):
            if auto:
                self._coach_pending = True
            return
        self._coach_busy = True
        self.coach_btn.config(state="disabled", text=tr("分析中..."))
        self._set_coach_text(tr("分析しています。ほかの画面はそのまま使えます。"))
        self._refresh_coach_dashboard()  # グラフはAIを待たずに先に最新化する
        try:
            api_key      = self.cfg.get("anthropic_api_key") or ""
            # AIコーチは長文テキスト生成 — Screen AI用の軽量ビジョンモデルとは
            # 別に、専用モデルがあればそれを使う（未設定なら共用にフォールバック）。
            ollama_model = self.cfg.get("coach_ollama_model") or self.cfg.get("ollama_model") or ""
            all_sessions = deepcopy(self.history.sessions)
            # 直近7日が空なら、データのある直近の週に切り替える
            window       = ai_coach.select_window(all_sessions)
            sessions     = window["sessions"]
            # 古い週を分析する時は「今週のパスワード使用0回」を事実として渡さない
            pw_summary   = None if window["stale"] else self.pw_logger.summary(7)
            task_stats   = ai_coach.summarize_tasks(self.task_mgr.tasks)
            streak       = self.game.stats.streak
            try:
                goal_minutes = int(self.cfg.get("daily_goal_minutes") or 120)
            except Exception:
                goal_minutes = 120
            findings     = ai_coach.compute_findings(
                all_sessions, window, list(self.activity_log.events),
                list(self.override_log.records), goal_minutes)
        except Exception:
            self._finish_analysis(None, auto)
            return

        def _worker():
            try:
                result       = ai_coach.analyze(api_key, sessions, ollama_model, pw_summary,
                                                 task_stats=task_stats, streak=streak,
                                                 goal_minutes=goal_minutes,
                                                 window=window, findings=findings,
                                                 language=i18n.get_language())
            except Exception:
                result = None
            try:
                self.root.after(0, lambda: self._finish_analysis(result, auto))
            except (RuntimeError, tk.TclError):
                pass  # Window was closed while the backend was responding.

        try:
            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            self._finish_analysis(None, auto)

    def _finish_analysis(self, text, auto: bool = False):
        try:
            if text is None:
                self._set_coach_text(tr("分析できませんでした。しばらくしてから、もう一度お試しください。"))
                return
            self._set_coach_text(text)
            now_str = datetime.now().strftime("%m/%d %H:%M")
            try:
                self.cfg.set_many({"coach_last_result": text,
                                   "coach_last_analyzed_at": now_str,
                                   "coach_last_language": i18n.get_language()})
            except Exception:
                if hasattr(self, "coach_time_var"):
                    self.coach_time_var.set(tr("分析結果を保存できませんでした。再分析できます。"))
                return
            if hasattr(self, "coach_time_var"):
                self.coach_time_var.set(tr("最終分析: {0}（最新）").format(now_str))
            if auto:
                self._log(tr("🤖 AIコーチ: 学習セッションの分析ができました"))
        finally:
            self._coach_busy = False
            self.coach_btn.config(state="normal", text=tr("今すぐ分析"))
            if getattr(self, "_coach_pending", False):
                self._coach_pending = False
                self._run_analysis(auto=True)

    def _set_coach_text(self, text: str):
        self.coach_comment.config(text=text)

    # ── Settings ───────────────────────────────────────────────────

    def _refresh_settings(self):
        enabled = bool(self.cfg.get("protection_enabled"))
        self.protection_var.set(enabled)
        self.pw_status_var.set(tr("有効：自分で設定したEvoLockコードを使います。") if enabled else
                               tr("オフ：終了前に確認します。学習した時間は記録されます。"))
        if enabled:
            self.manage_code_btn.pack(anchor="w", pady=(8, 0))
        else:
            self.manage_code_btn.pack_forget()

    def _toggle_protection(self):
        if self.state == "studying":
            self._refresh_settings()
            messagebox.showinfo(tr("学習中"), tr("保護設定はセッション終了後に変更できます。"), parent=self.root)
            return
        if self.protection_var.get():
            if not self._setup_protection_code():
                self._refresh_settings()
        else:
            if self.cfg.get("protection_enabled") and not self._check_password("disable_protection"):
                self._refresh_settings()
                return
            self.cfg.set("protection_enabled", False)
            self._refresh_settings()

    def _setup_protection_code(self):
        if self.state == "studying":
            messagebox.showinfo(tr("学習中"), tr("コードはセッション終了後に変更できます。"), parent=self.root)
            return False
        if self.cfg.get("protection_enabled") and not self._check_password("change_code"):
            return False
        code = simpledialog.askstring(tr("保護コードを設定"), tr("覚えられる数字6桁を入力してください。\nGmailのパスワードではありません。忘れないよう保管してください。"), parent=self.root, show="●")
        if code is None:
            return False
        if not re.fullmatch(r"[0-9]{6}", code):
            messagebox.showerror(tr("コードの形式"), tr("数字6桁で入力してください。"), parent=self.root)
            return False
        confirm = simpledialog.askstring(tr("コードを確認"), tr("確認のため、同じコードをもう一度入力してください。"), parent=self.root, show="●")
        if confirm is None:
            return False
        if code != confirm:
            messagebox.showerror(tr("コードが一致しません"), tr("設定は変更されていません。もう一度お試しください。"), parent=self.root)
            return False
        self.cfg.set_password(code)
        self.cfg.set("protection_enabled", True)
        self._refresh_settings()
        return True

    def _confirm_early_stop(self):
        dlg = tk.Toplevel(self.root)
        dlg.title(tr("セッションを終了しますか？"))
        dlg.configure(bg=BG)
        dlg.transient(self.root)
        dlg.grab_set()
        result = [False]
        remaining = fmt_time(self.study_timer.remaining) if self.study_timer else ""
        tk.Label(dlg, text=tr("残り {0}\nここまでの学習時間は記録されます。").format(remaining), bg=BG, fg=FG,
                 font=(F_UI, 12), padx=24, pady=24).pack()
        buttons = tk.Frame(dlg, bg=BG)
        buttons.pack(padx=20, pady=(0, 20))
        def finish():
            result[0] = True
            dlg.destroy()
        keep = tk.Button(buttons, text=tr("学習を続ける"), command=dlg.destroy, bg=GREEN, fg=BG,
                         relief="flat", padx=16, pady=10)
        keep.pack(side="left", padx=5)
        tk.Button(buttons, text=tr("早めに終了する"), command=finish, bg=BG3, fg=FG,
                  relief="flat", padx=16, pady=10).pack(side="left", padx=5)
        dlg.bind("<Escape>", lambda event: dlg.destroy())
        keep.focus_set()
        dlg.wait_window()
        return result[0]

    def _generate_password(self):
        if self.cfg.has_password():
            if not self._check_password():
                return

        pw, emergency = self.cfg.generate_random_password(length=10)
        # config.jsonのメモには書かない（ファイルを共有したら即バレる）が、
        # Windows資格情報マネージャーには保存する — Gmailが主な抑止力になった
        # 今、パスワードは「予備」の役割なので、忘れて詰むより確認できる方を
        # 優先する。
        session_code.save_local_password(pw)
        self._refresh_settings()
        self._log(tr("ランダムパスワードを生成しました。「確認」ボタンでいつでも見返せます。"))
        self._show_password_dialog(pw, emergency)

    def _show_password_dialog(self, pw: str, emergency: str):
        dlg = tk.Toplevel(self.root)
        dlg.title(tr("パスワードを保存してください"))
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.transient(self.root)

        # ── メインパスワード ───────────────────────────────────────
        tk.Label(dlg, text=tr("🔐 メインパスワード"),
                 font=(F_UI, 10, "bold"), bg=BG, fg=PURPLE
                 ).pack(pady=(20, 2), padx=24, anchor="w")
        tk.Label(dlg, text=tr("信頼できる人に渡す。自分では持たない。"),
                 font=(F_UI, 8), bg=BG, fg=FG_DIM
                 ).pack(padx=24, anchor="w")

        pw_box = tk.Frame(dlg, bg=BG2, pady=10)
        pw_box.pack(fill="x", padx=24, pady=(6, 4))
        tk.Label(pw_box, text=pw, font=(F_MONO, 22, "bold"),
                 bg=BG2, fg=GREEN).pack(side="left", padx=12)

        def _copy_pw():
            dlg.clipboard_clear()
            dlg.clipboard_append(pw)
            btn_copy_pw.config(text=tr("✓ コピー済み"))
        btn_copy_pw = tk.Button(pw_box, text=tr("📋 コピー"), font=(F_UI, 9),
                                bg=BG3, fg=FG, relief="flat", padx=8, pady=4,
                                cursor="hand2", command=_copy_pw)
        btn_copy_pw.pack(side="right", padx=8)

        # ── 緊急コード ─────────────────────────────────────────────
        tk.Label(dlg, text=tr("🆘 緊急コード"),
                 font=(F_UI, 10, "bold"), bg=BG, fg=YELLOW
                 ).pack(pady=(14, 2), padx=24, anchor="w")
        tk.Label(dlg, text=tr("自分だけが持つ。本当に緊急の時だけ使用。使用は記録される。"),
                 font=(F_UI, 8), bg=BG, fg=FG_DIM
                 ).pack(padx=24, anchor="w")

        em_box = tk.Frame(dlg, bg=BG2, pady=10)
        em_box.pack(fill="x", padx=24, pady=(6, 4))
        tk.Label(em_box, text=emergency, font=(F_MONO, 28, "bold"),
                 bg=BG2, fg=YELLOW).pack(side="left", padx=12)

        def _copy_em():
            dlg.clipboard_clear()
            dlg.clipboard_append(emergency)
            btn_copy_em.config(text=tr("✓ コピー済み"))
        btn_copy_em = tk.Button(em_box, text=tr("📋 コピー"), font=(F_UI, 9),
                                bg=BG3, fg=FG, relief="flat", padx=8, pady=4,
                                cursor="hand2", command=_copy_em)
        btn_copy_em.pack(side="right", padx=8)

        tk.Label(dlg, text=tr("⚠️ 閉じると二度と確認できません！"),
                 font=(F_UI, 9, "bold"), bg=BG, fg=RED
                 ).pack(pady=(12, 4))

        tk.Button(dlg, text=tr("確認しました — 閉じる"),
                  font=(F_UI, 10, "bold"),
                  bg=RED, fg=BG, relief="flat", padx=16, pady=8,
                  cursor="hand2", command=dlg.destroy
                  ).pack(pady=(4, 20))

    def _show_auto_password_dialog(self, pw: str, emergency: str):
        dlg = tk.Toplevel(self.root)
        dlg.title(tr("パスワードを保存してください"))
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.transient(self.root)

        tk.Label(dlg, text=tr("🔐 パスワードが自動生成されました"),
                 font=(F_UI, 11, "bold"), bg=BG, fg=PURPLE
                 ).pack(pady=(20, 2), padx=24)
        tk.Label(dlg, text=tr("必ずメモしてください。閉じると確認できません。"),
                 font=(F_UI, 8), bg=BG, fg=FG_DIM
                 ).pack(padx=24, pady=(0, 10))

        tk.Label(dlg, text=tr("パスワード:"), font=(F_UI, 9, "bold"), bg=BG, fg=FG
                 ).pack(anchor="w", padx=24)
        pw_box = tk.Frame(dlg, bg=BG2, pady=10)
        pw_box.pack(fill="x", padx=24, pady=(4, 8))
        tk.Label(pw_box, text=pw, font=(F_MONO, 22, "bold"),
                 bg=BG2, fg=GREEN).pack(side="left", padx=12)

        def _copy_pw():
            dlg.clipboard_clear()
            dlg.clipboard_append(pw)
            btn_copy_pw.config(text="✓")
        btn_copy_pw = tk.Button(pw_box, text=tr("📋 コピー"), font=(F_UI, 9),
                                bg=BG3, fg=FG, relief="flat", padx=8, pady=4,
                                cursor="hand2", command=_copy_pw)
        btn_copy_pw.pack(side="right", padx=8)

        tk.Label(dlg, text=tr("🆘 緊急コード:"), font=(F_UI, 9, "bold"), bg=BG, fg=YELLOW
                 ).pack(anchor="w", padx=24)
        em_box = tk.Frame(dlg, bg=BG2, pady=10)
        em_box.pack(fill="x", padx=24, pady=(4, 8))
        tk.Label(em_box, text=emergency, font=(F_MONO, 22, "bold"),
                 bg=BG2, fg=YELLOW).pack(side="left", padx=12)

        def _copy_em():
            dlg.clipboard_clear()
            dlg.clipboard_append(emergency)
            btn_copy_em.config(text="✓")
        btn_copy_em = tk.Button(em_box, text=tr("📋 コピー"), font=(F_UI, 9),
                                bg=BG3, fg=FG, relief="flat", padx=8, pady=4,
                                cursor="hand2", command=_copy_em)
        btn_copy_em.pack(side="right", padx=8)

        tk.Label(dlg, text=tr("⚠️ 閉じると二度と確認できません！"),
                 font=(F_UI, 9, "bold"), bg=BG, fg=RED
                 ).pack(pady=(8, 4))
        tk.Button(dlg, text=tr("メモしました — 学習開始"),
                  font=(F_UI, 10, "bold"),
                  bg=GREEN, fg=BG, relief="flat", padx=16, pady=8,
                  cursor="hand2", command=dlg.destroy
                  ).pack(pady=(4, 20))

        dlg.wait_window()

    def _clear_password(self):
        if not self._check_password():
            return
        self.cfg.set_password("")
        session_code.clear_local_password()
        self._refresh_settings()
        self._log(tr("パスワードを削除しました。"))

    def _view_password(self):
        pw = session_code.load_local_password()
        if not pw:
            messagebox.showinfo(
                tr("パスワード確認"),
                tr("保存されたパスワードがありません。\n"
                "（古いパスワードや、他の端末で生成した場合は保存されていません）"),
                parent=self.root)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(tr("パスワード確認"))
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.transient(self.root)

        tk.Label(dlg, text=tr("🔍 保存されたパスワード"), font=(F_UI, 11, "bold"),
                 bg=BG, fg=PURPLE).pack(pady=(20, 4), padx=24)

        pw_box = tk.Frame(dlg, bg=BG2, pady=10)
        pw_box.pack(fill="x", padx=24, pady=(4, 8))
        tk.Label(pw_box, text=pw, font=(F_MONO, 22, "bold"),
                 bg=BG2, fg=GREEN).pack(side="left", padx=12)

        def _copy_pw():
            dlg.clipboard_clear()
            dlg.clipboard_append(pw)
            btn_copy.config(text="✓")
        btn_copy = tk.Button(pw_box, text=tr("📋 コピー"), font=(F_UI, 9),
                             bg=BG3, fg=FG, relief="flat", padx=8, pady=4,
                             cursor="hand2", command=_copy_pw)
        btn_copy.pack(side="right", padx=8)

        tk.Button(dlg, text=tr("閉じる"), font=(F_UI, 10, "bold"),
                  bg=BG3, fg=FG, relief="flat", padx=16, pady=8,
                  cursor="hand2", command=dlg.destroy
                  ).pack(pady=(4, 20))

    # Gmail settings

    def _save_gmail_settings(self):
        addr = self.gmail_addr_var.get().strip()
        app_pw = self.gmail_app_pw_var.get().strip()
        if not addr:
            messagebox.showerror(tr("エラー"), tr("Gmailアドレスを入力してください。"), parent=self.root)
            return
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", addr):
            messagebox.showerror(tr("エラー"), tr("Gmailアドレスの形式が正しくありません。"), parent=self.root)
            return
        # すでにGmailで保護中に送信先を変えるには、今の送信先に届くコードが必要。
        # （子どもが自分のアドレスに差し替えて保護を回避できないように）
        current = (self.cfg.get("gmail_address") or "").strip().lower()
        if self._gmail_mode() and addr.lower() != current:
            if not self._check_password("change_gmail"):
                return
        self.cfg.set("gmail_address", addr)
        problems = []
        if app_pw:
            if session_code.save_app_password(app_pw):
                self.gmail_app_pw_var.set("")
            else:
                problems.append(tr("アプリパスワードをWindows資格情報マネージャーに保存できませんでした。"))
        client_id = self.oauth_client_id_var.get().strip()
        client_secret = self.oauth_client_secret_var.get().strip()
        if client_id or client_secret:
            if not (client_id and client_secret):
                problems.append(tr("Client IDとClient Secretは両方入力してください。"))
            elif gmail_oauth.save_client(client_id, client_secret):
                self.oauth_client_id_var.set("")
                self.oauth_client_secret_var.set("")
            else:
                problems.append(tr("Client情報をWindows資格情報マネージャーに保存できませんでした。"))
        # 送信元が用意できていれば、Gmailコードによる保護をオンにする。
        ready = self.cfg.has_gmail_configured() is True
        if ready and not problems:
            self.cfg.set("gmail_protection_enabled", True)
        self._refresh_gmail_status()
        if problems:
            messagebox.showerror(tr("保存エラー"), "\n".join(problems), parent=self.root)
            self._log(tr("Gmail設定の保存に失敗: ") + " ".join(problems))
            return
        self._log(tr("Gmail設定を保存しました: {0}").format(addr))
        if ready:
            self._test_gmail_send()  # 保存直後に実際に届くか確認する

    def _show_sender_setup(self) -> bool:
        """Client ID/Secretの入力欄は開発者向け。製品に同梱済みなら出さない。
        同梱がなく未設定の間（開発中）と、developer_mode / EVOLOCK_DEV 指定時だけ表示する。"""
        if self.cfg.get("developer_mode") is True or os.environ.get("EVOLOCK_DEV") == "1":
            return True
        return not gmail_oauth.has_client()

    def _import_client_json(self):
        """Google CloudからダウンロードしたクライアントJSONを読み込んで保存する。"""
        path = filedialog.askopenfilename(
            parent=self.root, title=tr("クライアントのJSONファイルを選択"),
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        ok, message = gmail_oauth.load_client_file(path)
        if not ok:
            messagebox.showerror(tr("エラー"), message, parent=self.root)
            return
        self._refresh_gmail_status()
        self._log(tr("クライアント情報をJSONから読み込みました。"))
        messagebox.showinfo(
            tr("読み込み完了"),
            tr("クライアント情報を保存しました。\n"
               "このJSONにはシークレットが含まれます。読み込みが終わったら、ファイルを削除してください。\n"
               "次に「Googleでログイン」を押してください。"),
            parent=self.root)

    def _login_google(self):
        if not gmail_oauth.has_client():
            messagebox.showerror(tr("エラー"), tr("先にClient IDとClient Secretを入力して「保存」してください。"),
                                 parent=self.root)
            return
        self.oauth_login_btn.config(state="disabled", text=tr("ブラウザでログインしてください…"))
        self.gmail_status_var.set(tr("ブラウザでGoogleにログインし、「許可」を押してください（最大3分）。"))

        def _run():
            ok, err = gmail_oauth.authorize()
            self.root.after(0, lambda: self._on_google_login_done(ok, err))

        threading.Thread(target=_run, daemon=True).start()

    def _on_google_login_done(self, ok: bool, err: str):
        self.oauth_login_btn.config(state="normal", text=tr("🔐 Googleでログイン"))
        if ok and (self.cfg.get("gmail_address") or "").strip():
            self.cfg.set("gmail_protection_enabled", True)
        self._refresh_gmail_status()
        if ok:
            self._log(tr("Googleログイン成功 ✓ 「テスト送信」で送信を確認してください。"))
        else:
            self.gmail_status_var.set(tr("⚠ ログインできませんでした。{0}").format(err))
            self._log(tr("Googleログイン失敗: {0}").format(err[:80]))

    def _test_gmail_send(self):
        if not self.cfg.has_gmail_configured():
            messagebox.showerror(tr("エラー"), tr("先にGmailアドレスとアプリパスワードを保存してください。"),
                                 parent=self.root)
            return
        self.gmail_test_btn.config(state="disabled", text=tr("送信中..."))
        gmail = self.cfg.get("gmail_address")

        def _send():
            ok, err = session_code.send_code_email(gmail, "000000", 0)
            self.root.after(0, lambda: self._on_gmail_test_done(ok, err))

        threading.Thread(target=_send, daemon=True).start()

    def _on_gmail_test_done(self, ok: bool, err: str):
        self.gmail_test_btn.config(state="normal", text=tr("📧 テスト送信"))
        if ok:
            self.gmail_status_var.set(
                tr("✓ テスト送信に成功しました。{0} を確認してください。").format(self._mask_email(self.cfg.get('gmail_address') or '')))
            self._log(tr("Gmailテスト送信 成功 ✓"))
        else:
            self.gmail_status_var.set(tr("⚠ テスト送信に失敗しました。{0}").format(err[:160]))
            self._log(tr("Gmailテスト送信 失敗: {0}").format(err[:120]))

    def _clear_gmail_settings(self):
        if self.state == "studying":
            messagebox.showinfo(tr("学習中"), tr("保護の設定はセッション終了後に変更できます。"), parent=self.root)
            return
        # 保護を外すにもコードが必要（外すだけで回避できてしまうのを防ぐ）
        if self._gmail_mode() and not self._check_password("disable_gmail"):
            return
        self.cfg.set("gmail_protection_enabled", False)
        self.cfg.set("gmail_address", "")
        self.cfg.clear_session_code()
        self.gmail_addr_var.set("")
        self._refresh_gmail_status()
        self._log(tr("Gmailによる保護を解除しました。"))

    def _gmail_mode(self) -> bool:
        """Gmailコードによる保護が有効か（送信先と送信元の両方が設定済みの時だけ）。"""
        return (self.cfg.get("gmail_protection_enabled") is True
                and self.cfg.has_gmail_configured() is True)

    def _has_session_code(self) -> bool:
        code_hash = self.cfg.get("session_code_hash")
        return isinstance(code_hash, str) and bool(code_hash)

    @staticmethod
    def _mask_email(address: str) -> str:
        name, _, domain = (address or "").partition("@")
        return f"{name[:2]}{'*' * max(1, len(name) - 2)}@{domain}" if domain else address

    def _send_code_blocking(self, code: str, minutes: int = 0) -> tuple[bool, str]:
        """コードを送信し、完了まで待つ（待つ間も画面は固まらない）。"""
        dlg = self._show_sending_dialog()
        box: dict = {}

        def work():
            box["result"] = session_code.send_code_email(
                self.cfg.get("gmail_address"), code, minutes)

        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        while worker.is_alive():
            self.root.update()
            worker.join(0.05)
        dlg.destroy()
        return box.get("result", (False, tr("送信に失敗しました。")))

    def _verify_emailed_code(self, action: str) -> bool:
        """新しいコードをGmailに送り、入力されたコードと照合する。"""
        code = session_code.generate_code()
        ok, err = self._send_code_blocking(code, 0)
        if not ok:
            messagebox.showerror(tr("コードを送信できません"), err, parent=self.root)
            return False
        code_hash, salt = session_code.hash_code(code)
        address = self._mask_email(self.cfg.get("gmail_address") or "")
        for _ in range(3):
            entered = ask_password(
                self.root, tr("Gmailに届いたコードを入力"),
                hint=tr("{0} に6桁のコードを送りました。").format(address), masked=False)
            if entered is None:
                return False
            if session_code.verify_code(entered.strip(), code_hash, salt):
                return True
            messagebox.showerror(tr("コードエラー"), tr("コードが正しくありません。"), parent=self.root)
        return False

    def _refresh_gmail_status(self):
        if not hasattr(self, "gmail_status_var"):
            return
        address = self.cfg.get("gmail_address") or ""
        if self._gmail_mode():
            self.gmail_status_var.set(
                tr("✓ 保護はオンです。コードの送り先: {0}").format(self._mask_email(address)))
        elif address:
            if gmail_oauth.has_client():
                self.gmail_status_var.set(
                    tr("送信元がまだ設定されていません。「Googleでログイン」を1回だけ押してください。"))
            else:
                self.gmail_status_var.set(
                    tr("送信元がまだ設定されていません。下の「送信元の設定」を開いて、"
                    "Googleでログインしてください。"))
        else:
            self.gmail_status_var.set(tr("Gmailを入力して「保存」を押すと、保護がオンになります。"))
        # 「Googleでログイン」は、Clientがあってまだログインしていない時だけ出す
        if hasattr(self, "oauth_login_btn"):
            if gmail_oauth.has_client() and not gmail_oauth.is_connected():
                self.oauth_login_btn.pack(anchor="w", pady=(0, 6))
            else:
                self.oauth_login_btn.pack_forget()

    def _toggle_startup(self):
        if self.startup_var.get():
            ok = add_to_startup()
            self.startup_msg.config(
                text=tr("スタートアップに追加しました ✓") if ok else tr("スタートアップ追加エラー"),
                fg=GREEN if ok else RED)
        else:
            ok = remove_from_startup()
            self.startup_msg.config(
                text=tr("スタートアップから削除しました") if ok else tr("スタートアップ削除エラー"),
                fg=FG_DIM if ok else RED)

    def _save_ollama_model(self):
        model = self.ollama_model_var.get().strip()
        self.cfg.set("ollama_model", model)
        self.blocker.screen_ollama_model = model
        self._sync_screen_settings()
        self._log(tr("Ollamaモデル保存: {0} — スクリーンAI: {1}").format(
            model, tr("有効 ✓") if self.blocker.screen_enabled else tr("無効")))
        self._refresh_screen_ai_status()

    def _save_coach_ollama_model(self):
        model = self.coach_ollama_model_var.get().strip()
        self.cfg.set("coach_ollama_model", model)
        self._log(tr("AIコーチ用モデル保存: {0}").format(model or tr("（スクリーンAI用と共用）")))

    def _save_api_key(self):
        key = self.api_key_var.get().strip()
        self.cfg.set("anthropic_api_key", key)
        self.blocker.screen_api_key = key
        self._sync_screen_settings()
        status = tr("有効 ✓") if self.blocker.screen_enabled else tr("無効")
        self._log(tr("APIキー保存 — スクリーンAI: {0}").format(status))
        self._refresh_screen_ai_status()

    # ── State machine ──────────────────────────────────────────────

    def _on_main_btn(self):
        if self.state in ("idle", "locked"):
            self._enter_studying()
        elif self.state == "studying":
            if not self._check_override(action="stop_study"):
                return
            self._enter_idle()
        elif self.state == "unlocked":
            self._enter_studying()

    def _enter_studying(self):
        try:
            for variable in (self.study_min_var, self.unlock_min_var):
                minutes = int(variable.get())
                if not 1 <= minutes <= 1440:
                    raise ValueError
        except (ValueError, TypeError):
            self.settings_msg.config(text=tr("集中・休憩は1〜1440分の整数で入力してください。"), fg=RED)
            return
        self.settings_msg.config(text="", fg=FG_DIM)
        self.history.settle_rewards(self.game)
        study_secs = self._get_study_seconds()
        if self._gmail_mode():
            # 学習を始めるたびに、新しいコードを登録のGmailへ送る。
            self._send_session_code_then_start(study_secs)
            return
        if self.cfg.get("protection_enabled") and not self.cfg.has_password():
            if not self._setup_protection_code():
                return
        self._begin_studying_state(study_secs)

    def _begin_studying_state(self, study_secs: int):
        self._session_protected = (bool(self.cfg.get("protection_enabled"))
                                   or (self._gmail_mode() and self._has_session_code()))
        self._record_play_session()
        self._reset_timers()
        self.state = "studying"
        self._study_started_at = datetime.now()
        self.blocker.start()
        self.study_timer.start()
        self.status_var.set(tr("学習中 📚 — アプリをブロック中"))
        self.status_label.config(fg=YELLOW)
        self.timer_var.set(fmt_time(study_secs))
        self._reset_session_bar()
        self.timer_label.config(text=tr("残り学習時間"))
        self.btn_main.config(text=tr("学習を止める"), bg=RED)
        self.settings_msg.config(
            text=tr("学習 {0}分 → プレイ {1}分").format(study_secs // 60, self._get_unlock_seconds() // 60))
        self._log(tr("学習開始 {0}分 — ブロッカーON").format(study_secs // 60))
        if TRAY_AVAILABLE and self._tray_icon:
            self._tray_icon.icon = _make_tray_image(True)

    def _send_session_code_then_start(self, study_secs: int):
        code  = session_code.generate_code()
        gmail = self.cfg.get("gmail_address")
        minutes = study_secs // 60

        dlg = self._show_sending_dialog()

        def _send():
            ok, err = session_code.send_code_email(gmail, code, minutes)
            self.root.after(0, lambda: self._on_session_code_sent(ok, err, code, study_secs, dlg))

        threading.Thread(target=_send, daemon=True).start()

    def _on_session_code_sent(self, ok: bool, err: str, code: str, study_secs: int, dlg: tk.Toplevel):
        dlg.destroy()
        if ok:
            self.cfg.set_session_code(code)
            self._log(tr("📧 解除コードをGmailに送信しました"))
            self._begin_studying_state(study_secs)
            return

        choice = self._ask_send_failed(err)
        if choice == "retry":
            self._send_session_code_then_start(study_secs)
        elif choice == "unprotected":
            self.cfg.clear_session_code()  # 前回のコードを引き継がない
            self._log(tr("⚠️ コードを送れなかったため、保護なしで学習を開始しました。"))
            self._begin_studying_state(study_secs)
        # choice == "cancel" → 何もしない、学習は開始しない

    def _show_sending_dialog(self) -> tk.Toplevel:
        dlg = tk.Toplevel(self.root)
        dlg.title(tr("送信中"))
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.transient(self.root)
        tk.Label(dlg, text=tr("📧 解除コードをGmailに送信中..."), font=(F_UI, 11, "bold"),
                 bg=BG, fg=PURPLE).pack(padx=32, pady=28)
        dlg.update()
        return dlg

    def _ask_send_failed(self, err: str) -> str:
        dlg = tk.Toplevel(self.root)
        dlg.title(tr("送信エラー"))
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.transient(self.root)

        tk.Label(dlg, text=tr("⚠️ コードを送信できませんでした"),
                 font=(F_UI, 11, "bold"), bg=BG, fg=RED).pack(padx=28, pady=(20, 4))
        tk.Label(dlg, text=err[:200], font=(F_UI, 9), bg=BG, fg=FG_DIM,
                 wraplength=320, justify="left").pack(padx=28, pady=(0, 12))

        result = ["cancel"]

        def _choose(v):
            result[0] = v
            dlg.destroy()

        btn_frame = tk.Frame(dlg, bg=BG)
        btn_frame.pack(pady=(0, 18))
        tk.Button(btn_frame, text=tr("🔁 再試行"), font=(F_UI, 9, "bold"),
                  bg=PURPLE, fg=BG, relief="flat", padx=10, pady=6, cursor="hand2",
                  command=lambda: _choose("retry")).pack(side="left", padx=4)
        tk.Button(btn_frame, text=tr("保護なしで開始"), font=(F_UI, 9),
                  bg=BG3, fg=FG, relief="flat", padx=10, pady=6, cursor="hand2",
                  command=lambda: _choose("unprotected")).pack(side="left", padx=4)
        tk.Button(btn_frame, text=tr("中止"), font=(F_UI, 9),
                  bg=BG3, fg=RED, relief="flat", padx=10, pady=6, cursor="hand2",
                  command=lambda: _choose("cancel")).pack(side="left", padx=4)

        dlg.wait_window()
        return result[0]

    def _enter_idle(self):
        self._record_study_session()
        self._record_play_session()
        self.cfg.clear_session_code()  # 終わったセッションのコードは残さない
        self.state = "idle"
        self.blocker.stop()
        self.study_timer.stop()
        self.unlock_timer.stop()
        self.status_var.set(tr("開始待ち"))
        self.status_label.config(fg=FG_DIM)
        self.timer_var.set(fmt_time(self._get_study_seconds()))
        self._reset_session_bar()
        self.timer_label.config(text=tr("学習時間"))
        self.btn_main.config(text=tr("学習開始"), bg=GREEN, state="normal")
        self.settings_msg.config(text="")
        self._log(tr("停止しました。"))
        if TRAY_AVAILABLE and self._tray_icon:
            self._tray_icon.icon = _make_tray_image(False)

    def _enter_unlocked(self):
        self._record_play_session()
        self._record_study_session()
        # フェーズ正常終了 — セッションコードはもう不要。残しておくと、
        # プレイ中/待機中にアプリを終了する時、期限切れのコードを要求してしまう。
        self.cfg.clear_session_code()
        self._unlock_started_at = datetime.now()
        self.state = "unlocked"
        self.blocker.stop()
        self.unlock_timer.start()
        self._reset_session_bar()  # 休憩（プレイ）の進み具合は0から数える
        self.status_var.set(tr("ロック解除 🎮 — プレイ時間"))
        self.status_label.config(fg=GREEN)
        self.timer_label.config(text=tr("残りプレイ時間"))
        self.btn_main.config(text=tr("学習を続ける"), bg=BLUE, state="normal")
        self.settings_msg.config(text="")
        self._log(tr("ロック解除 {0}分").format(self._get_unlock_seconds() // 60))
        if TRAY_AVAILABLE and self._tray_icon:
            self._tray_icon.icon = _make_tray_image(False)
        # 学習セッション終了直後 — 自分から分析結果を見せに行く（受動的に待たせない）
        self._run_analysis(auto=True)

    def _enter_locked(self):
        self._record_play_session()
        self.state = "locked"
        self.blocker.start()
        self.status_var.set(tr("プレイ終了 🔒 — 学習を再開しよう"))
        self.status_label.config(fg=RED)
        self.timer_var.set("00:00")
        self._reset_session_bar()
        self.timer_label.config(text=tr("プレイ時間終了"))
        self.btn_main.config(text=tr("学習開始"), bg=GREEN, state="normal")
        self._log(tr("プレイ終了 — ブロッカーON"))
        if TRAY_AVAILABLE and self._tray_icon:
            self._tray_icon.icon = _make_tray_image(True)

    # ── History helpers ────────────────────────────────────────────

    def _record_study_session(self):
        if self._study_started_at:
            s = self.history.log("study", self._study_started_at, datetime.now())
            self._study_started_at = None
            for result in self.history.settle_rewards(self.game):
                self._award_and_notify(result)
            self._refresh_history_display()

    def _record_play_session(self):
        if self._unlock_started_at:
            self.history.log("play", self._unlock_started_at, datetime.now())
            self._unlock_started_at = None
            self._refresh_history_display()

    # ── Timer ──────────────────────────────────────────────────────

    def _get_study_seconds(self) -> int:
        try:
            return max(1, int(self.study_min_var.get())) * 60
        except ValueError:
            return DEFAULT_STUDY_MIN * 60

    def _get_unlock_seconds(self) -> int:
        try:
            return max(1, int(self.unlock_min_var.get())) * 60
        except ValueError:
            return DEFAULT_UNLOCK_MIN * 60

    def _dispatch_to_ui(self, callback):
        """Đồng hồ chạy ở luồng nền; đưa callback về luồng Tk. Nếu cửa sổ vừa đóng thì
        bỏ qua (tránh in lỗi từ luồng nền lúc tắt app)."""
        try:
            self.root.after(0, callback)
        except (RuntimeError, tk.TclError):
            pass

    def _reset_timers(self):
        if self.study_timer:
            self.study_timer.stop()
        if self.unlock_timer:
            self.unlock_timer.stop()
        study_total, unlock_total = self._get_study_seconds(), self._get_unlock_seconds()
        self.study_timer = CountdownTimer(
            study_total,
            on_tick=lambda r: self._show_countdown(r, study_total),
            on_done=self._enter_unlocked,
            dispatch=self._dispatch_to_ui,
        )
        self.unlock_timer = CountdownTimer(
            unlock_total,
            on_tick=lambda r: self._show_countdown(r, unlock_total),
            on_done=self._enter_locked,
            dispatch=self._dispatch_to_ui,
        )

    # ── System tray ────────────────────────────────────────────────

    def _start_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem(tr("EvoLockを開く"), self._show_window, default=True),
            pystray.MenuItem(tr("終了"), self._quit_from_tray),
        )
        self._tray_icon = pystray.Icon(
            "EvoLock", _make_tray_image(False), "EvoLock", menu)
        threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def _show_window(self, icon=None, item=None):
        self.root.after(0, lambda: (self.root.deiconify(), self.root.lift()))

    def _on_close(self):
        # Đang học + có mật khẩu hoặc mã phiên Gmail → chặn hoàn toàn, chỉ minimize
        if self.state == "studying" and getattr(self, "_session_protected", False):
            self.root.iconify()
            self._log(tr("保護中です。先に「学習を止める」からコードを入力してください。"))
            return

        if TRAY_AVAILABLE and self._tray_icon:
            self.root.withdraw()
        else:
            if messagebox.askyesno(tr("終了確認"), tr("EvoLockを終了しますか？"), parent=self.root):
                self._quit_app()

    def _quit_from_tray(self, icon=None, item=None):
        self.root.after(0, self._quit_app)

    def _quit_app(self):
        if not self._check_override(action="quit_app"):
            return
        self._record_study_session()
        self._record_play_session()
        self.blocker.stop()
        if self.study_timer:
            self.study_timer.stop()
        if self.unlock_timer:
            self.unlock_timer.stop()
        self._stop_mascot()
        if getattr(self, "_day_after_id", None) is not None:
            self.root.after_cancel(self._day_after_id)
            self._day_after_id = None
        if TRAY_AVAILABLE and self._tray_icon:
            self._tray_icon.stop()
        self.root.destroy()

    # ── Password / Override ───────────────────────────────────────────

    def _check_override(self, action: str = "stop_study") -> bool:
        """Cổng dừng học sớm / thoát app khi đang học. Ưu tiên cơ chế Gmail
        (mã phiên + lý do + ghi chú); nếu Gmail chưa cấu hình thì dùng lại
        mật khẩu cũ (fail-safe — không khóa cứng người dùng nếu chưa setup)."""
        if action in ("stop_study", "quit_app"):
            if self.state != "studying":
                return True
            if not getattr(self, "_session_protected", bool(self.cfg.get("protection_enabled"))):
                return self._confirm_early_stop()
            if not (self._gmail_mode() and self._has_session_code()):
                return self._check_password(action)
            # この学習のコードをGmailに送信済み → 下の「コード＋理由」の確認へ進む

        # Không có mã phiên đang hoạt động (chưa cấu hình Gmail, hoặc không
        # đang trong phiên học nào cả) → dùng lại cơ chế mật khẩu cũ.
        if not self.cfg.get("session_code_hash"):
            return self._check_password(action)

        result = ask_override(self.root)
        if result is None:
            return False

        if not self.cfg.verify_session_code(result["code"]):
            messagebox.showerror(tr("コードエラー"), tr("コードが正しくありません！"), parent=self.root)
            return False

        # Management authorization must not consume the active study code.
        if action not in ("stop_study", "quit_app"):
            return True

        planned = self._get_study_seconds() // 60
        actual = planned
        if self._study_started_at and self.state == "studying":
            actual = max(0, int((datetime.now() - self._study_started_at).total_seconds() // 60))
        self.override_log.log(result["reason"], result["note"], planned, actual)
        self.cfg.clear_session_code()
        self._log(tr("⏸ セッション終了（理由: {0}） — {1}/{2}分").format(result['reason'], actual, planned))
        return True

    def _check_password(self, action: str = "manage") -> bool:
        if self._gmail_mode():
            return self._verify_emailed_code(action)
        if not self.cfg.has_password():
            return True
        pw = ask_password(self.root, tr("EvoLockの保護コードを入力してください"))
        if pw is None:
            return False

        # メインパスワード確認
        if self.cfg.verify_password(pw):
            if action in ("stop_study", "quit_app"):
                self.pw_logger.log("password", action)
            return True

        # 緊急コード入力フロー
        if pw == "__EMERGENCY__":
            return self._handle_emergency(action)

        messagebox.showerror(tr("パスワードエラー"), tr("パスワードが正しくありません！"), parent=self.root)
        return False

    def _handle_emergency(self, action: str = "stop_study") -> bool:
        code = ask_password(self.root, tr("🆘 緊急コードを入力してください"))
        if code is None:
            return False
        if self.cfg.verify_emergency(code):
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Log emergency usage
            self.pw_logger.log("emergency", action)

            # Trừ EXP
            result = self.game.on_emergency_used()
            self._refresh_stats()

            penalty_msg = f"-{result['penalty']} EXP"
            if result["leveled_down"]:
                penalty_msg += tr("  レベルダウン！→ Level {0}").format(self.game.stats.level)

            self._log(tr("⚠️ 緊急コード使用 — {0}  {1}").format(now, penalty_msg))
            messagebox.showwarning(
                tr("緊急コード使用"),
                tr("緊急コードでロックを解除しました。\nペナルティ: {0}\n\n本当に必要な時だけ使用してください。\n({1})").format(penalty_msg, now),
                parent=self.root
            )
            return True
        messagebox.showerror(tr("エラー"), tr("緊急コードが正しくありません！"), parent=self.root)
        return False

    # ── Misc ───────────────────────────────────────────────────────

    def _refresh_blocked_list(self):
        if not hasattr(self, "list_frame"):
            return
        for w in self.list_frame.winfo_children():
            w.destroy()
        try:
            apps = load_blocked_apps()
        except Exception:
            apps = []
        if not apps:
            tk.Label(self.list_frame, text=tr("  アプリがありません。"),
                     font=(F_UI, 8), bg=BG2, fg=FG_DIM
                     ).pack(anchor="w", padx=6, pady=8)
            return

        grid = tk.Frame(self.list_frame, bg=BG2)
        grid.pack(fill="x", padx=6, pady=6)
        cols = 2
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)
        for i, app in enumerate(apps):
            chip = tk.Frame(grid, bg=BG3)
            chip.grid(row=i // cols, column=i % cols, sticky="ew", padx=3, pady=2)
            tk.Label(chip, text="🔒", font=(F_UI, 8), bg=BG3, fg=RED
                     ).pack(side="left", padx=(6, 4), pady=4)
            tk.Label(chip, text=app, font=(F_MONO, 8), bg=BG3, fg=FG, anchor="w"
                     ).pack(side="left", fill="x", expand=True, pady=4)
            app_name = app
            tk.Button(chip, text="✕", font=(F_UI, 7),
                      bg=BG3, fg=FG_DIM, activebackground=BG3, activeforeground=RED,
                      relief="flat", bd=0, padx=5, cursor="hand2",
                      command=lambda a=app_name: self._remove_blocked_app(a)
                      ).pack(side="right", padx=(0, 4))

    def _toggle_blocked_list(self):
        self._blocked_list_visible = not getattr(self, "_blocked_list_visible", True)
        if self._blocked_list_visible:
            self.list_frame.pack(fill="x", padx=12, pady=(4, 6))
            self.blocked_toggle_btn.config(text=tr("▲ 隠す"))
        else:
            self.list_frame.pack_forget()
            self.blocked_toggle_btn.config(text=tr("▼ 表示"))

    def _remove_blocked_app(self, app: str):
        if self.state in ("studying", "locked"):
            if not self._check_override(action="manage_blocklist"):
                return
        apps = [a for a in load_blocked_apps() if a.lower() != app.lower()]
        save_blocked_apps(apps)
        self.blocker.reload_blocked_apps()
        self._refresh_blocked_list()
        self._log(tr("ブロックリストから削除: {0}").format(app))

    def _add_blocked_app(self, app: str):
        app = app.strip()
        if not app:
            return
        apps = load_blocked_apps()
        if app.lower() in (a.lower() for a in apps):
            return
        apps.append(app)
        save_blocked_apps(apps)
        self.blocker.reload_blocked_apps()
        self._refresh_blocked_list()
        self._log(tr("ブロックリストに追加: {0}").format(app))

    def _open_app_picker(self):
        dlg = tk.Toplevel(self.root)
        dlg.title(tr("アプリを選択してブロック"))
        dlg.geometry("380x480")
        dlg.configure(bg=BG)
        dlg.grab_set()
        dlg.transient(self.root)

        tk.Label(dlg, text=tr("実行中のアプリから選ぶ"), font=(F_UI, 11, "bold"),
                 bg=BG, fg=PURPLE).pack(pady=(16, 4), padx=16, anchor="w")
        tk.Label(dlg, text=tr("今このパソコンで動いているアプリの一覧。複数選択可。"),
                 font=(F_UI, 8), bg=BG, fg=FG_DIM
                 ).pack(padx=16, anchor="w", pady=(0, 8))

        filter_var = tk.StringVar()
        filter_entry = tk.Entry(dlg, textvariable=filter_var, font=(F_UI, 9),
                                bg=BG3, fg=FG, insertbackground=FG, relief="flat")
        filter_entry.pack(fill="x", padx=16, pady=(0, 6))
        filter_entry.focus_set()

        list_frame = tk.Frame(dlg, bg=BG)
        list_frame.pack(fill="both", expand=True, padx=16)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical")
        listbox = tk.Listbox(list_frame, selectmode="extended", font=(F_MONO, 9),
                             bg=BG3, fg=FG, relief="flat", activestyle="none",
                             yscrollcommand=scrollbar.set, exportselection=False)
        scrollbar.config(command=listbox.yview)
        scrollbar.pack(side="right", fill="y")
        listbox.pack(side="left", fill="both", expand=True)

        try:
            all_apps = list_running_apps()
        except Exception:
            all_apps = []
        already_blocked = {a.lower() for a in load_blocked_apps()}
        added_mark = tr(" (追加済み)")  # 表示と取り除き処理で同じ文字列を使う

        def _populate(filter_text: str = ""):
            listbox.delete(0, "end")
            ft = filter_text.lower()
            for name in all_apps:
                if ft and ft not in name.lower():
                    continue
                marker = added_mark if name.lower() in already_blocked else ""
                listbox.insert("end", f"{name}{marker}")

        _populate()
        filter_var.trace_add("write", lambda *_: _populate(filter_var.get()))

        tk.Label(dlg, text=tr("または名前を直接入力（例: game.exe）:"),
                 font=(F_UI, 8), bg=BG, fg=FG_DIM
                 ).pack(anchor="w", padx=16, pady=(10, 2))
        manual_var = tk.StringVar()
        manual_row = tk.Frame(dlg, bg=BG)
        manual_row.pack(fill="x", padx=16, pady=(0, 10))
        tk.Entry(manual_row, textvariable=manual_var, font=(F_UI, 9),
                 bg=BG3, fg=FG, insertbackground=FG, relief="flat"
                 ).pack(side="left", fill="x", expand=True, padx=(0, 6))

        def _add_manual():
            self._add_blocked_app(manual_var.get())
            manual_var.set("")
            nonlocal already_blocked
            already_blocked = {a.lower() for a in load_blocked_apps()}
            _populate(filter_var.get())

        tk.Button(manual_row, text="＋", font=(F_UI, 9, "bold"),
                  bg=BLUE, fg=BG, relief="flat", padx=10, cursor="hand2",
                  command=_add_manual).pack(side="left")

        def _add_selected():
            for i in listbox.curselection():
                text = listbox.get(i)
                name = text.replace(added_mark, "")
                self._add_blocked_app(name)
            dlg.destroy()

        btn_row = tk.Frame(dlg, bg=BG)
        btn_row.pack(pady=(0, 16))
        tk.Button(btn_row, text=tr("選択したアプリを追加"), font=(F_UI, 10, "bold"),
                  bg=GREEN, fg=BG, relief="flat", padx=14, pady=6, cursor="hand2",
                  command=_add_selected).pack(side="left", padx=4)
        tk.Button(btn_row, text=tr("閉じる"), font=(F_UI, 9),
                  bg=BG3, fg=FG, relief="flat", padx=12, pady=6, cursor="hand2",
                  command=dlg.destroy).pack(side="left", padx=4)

    def _on_model_ready(self, success: bool, error: str):
        def _update():
            if success:
                self.ai_status_var.set(tr("🤖 スマートブロック: 準備完了 ✓"))
            else:
                self.ai_status_var.set(tr("🤖 スマートブロック: エラー ({0})").format(error[:40]))
        self.root.after(0, _update)

    def _refresh_site_labels(self):
        """AIコーチタブの「AIが判断できなかったサイト」を作り直す。"""
        frame = getattr(self, "site_review_frame", None)
        labels = getattr(self.blocker, "labels", None)
        if frame is None or labels is None:
            return
        for widget in frame.winfo_children():
            widget.destroy()
        pending, labelled = labels.pending_items(), labels.labelled_items()
        if not pending and not labelled:
            tk.Label(frame, text=tr("判断できなかったサイトはありません。"), font=(F_UI, 9),
                     bg=BG2, fg=FG_DIM, anchor="w").pack(fill="x")
            return
        for key, title, count in pending:
            row = tk.Frame(frame, bg=BG3)
            row.pack(fill="x", pady=2)
            seen = f"  ×{count}" if count > 1 else ""
            # nút を先に右へ詰め、タイトルは残りの幅に収める（長いタイトルでも nút が切れない）
            tk.Button(row, text="✕", font=(F_UI, 9), bg=BG2, fg=FG_DIM, relief="flat", padx=6,
                      pady=2, cursor="hand2", command=lambda k=key: self._dismiss_site(k)
                      ).pack(side="right", padx=(2, 6))
            for text, label, colour in ((tr("娯楽"), "block", RED), (tr("学習"), "study", GREEN)):
                tk.Button(row, text=text, font=(F_UI, 9, "bold"), bg=BG2, fg=colour, relief="flat",
                          padx=8, pady=2, cursor="hand2",
                          command=lambda k=key, l=label: self._label_site(k, l)
                          ).pack(side="right", padx=2)
            tk.Label(row, text="🤔 " + title[:28] + ("…" if len(title) > 28 else "") + seen,
                     font=(F_UI, 9), bg=BG3, fg=FG, anchor="w"
                     ).pack(side="left", fill="x", expand=True, padx=(8, 4), pady=5)
        if labelled:
            tk.Label(frame, text=tr("保存した判断"), font=(F_UI, 9, "bold"), bg=BG2, fg=FG,
                     anchor="w").pack(fill="x", pady=(8, 2))
            for key, label in labelled:
                row = tk.Frame(frame, bg=BG2)
                row.pack(fill="x")
                mark = tr("学習") if label == "study" else tr("娯楽")
                tk.Label(row, text=f"{mark}  {key[:44]}", font=(F_UI, 9), bg=BG2,
                         fg=GREEN if label == "study" else RED, anchor="w"
                         ).pack(side="left", fill="x", expand=True)
                tk.Button(row, text="✕", font=(F_UI, 9), bg=BG3, fg=FG_DIM, relief="flat", padx=6,
                          cursor="hand2", command=lambda k=key: self._remove_site_label(k)
                          ).pack(side="left")

    def _label_site(self, key: str, label: str):
        # 子どもが自分で「学習」にできないよう、Gmailのコード（保護中）を確認する。
        if not self._check_password("label_site"):
            return
        self.blocker.labels.set_label(key, label)
        self._log(tr("サイトの判断を保存: {0} → {1}").format(
            key, tr("学習") if label == "study" else tr("娯楽")))
        self._refresh_site_labels()

    def _dismiss_site(self, key: str):
        self.blocker.labels.dismiss(key)
        self._refresh_site_labels()

    def _remove_site_label(self, key: str):
        if not self._check_password("label_site"):
            return
        self.blocker.labels.remove_label(key)
        self._refresh_site_labels()

    def _on_smart_allow(self, allowed: list):
        for name, title, layer, detail in allowed:
            if layer == "unsure":
                self._log(tr("🤔 判断できないため許可しました: {0}").format(title))
                self._refresh_site_labels()
            elif layer == "label":
                self._log(tr("✓ 保護者の判断で許可: {0}").format(detail))
            elif layer == "whitelist":
                self._log(tr("✓ ホワイトリスト [{0}] {1}").format(detail, title))
            elif layer == "reference":
                self._log(tr("🔎 検索/参照ツール許可: {0}").format(title))
            elif layer == "warn":
                self._log(f"⚠️ {detail}  {title}")
                self.activity_log.log("warn", name, f"{detail} - {title}")
                self.ai_status_var.set(tr("⚠️ 集中力低下の兆候: {0}").format(title[:30]))
            else:
                self._log(tr("✓ AI許可 {0}  ({1})").format(title, detail))

    def _add_whitelist_channel(self):
        name = self.wl_input_var.get().strip()
        if not name:
            return
        self.blocker.whitelist.add(name)
        self.wl_input_var.set("")
        self._refresh_whitelist()
        self._log(tr("ホワイトリスト追加: {0}").format(name))

    def _remove_whitelist_channel(self, name: str):
        self.blocker.whitelist.remove(name)
        self._refresh_whitelist()

    def _refresh_whitelist(self):
        for w in self.wl_list_frame.winfo_children():
            w.destroy()
        channels = self.blocker.whitelist.channels
        if not channels:
            tk.Label(self.wl_list_frame, text=tr("  チャンネルがありません。"),
                     font=(F_UI, 8), bg=BG2, fg=FG_DIM
                     ).pack(anchor="w", padx=6, pady=4)
            return
        for ch in channels:
            row = tk.Frame(self.wl_list_frame, bg=BG2)
            row.pack(fill="x", padx=2, pady=1)
            tk.Label(row, text=f"  ✓ {ch}", font=(F_UI, 9),
                     bg=BG2, fg=GREEN, anchor="w"
                     ).pack(side="left", fill="x", expand=True)
            ch_name = ch
            tk.Button(row, text="✕", font=(F_UI, 8),
                      bg=BG2, fg=RED, activebackground=BG2,
                      relief="flat", padx=4, pady=1, cursor="hand2",
                      command=lambda c=ch_name: self._remove_whitelist_channel(c)
                      ).pack(side="right", padx=(0, 4))

    def _toggle_smart(self):
        enabled = self.smart_var.get()
        self.cfg.set("smart_enabled", bool(enabled))
        self.blocker.smart_enabled = enabled
        status = tr("準備完了 ✓") if self.blocker.smart.ready else tr("読み込み中...")
        self.ai_status_var.set(tr("🤖 スマートブロック: {0}").format(
            (tr("有効 — ") + status) if enabled else tr("無効")))

    def _toggle_screen_ai(self):
        enabled = self.screen_ai_var.get()
        has_backend = bool(self.blocker.screen_ollama_model or self.blocker.screen_api_key)
        if enabled and not has_backend:
            self.screen_ai_var.set(False)
            self.screen_ai_status_var.set(tr("画面の確認はまだ利用できません。設定が必要です。"))
            return
        if enabled and not messagebox.askyesno(
                tr("画面の読み取り"), tr("画面全体を読み取ります。") +
                (tr("画像はこのPCのAIへ送られます。") if self.blocker.screen_ollama_model else
                 tr("画像は外部サービス（Anthropic）へ送信されます。")) +
                tr("\n画面の読み取りを有効にしますか？"), parent=self.root):
            self.screen_ai_var.set(False)
            return
        destination = "local" if self.blocker.screen_ollama_model else "anthropic"
        self.cfg.set_many({"screen_enabled": bool(enabled),
                           "screen_consent_destination": destination if enabled else ""})
        self._sync_screen_settings()
        self._refresh_screen_ai_status()
        self._log(tr("📸 スクリーンAI: {0}").format(tr("有効") if enabled else tr("無効")))

    def _sync_screen_settings(self):
        backend = bool(self.blocker.screen_ollama_model or self.blocker.screen_api_key)
        destination = "local" if self.blocker.screen_ollama_model else "anthropic"
        self.blocker.screen_enabled = (bool(self.cfg.get("screen_enabled")) and backend
                                       and self.cfg.get("screen_consent_destination") == destination)
        if hasattr(self, "screen_ai_var"):
            self.screen_ai_var.set(self.blocker.screen_enabled)

    def _refresh_screen_ai_status(self):
        if not hasattr(self, "screen_ai_status_var"):
            return
        # 技術的な状態表示は通常は不要。画面が「外部サービス」へ送られる時だけ、
        # プライバシー上重要なので警告として残す（このPC内のAIなら何も出さない）。
        ollama = self.blocker.screen_ollama_model
        has_api = bool(self.blocker.screen_api_key)
        if self.blocker.screen_enabled and has_api and not ollama:
            self.screen_ai_status_var.set(tr("⚠ 画面の画像は外部サービス（Anthropic）に送信されます。"))
        else:
            self.screen_ai_status_var.set("")

    def _on_screen_classify(self, is_study: bool, reason: str):
        icon = "✅" if is_study else "🚫"
        label = tr("学習中") if is_study else tr("娯楽検出")
        self.root.after(0, lambda: (
            self._log(tr("📸 スクリーンAI → {0} {1}: {2}").format(icon, label, reason)),
            self.ai_status_var.set(
                tr("📸 スクリーンAI: {0} {1} — {2}").format(icon, label, reason[:35])
            )
        ))

    def _on_kill(self, killed):
        for name, reason in killed:
            self._log(tr("終了: {0} — {1}").format(name, reason))
            self.activity_log.log("kill", name, reason)

    def _log(self, msg: str):
        now = datetime.now().strftime("%H:%M:%S")
        self.log.config(state="normal")
        self.log.insert("end", f"[{now}] {msg}\n")
        self.log.see("end")
        self.log.config(state="disabled")


def main():
    instance = InstanceLock()
    if not instance.acquire():
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showinfo("EvoLock", tr("EvoLockは既に起動しています。タスクバーまたはトレイを確認してください。"), parent=root)
        finally:
            root.destroy()
        return
    try:
        root = tk.Tk()
        default_exception_handler = root.report_callback_exception
        def report_callback_error(exc_type, exc, traceback):
            if isinstance(exc, DataFileError):
                messagebox.showerror("EvoLock — Data error", str(exc), parent=root)
            else:
                default_exception_handler(exc_type, exc, traceback)
        root.report_callback_exception = report_callback_error
        try:
            EvoLockApp(root)
        except DataFileError as exc:
            messagebox.showerror("EvoLock — Data error", str(exc), parent=root)
            root.destroy()
            return
        root.mainloop()
    finally:
        instance.release()


if __name__ == "__main__":
    main()
