import re
import sqlite3

KEYWORD_MISS = "no Business Central / F&O / Dynamics keyword in title or description"
REPEAT = "REPEAT"  # reason prefix for jobs that copied the score of an identical posting


def _norm(s):
    return " ".join(re.sub(r"[^a-z0-9+#&]+", " ", (s or "").lower()).split())


def job_key(title, company):
    """Same job = same title at the same company, ignoring case, punctuation and location
    (company is stored as "Company · Location"). None when either part is missing."""
    t, c = _norm(title), _norm((company or "").split(" · ")[0])
    return (t, c) if t and c else None


class DB:
    """Every job the hunter has looked at, with a status:
    scored  - Gemini scored it (reason = Gemini's reason)
    skipped - ruled out without scoring (reason says why)
    queued  - not processed yet (reason says why); picked up again next time it's fetched
    prelim  - scored from the search-result card only (not opened yet); opened and re-scored when picked
    """

    def __init__(self, path="jobs.db"):
        self.c = sqlite3.connect(path)
        self.c.execute("""CREATE TABLE IF NOT EXISTS jobs (
            url TEXT PRIMARY KEY, source TEXT, title TEXT, company TEXT,
            score INTEGER, reason TEXT, profiles TEXT,
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP, posted TEXT, status TEXT)""")
        for col in ("posted", "status"):  # databases created before these columns existed
            try:
                self.c.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass
        self.c.execute("UPDATE jobs SET status='scored' WHERE status IS NULL AND profiles != ''")
        self.c.execute("UPDATE jobs SET status='skipped', reason=? WHERE status IS NULL", (KEYWORD_MISS,))
        self.c.commit()
        self._twins = None  # job_key -> fully scored row, rebuilt after each save

    def scored_twin(self, title, company):
        """An already fully-read job with the same title and company, as a dict, or None."""
        key = job_key(title, company)
        if not key:
            return None
        if self._twins is None:
            self._twins = {}
            cur = self.c.execute("SELECT url, title, company, score, reason, profiles FROM jobs "
                                 "WHERE status='scored' ORDER BY first_seen")
            for url, t, c, score, reason, profiles in cur:
                k = job_key(t, c)
                if k and k not in self._twins:
                    self._twins[k] = {"url": url, "score": score, "reason": reason or "", "profiles": profiles or ""}
        return self._twins.get(key)

    def copy_twin(self, j) -> bool:
        """If job j repeats one already read, give it that job's score and say so. True if it did."""
        twin = self.scored_twin(j.title, j.company)
        if not twin:
            return False
        reason = twin["reason"]
        j.score, j.status = twin["score"], "scored"
        j.profiles = [p for p in twin["profiles"].split(",") if p]
        j.reason = reason if reason.startswith(REPEAT) else (
            f"{REPEAT}: same title and company as a job already read, so not opened or scored again "
            f"(score copied). Gemini: {reason}")
        return True

    def seen(self, url) -> bool:
        """True once a job is decided (scored or skipped); queued and prelim jobs get another go."""
        return self.c.execute("SELECT 1 FROM jobs WHERE url=? AND status NOT IN ('queued', 'prelim')",
                              (url,)).fetchone() is not None

    def pending(self, source) -> list:
        """Jobs from source not fully processed yet (queued, or scored from the card only), oldest first."""
        cur = self.c.execute("SELECT url, title, company, posted FROM jobs WHERE source=? "
                             "AND status IN ('queued', 'prelim') ORDER BY first_seen", (source,))
        return [dict(zip(("url", "title", "company", "posted"), r)) for r in cur]

    def save(self, j):
        self.c.execute("""INSERT INTO jobs (url,source,title,company,score,reason,profiles,posted,status)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(url) DO UPDATE SET source=excluded.source, title=excluded.title,
                company=excluded.company, score=excluded.score, reason=excluded.reason,
                profiles=excluded.profiles, posted=excluded.posted, status=excluded.status""",
                       (j.url, j.source, j.title, j.company, j.score, j.reason, ",".join(j.profiles),
                        j.posted, j.status))
        self.c.commit()
        if j.status == "scored":
            self._twins = None
