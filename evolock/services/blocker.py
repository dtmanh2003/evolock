from evolock.storage.state import committed_state
import ctypes
import ctypes.wintypes
import json
import re
import threading
import time
from evolock.paths import DATA_DIR
from evolock.storage.json_file import read_json, atomic_write_text, DataFileError
from evolock.storage.site_labels import SiteLabels

import psutil

BLOCKED_FILE   = DATA_DIR / "blocked.json"
WHITELIST_FILE = DATA_DIR / "whitelist.json"
SCAN_INTERVAL  = 3
# Khi điểm "học" và "giải trí" chênh nhau ít hơn ngưỡng này, AI coi là KHÔNG CHẮC:
# không chặn, ghi vào danh sách chờ để phụ huynh quyết định.
UNSURE_MARGIN  = 0.05
# Mô hình nhúng câu dùng phân loại tiêu đề. Bản đa ngôn ngữ (~470MB, tải lần đầu từ Hugging Face)
# vì tiêu đề thực tế có tiếng Việt/Nhật; bản cũ all-MiniLM-L6-v2 chỉ giỏi tiếng Anh.
SMART_MODEL    = "paraphrase-multilingual-MiniLM-L12-v2"

BROWSER_PROCESSES = {
    "chrome.exe", "firefox.exe", "msedge.exe",
    "opera.exe", "brave.exe", "vivaldi.exe",
}

STUDY_PHRASES = [
    "studying tutorial online course lecture",
    "reading documentation research paper article",
    "programming coding software development",
    "learning educational university textbook",
    "working productivity professional task",
    "music for studying concentration lofi focus",
    "language learning vocabulary grammar",
    "mathematics science formula physics chemistry",
    "writing essay report assignment project",
    "how to guide explanation step by step",
    "Stack Overflow GitHub documentation",
    "Khan Academy Coursera edX MIT lecture",
]

ENTERTAINMENT_PHRASES = [
    "gaming gameplay walkthrough let's play streamer",
    "funny video meme viral entertainment clips",
    "social media feed scrolling reels shorts",
    "watching movie series drama episode season",
    "sports highlights match result score",
    "music video pop artist singer official MV",
    "celebrity gossip news drama reaction",
    "anime cartoon episode stream",
    "TikTok Instagram Twitter trending",
    "funny compilation fails moments",
]

DEFAULT_CHANNELS = [
    "Lofi Girl", "ChilledCow", "Khan Academy", "freeCodeCamp.org",
    "MIT OpenCourseWare", "Coursera", "TED", "3Blue1Brown",
    "Crash Course", "Kurzgesagt – In a Nutshell",
]

# Trang tra cứu/công cụ — luôn cho phép, không tính là giải trí dù đang giờ học.
# Tra Google, xem Wikipedia, đọc docs... là hành vi học tập bình thường.
REFERENCE_KEYWORDS = [
    "google search", "- bing", "duckduckgo", "wikipedia", "dictionary",
    "merriam-webster", "stack overflow", "stackoverflow", "- github",
    "wolfram alpha", "wolframalpha", "google scholar", "google translate",
    "google docs", "google drive", "google maps",
]


def is_reference_tool(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in REFERENCE_KEYWORDS)


_BROWSER_SUFFIX = re.compile(
    r"\s*[-—–]\s*(?:Google Chrome|Microsoft\s*.?\s*Edge|Mozilla Firefox|Brave|Opera|Vivaldi)\s*$",
    re.IGNORECASE)


def site_key(title: str) -> str:
    """Khóa nhận diện "trang" từ tiêu đề cửa sổ để gán nhãn: kênh YouTube, hoặc phần tên trang
    ở cuối tiêu đề ("... - Stack Overflow" -> "stack overflow"). Không có dấu phân cách thì
    dùng cả tiêu đề."""
    text = _BROWSER_SUFFIX.sub("", (title or "").strip())
    channel = parse_youtube_channel(text)
    if channel:
        return ("youtube:" + channel.lower())[:60]
    parts = [p for p in re.split(r"\s+[-—–|]\s+", text) if p.strip()]
    key = parts[-1] if len(parts) > 1 else text
    if key.strip().lower() == "youtube":  # video không rõ kênh: dùng cả tiêu đề, không gộp cả YouTube
        key = text
    return key.strip().lower()[:60]


