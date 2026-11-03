import logging
import os

import yaml

from .db import DB
from .filtering import match_profiles
from .notify import build_digest, send_telegram
from .scoring import score_job
from .sources import fetch_all


def load_env(path=".env"):
    """Minimal .env loader (KEY=VALUE per line) so local runs need no extra packages."""
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"\''))


def run(config_path="config.yaml", db_path="jobs.db"):
    load_env()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = yaml.safe_load(open(config_path))
    db = DB(db_path)

    new = []
    for j in fetch_all(cfg):
        if db.seen(j.url):
            continue
        j.profiles = match_profiles(j, cfg)
        if j.profiles:
            new.append(j)
        else:
            db.save(j)  # remember irrelevant ones so we skip them next time
    logging.info("%d new relevant postings", len(new))

    good = []
    for j in new[: cfg["max_new_per_run"]]:
        score_job(j, cfg)
        db.save(j)
        if j.score >= cfg["min_score"]:
            good.append(j)

    digest = build_digest(good)
    open("digest.md", "w").write(digest)
    if good:
        send_telegram(digest)
    print(digest)


if __name__ == "__main__":
    run()
