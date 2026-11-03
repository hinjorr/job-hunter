import sqlite3


class DB:
    def __init__(self, path="jobs.db"):
        self.c = sqlite3.connect(path)
        self.c.execute("""CREATE TABLE IF NOT EXISTS jobs (
            url TEXT PRIMARY KEY, source TEXT, title TEXT, company TEXT,
            score INTEGER, reason TEXT, profiles TEXT,
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP)""")

    def seen(self, url) -> bool:
        return self.c.execute("SELECT 1 FROM jobs WHERE url=?", (url,)).fetchone() is not None

    def save(self, j):
        self.c.execute("INSERT OR IGNORE INTO jobs (url,source,title,company,score,reason,profiles) VALUES (?,?,?,?,?,?,?)",
                       (j.url, j.source, j.title, j.company, j.score, j.reason, ",".join(j.profiles)))
        self.c.commit()
