import os
import sqlite3

import jobhunter.main as m
from jobhunter import scoring
from jobhunter.models import Job

CFG = {"candidate_summary": "BC developer", "gemini_model": "test-model"}


class Resp:
    def __init__(self, status, text="", data=None):
        self.status_code, self.text, self._data = status, text, data
        self.ok = 200 <= status < 300

    def json(self):
        return self._data


def test_daily_limit_stops_further_calls(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    calls = []
    monkeypatch.setattr(scoring.requests, "post", lambda *a, **kw: calls.append(1) or Resp(
        429, '{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}'))
    scoring.new_run()
    a, b = Job("x", "BC dev", "A", "u1"), Job("x", "BC dev", "B", "u2")
    assert scoring.score_job(a, CFG) is False and a.reason == scoring.DAILY_LIMIT
    assert scoring.score_job(b, CFG) is False and len(calls) == 1  # second job: no request at all
    scoring.new_run()
    assert not scoring.daily_limit_hit()


def test_real_score_and_unreadable_reply(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    scoring.new_run()
    good = {"candidates": [{"content": {"parts": [{"text": '{"score": 77, "reason": "fit"}'}]}}]}
    monkeypatch.setattr(scoring.requests, "post", lambda *a, **kw: Resp(200, data=good))
    j = Job("x", "BC dev", "A", "u1")
    assert scoring.score_job(j, CFG) is True and (j.score, j.reason) == (77, "fit")
    monkeypatch.setattr(scoring.requests, "post", lambda *a, **kw: Resp(200, data={"candidates": []}))
    assert scoring.score_job(Job("x", "BC dev", "A", "u2"), CFG) is False


def test_unscored_jobs_are_queued_not_guessed(tmp_path, monkeypatch):
    jobs = [Job("remotive", "Business Central Developer", "Acme", "q1", "AL work")]
    cfg_path = os.path.abspath("config.yaml")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(m, "fetch_all", lambda cfg, seen, progress, on_source, **kw: on_source("remotive", jobs))

    def no_gemini(j, cfg):
        j.reason = scoring.DAILY_LIMIT
        return False
    monkeypatch.setattr(m, "score_job", no_gemini)
    sent = []
    monkeypatch.setattr(m, "send_all", sent.append)

    m.run(config_path=cfg_path, db_path=str(tmp_path / "t.db"))
    status, score, reason = sqlite3.connect(tmp_path / "t.db").execute(
        "SELECT status, score, reason FROM jobs WHERE url='q1'").fetchone()
    assert (status, score) == ("queued", 0) and reason.startswith("waiting for Gemini")
    assert sent == []  # nothing guessed, so nothing sent to Discord