def load_blocked_apps() -> list[str]:
    if not BLOCKED_FILE.exists():
        return []
    try:
        names = read_json(BLOCKED_FILE)["apps"]
        if not isinstance(names, list) or any(type(name) is not str for name in names):
            raise ValueError("Invalid blocked apps")
        return [name.lower() for name in names]
    except Exception as exc:
        raise DataFileError(BLOCKED_FILE) from exc


def save_blocked_apps(apps: list[str]):
    seen = set()
    unique = []
    for a in apps:
        a = a.strip()
        if a and a.lower() not in seen:
            seen.add(a.lower())
            unique.append(a)
    atomic_write_text(BLOCKED_FILE, json.dumps({"apps": unique}, ensure_ascii=False, indent=2))


def list_running_apps() -> list[str]:
    """Tên process đang chạy thật trên máy — để người dùng chọn thay vì đoán tên,
    vì mỗi máy cài game/app khác nhau (tên process không đoán trước được)."""
    names = set()
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info["name"]
            if name:
                names.add(name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return sorted(names, key=str.lower)


def parse_youtube_channel(title: str) -> str | None:
    if "YouTube" not in title:
        return None
    title = re.sub(r"\s*—.*$", "", title).strip()
    title = re.sub(r"\s*-\s*YouTube\s*$", "", title).strip()
    parts = title.rsplit(" - ", 1)
    if len(parts) == 2 and parts[1].strip():
        return parts[1].strip()
    return None


def get_pid_to_title() -> dict[int, str]:
    result: dict[int, str] = {}
    EnumWindowsProc    = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
    GetWindowText      = ctypes.windll.user32.GetWindowTextW
    GetWindowTextLen   = ctypes.windll.user32.GetWindowTextLengthW
    IsWindowVisible    = ctypes.windll.user32.IsWindowVisible
    GetWinThreadProcId = ctypes.windll.user32.GetWindowThreadProcessId

    def _cb(hwnd, _):
        if not IsWindowVisible(hwnd):
            return True
        length = GetWindowTextLen(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        GetWindowText(hwnd, buf, length + 1)
        pid = ctypes.c_ulong()
        GetWinThreadProcId(hwnd, ctypes.byref(pid))
        if pid.value and pid.value not in result:
            result[pid.value] = buf.value
        return True

    ctypes.windll.user32.EnumWindows(EnumWindowsProc(_cb), 0)
    return result


@committed_state("channels", path=lambda: WHITELIST_FILE)
class WhitelistManager:
    def __init__(self):
        self.channels: list[str] = []
        self._load()

    def _load(self):
        if WHITELIST_FILE.exists():
            try:
                data = read_json(WHITELIST_FILE, collection="channels", item_type=str)
                self.channels = data.get("channels", [])
                return
            except Exception as exc:
                raise DataFileError(WHITELIST_FILE) from exc
        self.channels = list(DEFAULT_CHANNELS)
        self._save()

    def _save(self):
        atomic_write_text(WHITELIST_FILE,
            json.dumps({"channels": self.channels}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_whitelisted(self, channel: str) -> bool:
        return any(channel.lower() == c.lower() for c in self.channels)

    def add(self, channel: str):
        channel = channel.strip()
        if channel and not self.is_whitelisted(channel):
            self.channels.append(channel)
            self._save()

    def remove(self, channel: str):
        self.channels = [c for c in self.channels if c.lower() != channel.lower()]
        self._save()


class SmartClassifier:
    def __init__(self):
        self._model       = None
        self._study_emb   = None
        self._entertain_emb = None
        self.ready = False
        self.error: str = ""

    def load(self):
        try:
            from sentence_transformers import SentenceTransformer
            from sklearn.metrics.pairwise import cosine_similarity as _cs
            self._cs            = _cs
            self._model         = SentenceTransformer(SMART_MODEL)
            self._study_emb     = self._model.encode(STUDY_PHRASES,         convert_to_numpy=True)
            self._entertain_emb = self._model.encode(ENTERTAINMENT_PHRASES, convert_to_numpy=True)
            self.ready = True
        except Exception as e:
            self.error = str(e)

    def is_study(self, title: str) -> tuple[bool, float, float]:
        if not self.ready or not title.strip():
            return False, 0.0, 0.0
        emb = self._model.encode([title], convert_to_numpy=True)
        s = float(self._cs(emb, self._study_emb).max())
        e = float(self._cs(emb, self._entertain_emb).max())
        return s >= e, round(s, 3), round(e, 3)


_SCREEN_PROMPT = (
    "Look at this screenshot of a student's computer screen. Decide STUDY or BLOCK.\n\n"
    "STUDY = studying/working/researching, coding, reading documents/textbooks, "
    "using a search engine or reference site, OR a chat/messaging app where the "
    "VISIBLE conversation text is about schoolwork — homework, documents, class "
    "schedule, assignments, exam prep (e.g. exchanging study materials with a "
    "teacher or classmate).\n\n"
    "BLOCK = gaming, entertainment videos, or a chat/messaging app where the "
    "VISIBLE conversation text is casual/social chit-chat, jokes, gossip, or "
    "about games/entertainment. A messaging app being open is NOT by itself a "
    "reason to block — judge by the actual visible text/topic in the "
    "conversation, not by which app it is.\n\n"
    "Music apps (Spotify, YouTube Music, etc.) are STUDY only if playing "
    "lofi, classical, ambient, or focus music. Pop, gaming, anime music = BLOCK.\n\n"
    "If the visible content is unclear, too small to read, or genuinely "
    "ambiguous, default to STUDY rather than guessing BLOCK — avoid wrongly "
    "blocking real schoolwork.\n\n"
    "Reply in this exact format only: STUDY:<short reason> or BLOCK:<short reason>"
)


class ScreenClassifier:
    """Chụp toàn màn hình, dùng Ollama vision local để phán quyết học hay giải trí."""
    COOLDOWN = 10  # giây giữa các lần gọi — kiểm tra thường xuyên hơn để phản ứng nhanh
    # Sau ngần này lần LỖI liên tiếp (không phải "phát hiện giải trí" mà là AI
    # không phản hồi được — Ollama tắt, mất mạng...), Blocker sẽ ngừng tin vào
    # Screen AI và chuyển sang lớp title-based AI thay vì tiếp tục cộng dồn điểm
    # lười biếng chỉ vì dịch vụ AI bị lỗi.
    ERROR_FALLBACK_THRESHOLD = 3

    def __init__(self):
        self._last_check  = 0.0
        self._last_result: tuple[bool, str] = (True, "待機中")
        self._prev_is_study: bool | None = None  # None = まだ判定なし
        self._pending     = False
        self.on_result    = None  # callback(is_study: bool, reason: str) — 変化時のみ
        self.consecutive_errors = 0
        # ~4 lần phát hiện "không học" liên tiếp (mỗi lần cách nhau COOLDOWN=10s)
        # mới thật sự kill → khoảng 30s hành vi xao nhãng liên tục, cảnh báo từ
        # lần thứ 2 (~10s). Không ngắt ngay ở lần đầu.
        self.laziness  = LazinessTracker(increase=25, decay=100,
                                          warn_threshold=50, kill_threshold=100)
        self.verdict   = "ok"  # cập nhật đúng 1 lần mỗi khi AI thực sự chạy

    def classify(self, ollama_model: str = "", api_key: str = "") -> tuple[bool, str]:
        """Non-blocking — trả về kết quả cache, cập nhật ngầm khi hết cooldown."""
        now = time.time()
        if not self._pending and now - self._last_check >= self.COOLDOWN:
            self._pending = True
            threading.Thread(
                target=self._update, args=(ollama_model, api_key), daemon=True
            ).start()
        return self._last_result

    def _capture_b64(self) -> str:
        import base64, io
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.thumbnail((1280, 720))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=65)
        return base64.standard_b64encode(buf.getvalue()).decode()

    def _update(self, ollama_model: str, api_key: str):
        try:
            b64 = self._capture_b64()
            if ollama_model:
                text = self._call_ollama(ollama_model, b64)
            elif api_key:
                text = self._call_claude(api_key, b64)
            else:
                self._last_result = (True, "バックエンド未設定")
                return
            is_study = text.upper().startswith("STUDY")
            reason   = text.split(":", 1)[1].strip() if ":" in text else text[:60]
            self._last_result = (is_study, reason)
            self.consecutive_errors = 0  # AI phản hồi thành công → reset bộ đếm lỗi
        except Exception as e:
            # Fail-closed: AI lỗi (Ollama không chạy, mạng lỗi...) KHÔNG được coi
            # là "đang học" mặc định — nếu không, tắt Ollama là vô hiệu hóa luôn
            # việc chặn. Coi như "chưa xác nhận học", để LazinessTracker xử lý
            # dần dần (lỗi thoáng qua vẫn còn ân hạn, lỗi kéo dài mới thực sự chặn).
            # Nếu lỗi kéo dài (ERROR_FALLBACK_THRESHOLD lần), Blocker sẽ tự
            # chuyển sang title-based AI thay vì tiếp tục dựa vào Screen AI lỗi.
            self._last_result = (False, f"err:{str(e)[:50]}")
            self.consecutive_errors += 1
        finally:
            self._last_check = time.time()
            self._pending = False
            is_study = self._last_result[0]
            # Chỉ cộng/trừ điểm lười biếng đúng 1 lần mỗi khi AI THỰC SỰ chạy
            # (mỗi COOLDOWN giây) — không phải mỗi lần vòng quét 3s gọi classify().
            self.verdict = self.laziness.update(not is_study)
            if self.on_result and is_study != self._prev_is_study:
                self.on_result(*self._last_result)
            self._prev_is_study = is_study

    def _call_ollama(self, model: str, b64: str) -> str:
        import json, urllib.request
        payload = json.dumps({
            "model": model,
            "prompt": _SCREEN_PROMPT,
            "images": [b64],
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read()).get("response", "").strip()

    def _call_claude(self, api_key: str, b64: str) -> str:
        import anthropic as _ant
        client = _ant.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": _SCREEN_PROMPT},
            ]}],
        )
        return resp.content[0].text.strip()


