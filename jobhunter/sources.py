"""Job sources. Each fetcher returns list[Job] and never raises (errors are logged)."""
import html
import logging
import re
import time

import feedparser
import requests

from .models import Job
from .progress import NULL

log = logging.getLogger(__name__)
UA = {"User-Agent": "job-hunter/0.1 (personal job search tool)"}
TIMEOUT = 30
ERRORS = {}  # source name -> what went wrong in this run, for the progress view
LABELS = {"remoteok": "RemoteOK", "weworkremotely": "We Work Remotely", "remotive": "Remotive",
          "hn_hiring": "HN Who's hiring", "reddit": "Reddit", "linkedin": "LinkedIn (Chrome)"}


def _strip(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _day(entry) -> str:
    """YYYY-MM-DD from a feed entry's published/updated time, or ""."""
    st = entry.get("published_parsed") or entry.get("updated_parsed")
    return time.strftime("%Y-%m-%d", st) if st else ""


def _feed(url):
    """Download with requests so a failed fetch raises (feedparser alone returns 0 entries silently)."""
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return feedparser.parse(r.content)


def _safe(fn):
    def wrapper(*a, **kw):
        try:
            try:
                return fn(*a, **kw)
            except requests.ConnectionError as e:
                # Often a flaky DNS lookup; one retry after a pause usually gets through.
                log.info("source %s: network error (%s), retrying in 15s", fn.__name__, e.__class__.__name__)
                time.sleep(15)
                return fn(*a, **kw)
        except Exception as e:  # one broken source must not kill the run
            log.warning("source %s failed: %s", fn.__name__, e)
            ERRORS[fn.__name__] = str(e)
            return []
    wrapper.__name__ = fn.__name__
    return wrapper


@_safe
def remoteok(cfg):
    data = requests.get("https://remoteok.com/api", headers=UA, timeout=TIMEOUT).json()
    return [
        Job("remoteok", j.get("position", ""), j.get("company", ""), j.get("url", ""),
            _strip(j.get("description", "")), posted=(j.get("date") or "")[:10])
        for j in data if isinstance(j, dict) and j.get("position")
    ]


@_safe
def weworkremotely(cfg):
    out = []
    for feed in ("remote-programming-jobs", "remote-devops-sysadmin-jobs", "remote-full-stack-programming-jobs"):
        d = _feed(f"https://weworkremotely.com/categories/{feed}.rss")
        for e in d.entries:
            company, _, title = e.title.partition(": ")
            out.append(Job("weworkremotely", title or e.title, company if title else "", e.link,
                           _strip(e.get("summary", "")), posted=_day(e)))
    return out


@_safe
def remotive(cfg):
    out = []
    for term in cfg["sources"].get("remotive_terms", ["business central", "dynamics 365", "erp"]):
        r = requests.get("https://remotive.com/api/remote-jobs", params={"search": term},
                         headers=UA, timeout=TIMEOUT).json()
        for j in r.get("jobs", []):
            out.append(Job("remotive", j["title"], j["company_name"], j["url"],
                           _strip(j.get("description", "")), posted=(j.get("publication_date") or "")[:10]))
    return out


@_safe
def hn_hiring(cfg):
    base = "https://hn.algolia.com/api/v1"
    story = requests.get(f"{base}/search_by_date", params={
        "query": "Ask HN: Who is hiring?", "tags": "story,author_whoishiring", "hitsPerPage": 1},
        headers=UA, timeout=TIMEOUT).json()["hits"][0]
    out = []
    comments = requests.get(f"{base}/search", params={
        "tags": f"comment,story_{story['objectID']}", "hitsPerPage": 500},
        headers=UA, timeout=TIMEOUT).json()["hits"]
    for c in comments:
        text = _strip(c.get("comment_text", ""))
        if not text:
            continue
        first = text.split("|")[0].strip()[:80]
        out.append(Job("hn_hiring", text[:120], first, f"https://news.ycombinator.com/item?id={c['objectID']}", text,
                       posted=(c.get("created_at") or "")[:10]))
    return out


@_safe
def reddit(cfg):
    out, failed = [], []
    for i, url in enumerate(cfg["sources"].get("reddit_feeds", [])):
        if i:
            time.sleep(3)  # Reddit answers 429 to quick back-to-back requests
        try:
            d = _feed(url)
        except Exception as e:  # one bad feed shouldn't drop the others
            failed.append(re.sub(r"\?.*", "", url.split("/r/")[-1]) + f" ({e.__class__.__name__})")
            continue
        for e in d.entries:
            out.append(Job("reddit", e.title, e.get("author", ""), e.link, _strip(e.get("summary", "")),
                           posted=_day(e)))
    if failed:
        ERRORS["reddit"] = "feeds failed: " + ", ".join(failed)
    return out


@_safe
def linkedin(cfg, seen=None, on_step=None, revisit=None, known=None):
    from . import linkedin as li  # imported lazily: needs Playwright and Chrome
    jobs = li.search(cfg, seen, on_step, revisit, known)
    if li.last_block:
        ERRORS["linkedin"] = (li.last_block if li.last_block.startswith("stopped early")
                              else "stopped at a sign-in wall/CAPTCHA (not bypassed); screenshot in blocked/")
    return jobs



REGISTRY = {
    "remoteok": remoteok,
    "weworkremotely": weworkremotely,
    "remotive": remotive,
    "hn_hiring": hn_hiring,
    "reddit": reddit,
    "linkedin": linkedin,
}
BROWSER = {"linkedin"}  # get the seen-check and step reporting


def enabled(cfg) -> list:
    return [n for n in REGISTRY if cfg["sources"].get(n)]


def fetch_all(cfg, seen=None, progress=NULL, on_source=None, pending=None, known=None) -> list:
    """Fetch every enabled source in turn; on_source(name, jobs) runs right after each one.
    pending(source) lists that source's jobs left queued/preliminary earlier, for browser sources to revisit.
    known(title, company) is True when a job with that title and company was already read (not reopened)."""
    jobs = []
    for name in enabled(cfg):
        key = f"fetch:{name}"
        progress.update(key, "running")
        if name in BROWSER:
            # Browser sources get the seen-check so they don't click postings already known.
            got = REGISTRY[name](cfg, seen, lambda d, k=key: progress.update(k, detail=d),
                                 pending(name) if pending else None, known)
        else:
            got = REGISTRY[name](cfg)
        log.info("%s: %d postings", name, len(got))
        err = ERRORS.pop(name, None)
        if err:
            progress.update(key, "warn" if got else "failed", f"{len(got)} postings; {err[:160]}")
        else:
            progress.update(key, "done", f"{len(got)} postings")
        got = [j for j in got if j.url]
        if on_source:
            on_source(name, got)
        jobs.extend(got)
    return [j for j in jobs if j.url]
