from evolock.storage.state import committed_state
from evolock.storage.json_file import read_json, atomic_write_text, DataFileError
import json
from dataclasses import dataclass, asdict
from evolock.paths import DATA_DIR
from datetime import datetime, date, timedelta

ACTIVITY_FILE = DATA_DIR / "activity_log.json"
MAX_EVENTS = 500


@dataclass
class ActivityEvent:
    timestamp: str   # "HH:MM"
    date: str        # "YYYY-MM-DD"
    kind: str         # "warn" | "kill"
    app: str          # tên process hoặc "screen"
    detail: str        # lý do AI đưa ra (đã rút gọn)


@committed_state("events", path=lambda: ACTIVITY_FILE)
class ActivityLogger:
    """Lưu lại các lần AI (screen/title) phát hiện dấu hiệu xao nhãng thật sự
    (warn/kill) — làm cơ sở dữ liệu thật cho AI coach phân tích theo tuần,
    thay vì chỉ hiện thoáng qua trong log UI rồi mất."""

    def __init__(self):
        self.events: list[ActivityEvent] = []
        self._load()

    def _load(self):
        if not ACTIVITY_FILE.exists():
            return
        try:
            data = read_json(ACTIVITY_FILE, collection="events")
            self.events = [ActivityEvent(**e) for e in data.get("events", [])]
        except Exception as exc:
            raise DataFileError(ACTIVITY_FILE) from exc

    def _save(self):
        atomic_write_text(ACTIVITY_FILE, json.dumps({"events": [asdict(e) for e in self.events]},
                       ensure_ascii=False, indent=2))

    def log(self, kind: str, app: str, detail: str):
        now = datetime.now()
        self.events.append(ActivityEvent(
            timestamp=now.strftime("%H:%M"),
            date=str(now.date()),
            kind=kind, app=app, detail=detail[:80],
        ))
        if len(self.events) > MAX_EVENTS:
            self.events = self.events[-MAX_EVENTS:]
        self._save()

    def last_n_days(self, n: int = 7) -> list[ActivityEvent]:
        cutoff = str(date.today() - timedelta(days=max(0, n - 1)))
        return [e for e in self.events if n > 0 and cutoff <= e.date <= str(date.today())]
