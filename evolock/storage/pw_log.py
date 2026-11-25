from evolock.storage.state import committed_state
from evolock.storage.json_file import read_json, atomic_write_text, DataFileError
import json
from dataclasses import dataclass, asdict
from evolock.paths import DATA_DIR
from datetime import datetime, date, timedelta

PW_LOG_FILE = DATA_DIR / "pw_log.json"
MAX_EVENTS  = 300   # giữ tối đa 300 sự kiện (~1 năm)


@dataclass
class PasswordEvent:
    date:       str   # "2026-06-03"
    time:       str   # "14:30"
    event_type: str   # "password" | "emergency"
    action:     str   # "stop_study" | "quit_app" | "manage"


@committed_state("events", path=lambda: PW_LOG_FILE)
class PasswordLogger:
    def __init__(self):
        self.events: list[PasswordEvent] = []
        self._load()

    def _load(self):
        if not PW_LOG_FILE.exists():
            return
        try:
            data = read_json(PW_LOG_FILE, collection="events")
            self.events = [PasswordEvent(**e) for e in data.get("events", [])]
        except Exception as exc:
            raise DataFileError(PW_LOG_FILE) from exc

    def _save(self):
        if len(self.events) > MAX_EVENTS:
            self.events = self.events[-MAX_EVENTS:]
        atomic_write_text(PW_LOG_FILE, json.dumps({"events": [asdict(e) for e in self.events]},
                       ensure_ascii=False, indent=2))

    def log(self, event_type: str, action: str):
        """Ghi lại 1 lần dùng password. Chỉ gọi khi xác thực thành công."""
        now = datetime.now()
        self.events.append(PasswordEvent(
            date=str(date.today()),
            time=now.strftime("%H:%M"),
            event_type=event_type,
            action=action,
        ))
        self._save()

    def last_n_days(self, n: int = 7) -> list[PasswordEvent]:
        cutoff = str(date.today() - timedelta(days=max(0, n - 1)))
        return [e for e in self.events if n > 0 and cutoff <= e.date <= str(date.today())]

    def summary(self, n: int = 7) -> dict:
        """Trả về thống kê password usage trong n ngày gần nhất."""
        events = self.last_n_days(n)
        pw_stops   = [e for e in events if e.event_type == "password" and e.action == "stop_study"]
        pw_quits   = [e for e in events if e.event_type == "password" and e.action == "quit_app"]
        em_uses    = [e for e in events if e.event_type == "emergency"]

        # stops theo ngày  {"2026-06-01": ["14:30", "16:00"]}
        stops_by_date: dict[str, list[str]] = {}
        for e in pw_stops:
            stops_by_date.setdefault(e.date, []).append(e.time)

        # phân tích giờ của pw_stops
        hours = [int(e.time.split(":")[0]) for e in pw_stops if e.time]
        morning   = sum(1 for h in hours if 5  <= h < 12)
        afternoon = sum(1 for h in hours if 12 <= h < 18)
        evening   = sum(1 for h in hours if 18 <= h < 24 or h < 5)

        return {
            "days":                  n,
            "total_password_stops":  len(pw_stops),
            "total_quit":            len(pw_quits),
            "total_emergency":       len(em_uses),
            "stops_by_date":         stops_by_date,
            "morning_stops":         morning,
            "afternoon_stops":       afternoon,
            "evening_stops":         evening,
            "emergency_events":      [{"date": e.date, "time": e.time} for e in em_uses],
        }
