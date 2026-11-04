import json
import logging
import os
import time

import requests

log = logging.getLogger(__name__)

PROMPT = """You screen job postings for a candidate.

Candidate: {candidate}

Posting:
Title: {title}
Company: {company}
Source: {source}
Text: {text}

Rate fit 0-100 (100 = ideal, 0 = irrelevant/not remote-friendly/wrong skills).
Also answer remote_from_pakistan: can someone living in Pakistan do this job without relocating or
regularly going to an office abroad? "yes" (remote and open to Pakistan, or based in Pakistan),
"no" (on-site or hybrid outside Pakistan, or remote but limited to other countries' residents),
or "unclear" (the text doesn't say).
Reply ONLY with JSON: {{"score": <int>, "reason": "<one short sentence>", "remote_from_pakistan": "yes|no|unclear"}}"""

DAILY_LIMIT = "Gemini daily free limit reached"
_daily_limit_hit = False  # set when Google says the per-day quota is used up; cleared each run


def new_run():
    """Call at the start of each run: the daily quota may have reset since the last one."""
    global _daily_limit_hit
    _daily_limit_hit = False


def daily_limit_hit() -> bool:
    return _daily_limit_hit


def keyword_score(job, reason):
    """Keyword-count heuristic, used only when no Gemini key is set at all."""
    job.score = min(100, 50 + 15 * len(job.profiles))
    job.reason = reason
    return job


def _not_scored(job, why):
    job.reason = why
    return False


def score_job(job, cfg) -> bool:
    """Score job with Gemini; True when it got a real score.

    False when Gemini couldn't score it (job.reason says why): the caller queues it for the next
    run rather than inventing a score. Without any key, a keyword score is used and True returned."""
    global _daily_limit_hit
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        keyword_score(job, "keyword match (no GEMINI_API_KEY set)")
        return True
    if _daily_limit_hit:
        return _not_scored(job, DAILY_LIMIT)
    model = cfg.get("gemini_model", "gemini-3.5-flash-lite")
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(
            candidate=cfg["candidate_summary"], title=job.title, company=job.company,
            source=job.source, text=job.description[:3000])}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    last = "Gemini unavailable"
    for attempt in range(3):
        try:
            r = requests.post(url, params={"key": key}, json=body, timeout=60)
        except requests.RequestException as e:
            log.warning("Gemini request failed (%s), retrying", type(e).__name__)
            last = f"Gemini unreachable ({type(e).__name__})"
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 429 and "PerDay" in r.text:
            # Free tier's requests-per-day quota: retrying won't help until it resets.
            _daily_limit_hit = True
            log.warning("%s; remaining jobs this run wait for the next run", DAILY_LIMIT)
            return _not_scored(job, DAILY_LIMIT)
        if r.status_code in (429, 500, 503):  # per-minute rate limit / overloaded: wait and retry
            log.warning("Gemini HTTP %s, retrying", r.status_code)
            last = f"Gemini busy (HTTP {r.status_code})"
            time.sleep(15 * (attempt + 1))
            continue
        if not r.ok:
            # Log status only: the request URL carries the API key.
            log.warning("Gemini HTTP %s for %s: %s", r.status_code, job.url, r.text[:200])
            return _not_scored(job, f"Gemini error {r.status_code}")
        try:
            txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(txt)
            job.score = int(data["score"])
            job.reason = str(data.get("reason", ""))
            job.remote_ok = str(data.get("remote_from_pakistan", "unclear")).strip().lower()
            return True
        except (KeyError, ValueError, IndexError, TypeError) as e:
            log.warning("bad Gemini reply for %s: %s", job.url, e)
            return _not_scored(job, "Gemini gave an unreadable reply")
    log.warning("%s for %s", last, job.url)
    return _not_scored(job, last)
