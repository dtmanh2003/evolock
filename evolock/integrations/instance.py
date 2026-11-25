"""One GUI writer per data directory, enforced by a Windows byte-range lock."""
import errno
import msvcrt
from evolock.paths import DATA_DIR


class InstanceLock:
    def __init__(self, path=None):
        self.path = path if path is not None else DATA_DIR / '.instance.lock'
        self._file = None

    def acquire(self) -> bool:
        if self._file is not None:
            return True
        handle = open(self.path, 'a+b')
        try:
            # Windows permits locking beyond EOF; no write or truncation needed.
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            handle.close()
            if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                return False
            raise
        self._file = handle
        return True

    def release(self):
        if self._file is not None:
            handle, self._file = self._file, None
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                handle.close()


def is_instance_running() -> bool:
    lock = InstanceLock()
    if not lock.acquire():
        return True
    lock.release()
    return False
