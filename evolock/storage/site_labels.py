"""Nhãn "học / giải trí" do phụ huynh gán cho các trang mà AI không chắc, và danh sách chờ.

- `labels`: khóa trang (xem `blocker.site_key`) -> "study" | "block". Nhãn được ưu tiên hơn AI.
- `pending`: các trang AI không phân loại được, đang chờ phụ huynh quyết định.
"""

import json
import threading
import time
from datetime import datetime, timedelta

from evolock.paths import DATA_DIR
from evolock.storage.json_file import DataFileError, atomic_write_text, read_json

LABELS_FILE = DATA_DIR / "site_labels.json"
VALID_LABELS = ("study", "block")
MAX_PENDING = 50
PENDING_DAYS = 14  # trang chờ quá lâu mà không ai xử lý thì tự xóa (không giữ dữ liệu duyệt web)
SAVE_EVERY = 60.0  # giây; số lần gặp chỉ ghi đĩa thưa, không ghi mỗi lần quét


class SiteLabels:
    def __init__(self):
        self._lock = threading.Lock()
        self.labels: dict[str, str] = {}
        self.pending: dict[str, dict] = {}
        self._last_save = 0.0
        self._load()

    def _load(self):
        if not LABELS_FILE.exists():
            return
        data = read_json(LABELS_FILE)
        labels = data.get("labels", {})
        pending = data.get("pending", {})
        if (not isinstance(labels, dict) or not isinstance(pending, dict)
                or any(type(k) is not str or v not in VALID_LABELS for k, v in labels.items())
                or any(type(k) is not str or not isinstance(v, dict)
                       or type(v.get("title")) is not str for k, v in pending.items())):
            raise DataFileError(LABELS_FILE)
        self.labels = dict(labels)
        cutoff = (datetime.now() - timedelta(days=PENDING_DAYS)).isoformat(timespec="seconds")
        self.pending = {k: {"title": v["title"], "last": str(v.get("last", "")),
                            "count": v["count"] if type(v.get("count")) is int else 1}
                        for k, v in pending.items() if str(v.get("last", "")) >= cutoff}

    def _save(self):
        atomic_write_text(LABELS_FILE, json.dumps(
            {"labels": self.labels, "pending": self.pending}, ensure_ascii=False, indent=2))
        self._last_save = time.monotonic()

    def label_for(self, key: str) -> str | None:
        with self._lock:
            return self.labels.get(key)

    def add_pending(self, key: str, title: str) -> bool:
        """Ghi trang AI không chắc. Trả về True nếu là trang mới (cần làm mới giao diện)."""
        if not key:
            return False
        with self._lock:
            if key in self.labels:
                return False
            is_new = key not in self.pending
            entry = self.pending.get(key, {"count": 0})
            self.pending[key] = {"title": title[:120],
                                 "last": datetime.now().isoformat(timespec="seconds"),
                                 "count": entry["count"] + 1}
            if is_new:
                while len(self.pending) > MAX_PENDING:
                    oldest = min(self.pending, key=lambda k: self.pending[k]["last"])
                    del self.pending[oldest]
            if is_new or time.monotonic() - self._last_save >= SAVE_EVERY:
                self._save()  # trang mới ghi ngay; số lần gặp chỉ cập nhật thưa
            return is_new

    def set_label(self, key: str, label: str):
        if label not in VALID_LABELS or not key:
            raise ValueError("invalid label")
        with self._lock:
            self.labels[key] = label
            self.pending.pop(key, None)
            self._save()

    def remove_label(self, key: str):
        with self._lock:
            self.labels.pop(key, None)
            self._save()

    def dismiss(self, key: str):
        with self._lock:
            self.pending.pop(key, None)
            self._save()

    def pending_items(self) -> list[tuple[str, str, int]]:
        with self._lock:
            return [(k, v["title"], v["count"]) for k, v in sorted(
                self.pending.items(), key=lambda item: item[1]["last"], reverse=True)]

    def labelled_items(self) -> list[tuple[str, str]]:
        with self._lock:
            return sorted(self.labels.items())
