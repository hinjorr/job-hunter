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
Reply ONLY with JSON: {{"score": <int>, "reason": "<one short sentence>"}}"""


def score_job(job, cfg):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        # No key: fall back to a keyword-count heuristic so the pipeline still works.
        job.score = min(100, 50 + 15 * len(job.profiles))
        job.reason = "keyword match (no GEMINI_API_KEY set)"
        return job
    model = cfg.get("gemini_model", "gemini-2.5-flash")
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(
            candidate=cfg["candidate_summary"], title=job.title, company=job.company,
            source=job.source, text=job.description[:3000])}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for attempt in range(3):
        r = requests.post(url, params={"key": key}, json=body, timeout=60)
        if r.status_code == 429:  # free-tier rate limit
            time.sleep(15 * (attempt + 1))
            continue
        r.raise_for_status()
        try:
            txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(txt)
            job.score = int(data["score"])
            job.reason = str(data.get("reason", ""))
        except (KeyError, ValueError, IndexError) as e:
            log.warning("bad Gemini reply for %s: %s", job.url, e)
        return job
    log.warning("Gemini rate-limited, skipping %s", job.url)
    return job
