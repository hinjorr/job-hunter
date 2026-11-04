"""Automatic runs, set from the web page: start a hunt every N hours.

Settings live in schedule.json next to jobs.db (written by the page, not edited by hand):
    {"enabled": true, "every_hours": 6, "last_run": <epoch seconds of the last run's start>}

The next run is due `every_hours` after the last run started, whether that run was automatic or
the Re-run button. When the server starts (e.g. after Windows boots) and a run is overdue, it
waits STARTUP_DELAY first so the network is up, then runs; otherwise it waits for the normal time.
"""
import json
import logging
import threading
import time

log = logging.getLogger(__name__)

CHOICES = (3, 4, 5, 6, 8, 12, 24)  # hours offered in the page
DEFAULTS = {"enabled": True, "every_hours": 6, "last_run": None}
STARTUP_DELAY = 120  # seconds after the server starts before an overdue run begins


class Schedule:
    def __init__(self, path, now=None):
        self.path = path
        self._lock = threading.Lock()
        self.data = self._load()
        self.not_before = (now if now is not None else time.time()) + STARTUP_DELAY

    def _load(self):
        data = dict(DEFAULTS)
        try:
            with open(self.path, encoding="utf-8") as f:
                data.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
        except FileNotFoundError:
            pass
        except Exception as e:
            log.warning("schedule: couldn't read %s (%s); using defaults", self.path, e)
        if data["every_hours"] not in CHOICES:
            data["every_hours"] = DEFAULTS["every_hours"]
        data["enabled"] = bool(data["enabled"])
        return data

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def settings(self):
        with self._lock:
            return {"enabled": self.data["enabled"], "every_hours": self.data["every_hours"],
                    "choices": list(CHOICES)}

    def update(self, enabled, every_hours):
        if every_hours not in CHOICES or not isinstance(enabled, bool):
            raise ValueError(f"every_hours must be one of {CHOICES} and enabled true/false")
        with self._lock:
            self.data.update(enabled=enabled, every_hours=every_hours)
            self._save()

    def mark_run(self, when=None):
        """Call when any run starts, so the next automatic one is counted from it."""
        with self._lock:
            self.data["last_run"] = when if when is not None else time.time()
            self._save()

    def next_run(self, now=None):
        """Epoch seconds of the next automatic run, or None when automatic runs are off."""
        now = now if now is not None else time.time()
        with self._lock:
            if not self.data["enabled"]:
                return None
            last = self.data["last_run"]
            due = last + self.data["every_hours"] * 3600 if last else now
        return max(due, self.not_before)

    def loop(self, start_run, is_running, check_every=20):
        """Forever: start a run when one is due. start_run() must call mark_run()."""
        while True:
            now = time.time()
            nxt = self.next_run(now)
            if nxt is not None and now >= nxt and not is_running():
                log.info("schedule: starting the automatic run (every %s hours)", self.data["every_hours"])
                start_run()
            time.sleep(check_every)
