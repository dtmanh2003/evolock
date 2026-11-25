"""Fail visibly on unreadable data; replace complete JSON files atomically."""
import json
import os
from pathlib import Path
import tempfile


class DataFileError(RuntimeError):
    def __init__(self, path):
        super().__init__(f'Cannot read or save data file: {path}. Original data was not reset.')


def read_json(path, collection=None, item_type=dict):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('Expected JSON object')
        if collection is not None:
            items = data.get(collection, [])
            if type(items) is not list or any(type(item) is not item_type for item in items):
                raise ValueError('Invalid JSON collection')
        return data
    except (OSError, ValueError, UnicodeError) as exc:
        raise DataFileError(path) from exc


def _replace(path, text):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                         dir=path.parent, prefix=path.name + '.',
                                         suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_write_text(path, text, encoding='utf-8'):
    path = Path(path)
    try:
        if not isinstance(json.loads(text), dict):
            raise ValueError('Expected JSON object')
        if path.exists():
            read_json(path)  # Never replace a broken original with defaults.
            _replace(path.with_name(path.name + '.bak'), path.read_text(encoding='utf-8'))
        _replace(path, text)
    except (OSError, ValueError, UnicodeError) as exc:
        raise DataFileError(path) from exc
