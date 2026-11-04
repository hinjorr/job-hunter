import os
import sqlite3

import jobhunter.main as m
from jobhunter.db import KEYWORD_MISS
from jobhunter.models import Job


def test_every_job_gets_a_status_and_reason(tmp_path, monkeypatch):
    jobs = [
        Job("linkedin", "Business Central Developer", "A", "u1", "AL extensions work"),  # opened posting
        Job("linkedin", "D365 F&O Developer", "B", "u2", status="queued", reason="open limit"),  # card only
        Job("linkedin", "C++ Developer", "C", "u3", status="skipped", reason="title miss"),
        Job("remotive", "Copywriter", "D", "u4", "writing"),
        Job("remotive", "Business Central consultant", "E", "u5", "old one", posted="2000-01-01"),
    ]
    cfg_path = os.path.abspath("config.yaml")
    monkeypatch.chdir(tmp_path)  # digest.md lands here, no .env is loaded
    monkeypatch.setattr(m, "fetch_all", lambda cfg, seen, progress, on_source, **kw: on_source("linkedin", jobs))

    def fake_score(j, cfg):
        j.score, j.reason = 70, "fit"
    monkeypatch.setattr(m, "score_job", fake_score)

    m.run(config_path=cfg_path, db_path=str(tmp_path / "t.db"))
    rows = {r[0]: r[1:] for r in sqlite3.connect(tmp_path / "t.db").execute("SELECT url, status, reason FROM jobs")}
    assert rows["u1"] == ("scored", "fit")
    assert rows["u2"][0] == "prelim" and rows["u2"][1].startswith("PRELIMINARY")
    assert rows["u3"] == ("skipped", "title miss")
    assert rows["u4"] == ("skipped", KEYWORD_MISS)
    assert rows["u5"][0] == "skipped" and "older than" in rows["u5"][1]
