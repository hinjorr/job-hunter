"""Stage-by-stage run status, shared between the pipeline and the web UI."""
import collections
import threading
import time


class Progress:
    def __init__(self):
        self._lock = threading.Lock()
        self.running = False
        self.started = self.finished = None
        self.started_utc = None
        self.error = None
        self.stages = []
        self.logs = collections.deque(maxlen=200)

    def start(self):
        with self._lock:
            self.running, self.error = True, None
            self.started, self.finished = time.time(), None
            self.started_utc = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(self.started))
            self.stages = []
            self.logs.clear()

    def set_stages(self, stages):
        """stages: list of (key, label), all pending."""
        with self._lock:
            self.stages = [{"key": k, "label": l, "state": "pending", "detail": ""} for k, l in stages]

    def update(self, key, state=None, detail=None):
        with self._lock:
            for s in self.stages:
                if s["key"] == key:
                    if state:
                        s["state"] = state
                    if detail is not None:
                        s["detail"] = detail

    def log(self, line):
        self.logs.append(line)

    def finish(self, error=None):
        with self._lock:
            self.running, self.finished, self.error = False, time.time(), error
            for s in self.stages:
                if s["state"] == "running":
                    s["state"] = "failed" if error else "done"

    def snapshot(self):
        with self._lock:
            return {"running": self.running, "started": self.started, "finished": self.finished,
                    "started_utc": self.started_utc, "error": self.error,
                    "stages": [dict(s) for s in self.stages], "logs": list(self.logs)[-40:]}


class _Null:
    """Progress that ignores everything, for command-line runs."""
    def __getattr__(self, name):
        return lambda *a, **kw: None


NULL = _Null()
