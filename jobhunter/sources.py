"""Job sources. Each fetcher returns list[Job] and never raises (errors are logged)."""
import html
import logging
import re

import feedparser
import requests

from .models import Job

log = logging.getLogger(__name__)
UA = {"User-Agent": "job-hunter/0.1 (personal job search tool)"}
TIMEOUT = 30


def _strip(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _safe(fn):
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as e:  # one broken source must not kill the run
            log.warning("source %s failed: %s", fn.__name__, e)
            return []
    wrapper.__name__ = fn.__name__
    return wrapper


@_safe
def remoteok(cfg):
    data = requests.get("https://remoteok.com/api", headers=UA, timeout=TIMEOUT).json()
    return [
        Job("remoteok", j.get("position", ""), j.get("company", ""), j.get("url", ""),
            _strip(j.get("description", "")))
        for j in data if isinstance(j, dict) and j.get("position")
    ]


@_safe
def weworkremotely(cfg):
    out = []
    for feed in ("remote-programming-jobs", "remote-devops-sysadmin-jobs", "remote-full-stack-programming-jobs"):
        d = feedparser.parse(f"https://weworkremotely.com/categories/{feed}.rss", request_headers=UA)
        for e in d.entries:
            company, _, title = e.title.partition(": ")
            out.append(Job("weworkremotely", title or e.title, company if title else "", e.link,
                           _strip(e.get("summary", ""))))
    return out


@_safe
def remotive(cfg):
    out = []
    for term in ("net", "dynamics", "business central", "ai", "finops", "erp"):
        r = requests.get("https://remotive.com/api/remote-jobs", params={"search": term},
                         headers=UA, timeout=TIMEOUT).json()
        for j in r.get("jobs", []):
            out.append(Job("remotive", j["title"], j["company_name"], j["url"],
                           _strip(j.get("description", ""))))
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
        out.append(Job("hn_hiring", text[:120], first, f"https://news.ycombinator.com/item?id={c['objectID']}", text))
    return out


@_safe
def reddit(cfg):
    out = []
    for url in cfg["sources"].get("reddit_feeds", []):
        d = feedparser.parse(url, request_headers=UA)
        for e in d.entries:
            out.append(Job("reddit", e.title, e.get("author", ""), e.link, _strip(e.get("summary", ""))))
    return out


REGISTRY = {
    "remoteok": remoteok,
    "weworkremotely": weworkremotely,
    "remotive": remotive,
    "hn_hiring": hn_hiring,
    "reddit": reddit,
}


def fetch_all(cfg) -> list:
    jobs = []
    for name, fn in REGISTRY.items():
        if cfg["sources"].get(name):
            got = fn(cfg)
            log.info("%s: %d postings", name, len(got))
            jobs.extend(got)
    return [j for j in jobs if j.url]
