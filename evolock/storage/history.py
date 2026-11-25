from evolock.storage.state import committed_state
from evolock.storage.json_file import read_json, atomic_write_text, DataFileError
import json
import uuid
from dataclasses import dataclass, asdict
from evolock.paths import DATA_DIR
from datetime import datetime, date, timedelta

HISTORY_FILE = DATA_DIR / "history.json"


@dataclass
class Session:
    session_type: str   # "study" | "play"
    start_time: str
    end_time: str
    duration_minutes: int
    date: str
    session_id: str = ""
    reward_pending: bool = False


@committed_state("sessions", path=lambda: HISTORY_FILE)
class HistoryManager:
    def __init__(self):
        self.sessions: list[Session] = []
        self._load()

    def _load(self):
        if not HISTORY_FILE.exists():
            return
        try:
            data = read_json(HISTORY_FILE, collection="sessions")
            self.sessions = [Session(**s) for s in data.get("sessions", [])]
        except Exception as exc:
            raise DataFileError(HISTORY_FILE) from exc

    def _save(self):
        atomic_write_text(HISTORY_FILE, json.dumps(
                {"sessions": [asdict(s) for s in self.sessions]},
                ensure_ascii=False, indent=2,
            ))

    def log(self, session_type: str, start: datetime, end: datetime) -> Session | None:
        duration = max(0, int((end - start).total_seconds() / 60))
        if duration < 1:
            return None
        s = Session(
            session_type=session_type,
            start_time=start.strftime("%H:%M"),
            end_time=end.strftime("%H:%M"),
            duration_minutes=duration,
            date=str(date.today()),
            session_id=uuid.uuid4().hex,
            reward_pending=session_type == "study",
        )
        self.sessions.append(s)
        self._save()
        return s

    def settle_rewards(self, game):
        results = []
        for session in self.sessions:
            if session.reward_pending and session.session_type == "study":
                result = game.on_study_complete(session.duration_minutes,
                                                session_id=session.session_id,
                                                session_date=session.date)
                session.reward_pending = False
                self._save()
                if result is not None:
                    results.append(result)
        return results

    def today(self) -> list[Session]:
        today = str(date.today())
        return [s for s in self.sessions if s.date == today]

    def last_n_days(self, n: int = 7) -> list[Session]:
        cutoff = str(date.today() - timedelta(days=max(0, n - 1)))
        return [s for s in self.sessions if n > 0 and cutoff <= s.date <= str(date.today())]

    def today_study_minutes(self) -> int:
        return sum(s.duration_minutes for s in self.today() if s.session_type == "study")
