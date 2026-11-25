"""Validate loaded state and restore the last committed state after save failure."""
from copy import deepcopy
from dataclasses import fields, is_dataclass
from datetime import date
from functools import wraps
from evolock.storage.json_file import DataFileError


def validate(value):
    if is_dataclass(value):
        for field in fields(value):
            item = getattr(value, field.name)
            expected = field.type
            if expected in (int, str, bool, list) and type(item) is not expected:
                raise ValueError(f"Invalid field type: {field.name}")
            if type(item) is int and item < 0:
                raise ValueError(f"Negative field: {field.name}")
            if field.name in ("date", "today_date", "last_active_date") and item:
                date.fromisoformat(item)
            if field.name in ("unlocked_achievements", "rewarded_sessions") and any(type(x) is not str for x in item):
                raise ValueError("Invalid achievements")
    elif isinstance(value, list):
        for item in value:
            validate(item)


def committed_state(*attributes, path, defaults=None):
    """For single-threaded managers; mutations become committed only after _save."""
    def decorate(cls):
        load, save = cls._load, cls._save

        def snapshot(self):
            return {name: deepcopy(getattr(self, name)) for name in attributes}

        def check(self):
            for name in attributes:
                validate(getattr(self, name))
            if defaults is not None:
                data = self.data
                for key, default in defaults.items():
                    if key in data and type(data[key]) is not type(default):
                        raise ValueError(f"Invalid setting type: {key}")
                if data.get("daily_goal_minutes", 120) <= 0:
                    raise ValueError("Invalid daily goal")
                suggestions = data.get("task_name_suggestions", {})
                if any(not isinstance(v, list) or any(type(x) is not str for x in v)
                       for v in suggestions.values()):
                    raise ValueError("Invalid task suggestions")
            if hasattr(self, "channels") and any(type(x) is not str for x in self.channels):
                raise ValueError("Invalid channels")

        @wraps(load)
        def checked_load(self):
            try:
                load(self)
                check(self)
            except (ValueError, TypeError) as exc:
                raise DataFileError(path()) from exc
            self._committed_state = snapshot(self)

        @wraps(save)
        def checked_save(self):
            try:
                try:
                    check(self)
                except (ValueError, TypeError) as exc:
                    raise DataFileError(path()) from exc
                save(self)
            except Exception:
                if hasattr(self, "_committed_state"):
                    for key, value in deepcopy(self._committed_state).items():
                        setattr(self, key, value)
                raise
            self._committed_state = snapshot(self)

        cls._load, cls._save = checked_load, checked_save
        return cls
    return decorate
