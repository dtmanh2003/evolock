from evolock.storage.state import committed_state
from evolock.storage.json_file import read_json, atomic_write_text, DataFileError
import json
from dataclasses import dataclass, field, asdict
from evolock.paths import DATA_DIR
from datetime import date

STATS_FILE = DATA_DIR / "stats.json"

RANKS = [
    (0,  "小学生"),
    (5,  "大学生"),
    (10, "研究生"),
    (20, "専門家"),
    (30, "達人"),
    (50, "伝説"),
]

ACHIEVEMENTS = [
    ("first_task",    "第一歩",             "初めてのタスクを完了"),
    ("task_10",       "勤勉家",             "タスクを10件完了"),
    ("task_50",       "スーパースター",     "タスクを50件完了"),
    ("streak_3",      "3日連続",            "3日連続でアクティブ"),
    ("streak_7",      "黄金週間",           "7日連続でアクティブ"),
    ("streak_30",     "鉄の月",             "30日連続でアクティブ"),
    ("level_5",       "レベル5到達",        "レベル5に到達"),
    ("level_10",      "レベル10到達",       "レベル10に到達"),
    ("study_60min",   "集中力",             "1日に60分学習を達成"),
    ("study_300min",  "頂点",               "累計300分学習を達成"),
]

EXP_PER_TASK = 50
EXP_PER_10MIN = 20
EXP_EMERGENCY_PENALTY = 100
EXP_DAILY_CHECKIN = 10

STREAK_MULTIPLIERS = [
    (30, 2.0),
    (14, 1.5),
    (7,  1.25),
    (0,  1.0),
]

def streak_multiplier(streak: int) -> float:
    for min_days, mult in STREAK_MULTIPLIERS:
        if streak >= min_days:
            return mult
    return 1.0


def exp_for_level(level: int) -> int:
    return max(1, level) * 100


@dataclass
class Stats:
    exp: int = 0
    level: int = 1
    streak: int = 0
    last_active_date: str = ""
    total_tasks: int = 0
    total_study_minutes: int = 0
    today_study_minutes: int = 0
    today_date: str = ""
    unlocked_achievements: list = field(default_factory=list)
    rewarded_sessions: list = field(default_factory=list)


@committed_state("stats", path=lambda: STATS_FILE)
class GameManager:
    def __init__(self):
        self.stats = Stats()
        self._load()
        self._check_streak()

    def _load(self):
        if not STATS_FILE.exists():
            return
        try:
            data = read_json(STATS_FILE)
            s = self.stats
            for k, v in data.items():
                if k in Stats.__dataclass_fields__:
                    setattr(s, k, v)
            # Đảm bảo level luôn >= 1
            if s.level < 1:
                s.level = 1
        except Exception as exc:
            raise DataFileError(STATS_FILE) from exc

    def _save(self):
        atomic_write_text(STATS_FILE, json.dumps(asdict(self.stats), ensure_ascii=False, indent=2))

    def _check_streak(self):
        today = str(date.today())
        s = self.stats
        if s.today_date != today:
            s.today_study_minutes = 0
            s.today_date = today
        if not s.last_active_date:
            return
        last = date.fromisoformat(s.last_active_date)
        today_d = date.fromisoformat(today)
        if (today_d - last).days > 1:
            s.streak = 0
        self._save()

    def _add_exp(self, amount: int) -> int:
        self.stats.exp += amount
        leveled = 0
        while self.stats.exp >= exp_for_level(self.stats.level):
            self.stats.exp -= exp_for_level(self.stats.level)
            self.stats.level += 1
            leveled += 1
        return leveled

    def _mark_active(self) -> int:
        """Streak更新 + 初回チェックイン時にボーナスEXPを返す。"""
        today = str(date.today())
        s = self.stats
        if s.last_active_date == today:
            return 0
        if s.last_active_date:
            last = date.fromisoformat(s.last_active_date)
            today_d = date.fromisoformat(today)
            if (today_d - last).days == 1:
                s.streak += 1
            else:
                s.streak = 1
        else:
            s.streak = 1
        s.last_active_date = today
        # Daily check-in bonus
        self._add_exp(EXP_DAILY_CHECKIN)
        return EXP_DAILY_CHECKIN

    def on_task_complete(self) -> dict:
        self._check_streak()
        s = self.stats
        s.total_tasks += 1
        checkin_exp = self._mark_active()
        mult  = streak_multiplier(s.streak)
        exp   = int(EXP_PER_TASK * mult)
        leveled = self._add_exp(exp)
        new_ach = self._check_achievements()
        self._save()
        return {"exp": exp, "checkin_exp": checkin_exp, "mult": mult,
                "leveled": leveled, "achievements": new_ach}

    def on_emergency_used(self) -> dict:
        """Trừ EXP khi dùng mã khẩn cấp. Nếu EXP âm thì xuống level (min level 1)."""
        self._check_streak()
        s = self.stats
        penalty = EXP_EMERGENCY_PENALTY
        leveled_down = 0

        s.exp -= penalty
        while s.exp < 0 and s.level > 1:
            s.level -= 1
            s.exp += exp_for_level(s.level)
            leveled_down += 1
        s.exp = max(0, s.exp)

        self._save()
        return {"penalty": penalty, "leveled_down": leveled_down}

    def on_study_complete(self, minutes: int, session_id=None, session_date=None):
        if session_id and session_id in self.stats.rewarded_sessions:
            return None
        self._check_streak()
        s = self.stats
        s.total_study_minutes += minutes
        if session_date is None or session_date == str(date.today()):
            s.today_study_minutes += minutes
        checkin_exp = self._mark_active() if session_date in (None, str(date.today())) else 0
        mult    = streak_multiplier(s.streak)
        if session_id:
            s.rewarded_sessions.append(session_id)
        base    = (minutes // 10) * EXP_PER_10MIN
        exp     = int(base * mult)
        leveled = self._add_exp(exp)
        new_ach = self._check_achievements()
        self._save()
        return {"exp": exp, "checkin_exp": checkin_exp, "mult": mult,
                "leveled": leveled, "achievements": new_ach}

    def _check_achievements(self) -> list[str]:
        s = self.stats
        unlocked_set = set(s.unlocked_achievements)
        new = []
        checks = [
            ("first_task",   s.total_tasks >= 1),
            ("task_10",      s.total_tasks >= 10),
            ("task_50",      s.total_tasks >= 50),
            ("streak_3",     s.streak >= 3),
            ("streak_7",     s.streak >= 7),
            ("streak_30",    s.streak >= 30),
            ("level_5",      s.level >= 5),
            ("level_10",     s.level >= 10),
            ("study_60min",  s.today_study_minutes >= 60),
            ("study_300min", s.total_study_minutes >= 300),
        ]
        for key, condition in checks:
            if condition and key not in unlocked_set:
                unlocked_set.add(key)
                s.unlocked_achievements.append(key)
                new.append(key)
        return new

    def get_rank(self) -> str:
        rank = RANKS[0][1]
        for min_lvl, name in RANKS:
            if self.stats.level >= min_lvl:
                rank = name
        return rank

    def get_exp_progress(self) -> tuple[int, int]:
        needed = exp_for_level(self.stats.level)
        return self.stats.exp, needed

    def get_achievement_info(self, key: str) -> tuple[str, str]:
        for k, name, desc in ACHIEVEMENTS:
            if k == key:
                return name, desc
        return key, ""