class LazinessTracker:
    """Đo dấu hiệu 'lười biếng' tích lũy theo thời gian thay vì chặn ngay lập tức
    ở lần phát hiện giải trí đầu tiên. Điểm tăng khi phát hiện giải trí liên tục,
    giảm nhanh hơn khi quay lại học/tra cứu. Chỉ báo 'kill' khi điểm vượt ngưỡng,
    tức là hành vi giải trí đã kéo dài — không phải một cái liếc mắt thoáng qua."""

    def __init__(self, increase=30, decay=40, warn_threshold=45,
                 kill_threshold=90, max_score=100):
        self.increase       = increase
        self.decay          = decay
        self.warn_threshold = warn_threshold
        self.kill_threshold = kill_threshold
        self.max_score      = max_score
        self.score          = 0.0

    def update(self, is_entertainment: bool) -> str:
        """Trả về 'ok' | 'warn' | 'kill'."""
        if is_entertainment:
            self.score = min(self.max_score, self.score + self.increase)
        else:
            self.score = max(0.0, self.score - self.decay)

        if self.score >= self.kill_threshold:
            self.score = self.warn_threshold  # sau khi chặn, hạ về mức cảnh báo
            return "kill"
        if self.score >= self.warn_threshold:
            return "warn"
        return "ok"


