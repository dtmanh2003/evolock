import math
import threading
import time


class CountdownTimer:
    def __init__(self, seconds: int, on_tick=None, on_done=None, dispatch=None):
        self.total = seconds
        self.remaining = seconds
        self.on_tick = on_tick
        self.on_done = on_done
        self.dispatch = dispatch or (lambda callback: callback())
        self._thread = None
        self.running = False
        self._lock = threading.Lock()
        self._cancel = threading.Event()

    def start(self):
        with self._lock:
            if self.running:
                return
            self._cancel.set()
            event = self._cancel = threading.Event()
            self.remaining = self.total
            self.running = True
            deadline = time.monotonic() + self.total
            self._thread = threading.Thread(target=self._loop, args=(event, deadline), daemon=True)
            self._thread.start()

    def stop(self):
        with self._lock:
            self.running = False
            self._cancel.set()

    def _emit(self, event, callback, *args):
        if callback is None:
            return
        def deliver():
            if not event.is_set():
                callback(*args)
        self.dispatch(deliver)

    def _loop(self, event, deadline):
        while not event.is_set():
            remaining = max(0, math.ceil(deadline - time.monotonic()))
            with self._lock:
                if event.is_set():
                    return
                self.remaining = remaining
                if remaining == 0:
                    self.running = False
            self._emit(event, self.on_tick, remaining)
            if remaining == 0:
                self._emit(event, self.on_done)
                return
            event.wait(max(0.001, min(1.0, deadline - time.monotonic())))


def fmt_time(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f'{m:02d}:{s:02d}'
