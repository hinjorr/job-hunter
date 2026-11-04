import os
import sqlite3

import jobhunter.main as m
from jobhunter.models import Job
from jobhunter.workplace import NOT_REMOTE, onsite_elsewhere


def J(title, company, desc):
    return Job("x", title, company, "u", desc)


def test_text_check_only_catches_clear_cases():
    assert onsite_elsewhere(J("BC Developer", "Zensar · Pune, India", "This is an on-site role in Pune.")) == "on-site"
    assert onsite_elsewhere(J("BC Developer", "A · London", "Hybrid: 3 days in our office.")) == "Hybrid"
    assert onsite_elsewhere(J("BC Developer", "A · London", "Hybrid or fully remote.")) is None   # remote mentioned
    assert onsite_elsewhere(J("BC Developer", "A · Karachi, Pakistan", "On-site in Karachi.")) is None  # Pakistan
    assert onsite_elsewhere(J("BC Developer", "A · Pune, India", "AL extensions, upgrades.")) is None  # says nothing
    assert onsite_elsewhere(J("BC Developer", "A · Pune, India", "")) is None  # card only


def test_pipeline_skips_not_remote_jobs(tmp_path, monkeypatch):
    jobs = [
        Job("remotive", "Business Central Developer", "Zensar · Pune, India", "w1", "Work from office in Pune."),
        Job("remotive", "Business Central Developer", "Acme", "w2", "AL work, location flexible"),
        Job("remotive", "Business Central Developer", "Good Co", "w3", "Fully remote, worldwide."),
        Job("remotive", "Business Central Developer", "Zensar · Mumbai, India", "w4", "Same role, other city."),
    ]
    cfg_path = os.path.abspath("config.yaml")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(m, "fetch_all", lambda cfg, seen, progress, on_source, **kw: on_source("remotive", jobs))
    asked = []

    def fake_score(j, cfg):
        asked.append(j.url)
        j.score, j.reason = 85, "fit"
        j.remote_ok = "no" if j.url == "w2" else "yes"  # Gemini read w2: US residents only, say
        return True
    monkeypatch.setattr(m, "score_job", fake_score)
    sent = []
    monkeypatch.setattr(m, "send_all", sent.append)

    m.run(config_path=cfg_path, db_path=str(tmp_path / "t.db"))
    rows = {r[0]: r[1:] for r in sqlite3.connect(tmp_path / "t.db").execute("SELECT url, status, reason FROM jobs")}
    assert asked == ["w2", "w3"]  # w1 caught by the text check, w4 is a repeat of w1: no Gemini for either
    assert rows["w1"][0] == "skipped" and rows["w1"][1].startswith(NOT_REMOTE)
    assert rows["w2"][0] == "skipped" and rows["w2"][1].startswith(NOT_REMOTE) and "Gemini" in rows["w2"][1]
    assert rows["w3"][0] == "scored"
    assert rows["w4"][0] == "skipped" and rows["w4"][1].startswith("REPEAT")
    assert "w3" in sent[0] and "w1" not in sent[0] and "w2" not in sent[0]
