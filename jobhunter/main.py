import collections
import datetime
import logging
import os

import yaml

from .db import DB, KEYWORD_MISS
from .filtering import match_profiles
from .notify import build_digest, send_telegram
from .progress import NULL
from .scoring import score_job
from .sources import LABELS, enabled, fetch_all


def load_env(path=".env"):
    """Minimal .env loader (KEY=VALUE per line) so local runs need no extra packages."""
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"\''))


def run(config_path="config.yaml", db_path="jobs.db", progress=NULL):
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = yaml.safe_load(open(config_path))
    db = DB(db_path)
    progress.set_stages([(f"fetch:{n}", f"Fetch: {LABELS.get(n, n)}") for n in enabled(cfg)] + [
        ("filter", "Filter: already seen, age, keywords"),
        ("score", "Score with Gemini"),
        ("digest", "Write digest")])

    max_age, min_score = cfg.get("max_age_days", 30), cfg["min_score"]
    full_cap, card_cap = cfg["max_new_per_run"], cfg.get("max_card_scores_per_run", 60)
    oldest = (datetime.date.today() - datetime.timedelta(days=max_age)).isoformat()
    counts, good = collections.Counter(), []

    def score(j, status):
        score_job(j, cfg)
        j.status = status
        counts[status] += 1
        if j.score >= min_score:
            good.append(j)
        progress.update("score", "running", f"{counts['scored']} scored, {counts['prelim']} preliminary, "
                                            f"{len(good)} at {min_score}+")

    def handle(name, jobs):
        """Filter, save and score one source's jobs as soon as it's fetched, so the UI fills in during the run.
        Every job is saved with a status and reason, so it's clear why each was or wasn't scored."""
        progress.update("filter", "running")
        for j in jobs:
            if db.seen(j.url):
                counts["already seen"] += 1
                continue
            if j.status == "queued" and not j.description and match_profiles(j, cfg):
                # A matching card a browser source didn't open: score what the card shows.
                if counts["prelim"] < card_cap:
                    note = j.reason
                    j.description = "(Only the job card was read: title, company, location. No description.)"
                    score(j, "prelim")
                    j.description = ""
                    j.reason = f"PRELIMINARY, from the listing only ({note}). Gemini: {j.reason}"
                else:
                    j.reason += f"; over the card-scoring limit ({card_cap}, max_card_scores_per_run)"
                    counts["queued"] += 1
            elif j.status:  # a browser source already decided (cards it didn't open)
                counts[j.status] += 1
            elif j.posted and j.posted < oldest:
                j.status, j.reason = "skipped", f"posted {j.posted}, older than {max_age} days (max_age_days)"
                counts["skipped"] += 1
            else:
                j.profiles = match_profiles(j, cfg)
                if not j.profiles:
                    j.status, j.reason = "skipped", KEYWORD_MISS
                    counts["skipped"] += 1
                elif counts["scored"] < full_cap:
                    score(j, "scored")
                else:
                    j.status, j.reason = "queued", (f"not scored yet: over the Gemini limit of {full_cap} per run "
                                                    "(max_new_per_run); scored next run")
                    counts["queued"] += 1
            db.save(j)
        progress.update("filter", detail=f"{counts['skipped']} skipped, {counts['queued']} queued, "
                                         f"{counts['already seen']} already seen (after {LABELS.get(name, name)})")

    fetch_all(cfg, seen=db.seen, progress=progress, on_source=handle, pending=db.pending)
    logging.info("run counts: %s", dict(counts))
    progress.update("filter", "done", f"{counts['skipped']} skipped, {counts['queued']} queued, "
                                      f"{counts['already seen']} already seen")
    progress.update("score", "done", f"{counts['scored']} scored, {counts['prelim']} preliminary (card only), "
                                     f"{len(good)} at {min_score}+")

    progress.update("digest", "running")
    digest = build_digest(good)
    open("digest.md", "w", encoding="utf-8").write(digest)
    if good:
        send_telegram(digest)
    progress.update("digest", "done", "digest.md written")
    print(digest)


if __name__ == "__main__":
    run()
