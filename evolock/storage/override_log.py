from evolock.storage.state import committed_state
from evolock.storage.json_file import read_json, atomic_write_text, DataFileError
import json
from dataclasses import dataclass, asdict
from evolock.paths import DATA_DIR
from datetime import datetime, date, timedelta

OVERRIDE_FILE = DATA_DIR / "overrides.json"
MAX_RECORDS = 300


@dataclass
class OverrideRecord:
    date: str
    time: str
    reason: str
    note: str
    planned_minutes: int
    actual_minutes: int


@committed_state("records", path=lambda: OVERRIDE_FILE)
class OverrideLogger:
    """Ghi lại mỗi lần dừng học sớm có chủ ý (qua mã phiên Gmail) — lý do,
    ghi chú, thời lượng dự kiến vs thực tế — làm cơ sở dữ liệu thật cho
    AI coach phản chiếu, thay vì chỉ đếm 'số lần dùng mật khẩu'."""

    def __init__(self):
        self.records: list[OverrideRecord] = []
        self._load()

    def _load(self):
        if not OVERRIDE_FILE.exists():
            return
        try:
            data = read_json(OVERRIDE_FILE, collection="records")
            self.records = [OverrideRecord(**r) for r in data.get("records", [])]
        except Exception as exc:
            raise DataFileError(OVERRIDE_FILE) from exc

    def _save(self):
        atomic_write_text(OVERRIDE_FILE, json.dumps({"records": [asdict(r) for r in self.records]},
                       ensure_ascii=False, indent=2))

    def log(self, reason: str, note: str, planned_minutes: int, actual_minutes: int):
        now = datetime.now()
        self.records.append(OverrideRecord(
            date=str(now.date()), time=now.strftime("%H:%M"),
            reason=reason, note=note[:200],
            planned_minutes=planned_minutes, actual_minutes=actual_minutes,
        ))
        if len(self.records) > MAX_RECORDS:
            self.records = self.records[-MAX_RECORDS:]
        self._save()

    def last_n_days(self, n: int = 7) -> list[OverrideRecord]:
        cutoff = str(date.today() - timedelta(days=max(0, n - 1)))
        return [r for r in self.records if n > 0 and cutoff <= r.date <= str(date.today())]
