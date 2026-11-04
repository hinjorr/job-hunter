"""Local web UI: the job list, a Re-run button, automatic runs every N hours and live progress.

    python -m jobhunter.web            then open http://127.0.0.1:8765
    python -m jobhunter.web --no-browser
"""
import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path

import yaml
from flask import Flask, jsonify, request, send_file

from . import main, scheduler
from .db import DB
from .progress import Progress

ROOT = Path(__file__).resolve().parent.parent
HOST, PORT = "127.0.0.1", 8765

app = Flask(__name__)
P = Progress()
_start_lock = threading.Lock()
SCHED = scheduler.Schedule(ROOT / "schedule.json")


class _ToProgress(logging.Handler):
    def emit(self, record):
        P.log(self.format(record))


def _run():
    try:
        main.run(progress=P)
        P.finish()
    except Exception as e:  # show it in the UI instead of killing the server
        logging.exception("run failed")
        P.finish(error=str(e))


@app.get("/")
def index():
    return send_file(ROOT / "jobhunter" / "ui.html")


@app.get("/api/status")
def status():
    snap = P.snapshot()
    snap["next_run"] = SCHED.next_run()
    snap["schedule"] = SCHED.settings()
    return jsonify(snap)


def _start():
    """Start a run in the background; False if one is already going. Used by Re-run and the schedule."""
    with _start_lock:
        if P.running:
            return False
        P.start()
        SCHED.mark_run()
        threading.Thread(target=_run, daemon=True).start()
    return True


@app.post("/api/run")
def rerun():
    if not _start():
        return jsonify(error="A run is already in progress."), 409
    return jsonify(ok=True)


@app.post("/api/schedule")
def set_schedule():
    body = request.get_json(silent=True) or {}
    try:
        SCHED.update(body.get("enabled"), body.get("every_hours"))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(ok=True, next_run=SCHED.next_run(), schedule=SCHED.settings())


@app.get("/api/jobs")
def jobs():
    cfg = yaml.safe_load(open(ROOT / "config.yaml"))
    db = DB(str(ROOT / "jobs.db"))
    cols = ["url", "source", "title", "company", "score", "reason", "profiles", "first_seen", "posted", "status"]
    rows = db.c.execute(f"SELECT {','.join(cols)} FROM jobs "
                        "ORDER BY score DESC, first_seen DESC").fetchall()
    db.c.close()
    src = cfg["sources"]
    rules = {"min_score": cfg["min_score"], "max_new_per_run": cfg["max_new_per_run"],
             "max_age_days": cfg.get("max_age_days", 30),
             "max_card_scores_per_run": cfg.get("max_card_scores_per_run", 60),
             "keywords": {k: v["keywords"] for k, v in cfg["profiles"].items()},
             "browser": {n: {k: (src.get(f"{n}_options") or {}).get(k) for k in
                             ("max_queries_per_run", "max_jobs_per_query", "max_jobs_per_run")}
                         for n in ("linkedin",) if src.get(n)}}
    return jsonify(min_score=cfg["min_score"], rules=rules, jobs=[dict(zip(cols, r)) for r in rows])


if __name__ == "__main__":
    os.chdir(ROOT)  # the pipeline reads config.yaml, .env and jobs.db from the project folder
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    h = _ToProgress()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
    logging.getLogger().addHandler(h)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)  # keep request noise out of the log
    url = f"http://{HOST}:{PORT}"
    print(f"Job Hunter UI: {url}")
    threading.Thread(target=SCHED.loop, args=(_start, lambda: P.running), daemon=True, name="schedule").start()
    if "--no-browser" not in sys.argv:
        threading.Timer(1.0, webbrowser.open, [url]).start()
    app.run(host=HOST, port=PORT, threaded=True)