class Blocker:
    labels = None  # SiteLabels (nhãn phụ huynh); None = không dùng

    def __init__(self, on_kill_callback=None, on_allow_callback=None,
                 on_model_ready=None, on_screen_classify=None):
        self._lock = threading.Lock()
        self.running = False
        self._thread = None
        self._stop_event = threading.Event()
        self.on_kill_callback    = on_kill_callback
        self.on_allow_callback   = on_allow_callback
        self.on_model_ready      = on_model_ready
        self.on_screen_classify  = on_screen_classify
        self.smart_enabled       = True
        self.screen_enabled      = False
        self.screen_api_key      = ""    # Claude fallback
        self.screen_ollama_model = ""    # Ollama (ưu tiên)
        self.smart     = SmartClassifier()
        self.screen    = ScreenClassifier()
        self.whitelist = WhitelistManager()
        self.labels    = SiteLabels()
        self._cached_blocked: list[str] = load_blocked_apps()
        self.screen.on_result = self._on_screen_result
        # Theo dõi dấu hiệu lười biếng theo TÊN browser, không theo PID — Chrome
        # tạo process con mới mỗi khi chuyển site/tab (site isolation), nên theo
        # PID sẽ bị reset liên tục.
        self._title_laziness: dict[str, LazinessTracker] = {}
        # Lười biếng cho screen AI được theo dõi ngay trong self.screen (ScreenClassifier),
        # vì điểm chỉ nên cộng/trừ mỗi khi AI THỰC SỰ chạy (mỗi COOLDOWN giây),
        # không phải mỗi lần vòng quét 3s hỏi kết quả cache.
        threading.Thread(target=self._load_model, daemon=True).start()

    def _load_model(self):
        self.smart.load()
        if self.on_model_ready:
            self.on_model_ready(self.smart.ready, self.smart.error)

    def _on_screen_result(self, is_study: bool, reason: str):
        if self.on_screen_classify:
            self.on_screen_classify(is_study, reason)

    def start(self):
        with self._lock:
            if self.running:
                return
            self.running = True
            self._stop_event = threading.Event()
            self._title_laziness = {}
            self._thread = threading.Thread(target=self._loop, args=(self._stop_event,), daemon=True)
            self._thread.start()

    def stop(self):
        with self._lock:
            self.running = False
            self._stop_event.set()

    def _kill_if_active(self, proc, stop_event):
        # Serialize the final cancellation check with stop(), not AI inference.
        with self._lock:
            if stop_event.is_set() or not self.running:
                return False
            if (proc.info['name'] or '').lower() not in self._cached_blocked:
                return False
            proc.kill()
            return True

    def reload_blocked_apps(self):
        """Đọc lại blocked.json — gọi khi người dùng vừa thêm/xóa app trong
        Settings, để có hiệu lực ngay không cần khởi động lại."""
        self._cached_blocked = load_blocked_apps()

    def _get_title_tracker(self, browser_name: str) -> LazinessTracker:
        """Theo dõi theo TÊN process (vd 'chrome.exe'), không theo PID —
        vì Chrome tạo process con mới (PID mới) mỗi khi chuyển sang site khác
        (site isolation) hoặc chuyển tab, nên theo PID sẽ bị reset điểm liên
        tục, dễ bị né bằng cách đổi tab/mở lại trước khi đạt ngưỡng."""
        tracker = self._title_laziness.get(browser_name)
        if tracker is None:
            tracker = LazinessTracker()
            self._title_laziness[browser_name] = tracker
        return tracker

    def _loop(self, stop_event):
        while not stop_event.is_set():
            blocked = self._cached_blocked
            killed  = []
            allowed = []

            # ── Screen AI: lấy phán quyết toàn màn hình (non-blocking) ──────
            screen_is_study = True   # mặc định cho qua nếu chưa có kết quả
            using_screen_ai = self.screen_enabled and (
                bool(self.screen_ollama_model) or bool(self.screen_api_key)
            )
            screen_verdict = "ok"
            if using_screen_ai:
                screen_is_study, _ = self.screen.classify(
                    ollama_model=self.screen_ollama_model,
                    api_key=self.screen_api_key,
                )
                # self.screen.verdict được ScreenClassifier tự cập nhật đúng 1 lần
                # mỗi khi AI thực sự chạy (mỗi COOLDOWN=10s) — không tính lại ở đây.
                screen_verdict = self.screen.verdict
            # Screen AI lỗi liên tục (Ollama tắt, mất mạng...) → không còn tin vào
            # nó nữa, để tránh browser đang học thật bị chặn oan chỉ vì AI lỗi.
            # Chuyển xuống lớp title-based AI (hoặc basic block nếu cả hai đều
            # không sẵn sàng) thay vì tiếp tục cộng dồn điểm dựa trên lỗi.
            screen_usable = using_screen_ai and (
                self.screen.consecutive_errors < ScreenClassifier.ERROR_FALLBACK_THRESHOLD
            )

            # ── Title-based: lấy PID→title khi cần ─────────────────────────
            pid_titles: dict[int, str] = {}
            if self.smart_enabled:
                try:
                    pid_titles = get_pid_to_title()
                except Exception:
                    pass

            for proc in psutil.process_iter(["name", "pid"]):
                if stop_event.is_set():
                    return
                try:
                    name = (proc.info["name"] or "").lower()
                    if name not in blocked:
                        continue

                    reason = "ブロックリストのアプリ"  # mặc định cho app không qua AI (discord, steam...)

                    if name in BROWSER_PROCESSES and (self.smart_enabled or screen_usable):
                        pid   = proc.info["pid"]
                        title = pid_titles.get(pid, "") if self.smart_enabled else ""

                        if not title:
                            # ウィンドウタイトルが取れない（背景/補助プロセス、
                            # GPU/renderer等）→ 個別に判定しない。実際に見える
                            # ウィンドウを持つプロセス側で判定されるので誤kill
                            # を避けるため見送る。Screen AIしか使えない場合の
                            # みは画面全体の判定をそのまま適用する。
                            if not screen_usable:
                                # Fall back to the explicit blocklist for browser roots.
                                # Renderer/helper children must not be killed individually.
                                args = [arg.lower() for arg in proc.cmdline()[1:]]
                                if any(arg.startswith("--type=") or arg in
                                       ("-contentproc", "--utility", "--gpu") for arg in args):
                                    continue
                                if self._kill_if_active(proc, stop_event):
                                    killed.append((proc.info["name"], reason))
                                continue
                            if screen_is_study:
                                allowed.append((name, "screen", "screenAI", "学習中と判断"))
                                continue
                            if screen_verdict == "warn":
                                allowed.append((name, "screen", "warn",
                                                f"娯楽の兆候が続いています (score={self.screen.laziness.score:.0f})"))
                                continue
                            if screen_verdict == "ok":
                                continue
                            reason = f"スクリーンAI: 娯楽行動が継続 ({self.screen._last_result[1][:40]})"
                            if self._kill_if_active(proc, stop_event):
                                killed.append((proc.info["name"], reason))
                            continue

                        # タイトルあり — 参照ツール/ホワイトリストは無条件許可
                        if is_reference_tool(title):
                            allowed.append((name, title[:60], "reference", "検索/参照ツール"))
                            continue
                        channel = parse_youtube_channel(title)
                        if channel and self.whitelist.is_whitelisted(channel):
                            allowed.append((name, title[:60], "whitelist", channel))
                            continue

                        # タイトルAIとScreen AI、両方の信号を1つの
                        # LazinessTracker（ブラウザ名ごとに共有）にまとめる —
                        # 以前は screen が「学習」と言った時だけタイトルで反論、
                        # screen が「娯楽」と言った時は別のトラッカーを使って
                        # いたため、進捗が2つに分散して両方とも閾値に届かない
                        # バグがあった。今はどちらか一方でも「娯楽」と言えば
                        # 娯楽として扱い、同じトラッカーに積み上げる。
                        key = site_key(title)
                        label = self.labels.label_for(key) if self.labels else None
                        title_study = None
                        unsure = False
                        if label:
                            # Phụ huynh đã quyết định cho trang này — ưu tiên hơn AI.
                            title_study = (label == "study")
                        elif self.smart.ready:
                            title_study, s_score, e_score = self.smart.is_study(title)
                            unsure = abs(s_score - e_score) < UNSURE_MARGIN
                        if stop_event.is_set():
                            return
                        screen_study = screen_is_study if screen_usable else None
                        signals = [s for s in (title_study, screen_study) if s is not None]

                        if unsure and screen_study is None:
                            # AI không chắc: không chặn, nhờ phụ huynh gán nhãn.
                            # Chỉ báo giao diện khi gặp trang MỚI (không báo mỗi 3 giây).
                            if self.labels and self.labels.add_pending(key, title):
                                allowed.append((name, title[:60], "unsure", key))
                            continue

                        if not signals:
                            reason = "AI未準備 — 基本ブロックリストを適用"
                            if self._kill_if_active(proc, stop_event):
                                killed.append((proc.info["name"], reason))
                            continue

                        tracker = self._get_title_tracker(name)
                        if all(signals):
                            tracker.update(False)
                            if label == "study":
                                allowed.append((name, title[:60], "label", key))
                            else:
                                allowed.append((name, title[:60], "AI", "学習中と判断"))
                            continue

                        verdict = tracker.update(True)
                        if verdict == "warn":
                            allowed.append((name, title[:60], "warn",
                                            f"娯楽の兆候が続いています (score={tracker.score:.0f})"))
                            continue
                        if verdict == "ok":
                            continue
                        reason = f"AI: 娯楽と判定 - {title[:40]}"
                        if self._kill_if_active(proc, stop_event):
                            killed.append((proc.info["name"], reason))
                        continue

                    if self._kill_if_active(proc, stop_event):
                        killed.append((proc.info["name"], reason))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            if stop_event.is_set():
                return
            if killed  and self.on_kill_callback:
                self.on_kill_callback(killed)
            if allowed and self.on_allow_callback:
                self.on_allow_callback(allowed)

            stop_event.wait(SCAN_INTERVAL)
