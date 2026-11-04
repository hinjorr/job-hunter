import sqlite3

KEYWORD_MISS = "no Business Central / F&O / Dynamics keyword in title or description"


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
