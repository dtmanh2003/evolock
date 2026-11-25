from evolock.storage.state import committed_state
from evolock.storage.json_file import read_json, atomic_write_text, DataFileError
import json
from dataclasses import dataclass, field, asdict
from evolock.paths import DATA_DIR
from datetime import datetime

TASKS_FILE = DATA_DIR / "tasks.json"

TASK_TYPES = ["学習", "仕事", "読書", "運動", "その他"]


@dataclass
class Task:
    id: int
    name: str
    task_type: str
    completed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%H:%M %d/%m/%Y"))
    completed_at: str = ""


@committed_state("tasks", "_next_id", path=lambda: TASKS_FILE)
class TaskManager:
    def __init__(self):
        self.tasks: list[Task] = []
        self._next_id = 1
        self._load()

    def _load(self):
        if not TASKS_FILE.exists():
            return
        try:
            data = read_json(TASKS_FILE, collection="tasks")
            self.tasks = [Task(**t) for t in data.get("tasks", [])]
            self._next_id = max((t.id for t in self.tasks), default=0) + 1
        except Exception as exc:
            raise DataFileError(TASKS_FILE) from exc

    def _save(self):
        atomic_write_text(TASKS_FILE, json.dumps({"tasks": [asdict(t) for t in self.tasks]}, ensure_ascii=False, indent=2))

    def add(self, name: str, task_type: str) -> Task:
        task = Task(id=self._next_id, name=name.strip(), task_type=task_type)
        self._next_id += 1
        self.tasks.append(task)
        self._save()
        return task

    def complete(self, task_id: int) -> Task | None:
        for t in self.tasks:
            if t.id == task_id and not t.completed:
                t.completed = True
                t.completed_at = datetime.now().strftime("%H:%M %d/%m/%Y")
                self._save()
                return t
        return None

    def delete(self, task_id: int):
        self.tasks = [t for t in self.tasks if t.id != task_id]
        self._save()

    def pending(self) -> list[Task]:
        return [t for t in self.tasks if not t.completed]

    def completed_today(self) -> list[Task]:
        today = datetime.now().strftime("%d/%m/%Y")
        return [t for t in self.tasks if t.completed and today in t.completed_at]
