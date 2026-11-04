"""LinkedIn job search through a real Chrome window, logged out, with person-like pacing.

Runs every configured search, loads every results page, and opens every posting whose title
matches a profile keyword (limits in config; 0 = no limit). Postings left queued or only
card-scored by earlier runs are revisited directly by URL. Random pauses (scaled by `pace`),
mouse movement and scrolling throughout. Any checkpoint or real CAPTCHA stops LinkedIn for
the rest of the run; it is never bypassed.

Runs logged out by default. To search signed in, run once:
    python -m jobhunter.linkedin --login
and sign in by hand in the window that opens; the session is kept in `profile_dir`.
Quick test of one search:
    python -m jobhunter.linkedin --test
"""
import logging
import os
import random
import re
import sys
import time
from urllib.parse import quote_plus

from .filtering import match_profiles
from .models import Job

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.linkedin.com/jobs/search/?keywords={q}&location={loc}&f_TPR=r{secs}&sortBy=DD"
BLOCK_MARKERS = ("checkpoint", "authwall", "/login", "/uas/", "captcha", "challenge")
TITLE_SEL = [".job-details-jobs-unified-top-card__job-title", ".jobs-unified-top-card__job-title",
             ".top-card-layout__title", ".topcard__title"]
COMPANY_SEL = [".job-details-jobs-unified-top-card__company-name", ".jobs-unified-top-card__company-name",
               ".topcard__org-name-link", ".topcard__flavor"]
DESC_SEL = [".jobs-description__content", "#job-details", ".jobs-box__html-content",
            ".show-more-less-html__markup", ".description__text"]
DISMISS_SEL = ["button.modal__dismiss", ".contextual-sign-in-modal__modal-dismiss",
               "button[aria-label='Dismiss']", "button[data-tracking-control-name*='modal_dismiss']"]
DEFAULTS = {
    "profile_dir": ".linkedin-profile",
    "queries": ["Business Central developer"],
    "location": "Worldwide",
    "remote_only": True,
    "posted_within_hours": 24,
    "max_queries_per_run": 0,     # 0 = all queries
    "max_jobs_per_query": 0,      # 0 = no limit
    "max_jobs_per_run": 0,        # 0 = no limit
    "max_cards_per_search": 300,  # stop loading more result pages after this many cards
    "revisit_pending": True,      # reopen jobs left queued/preliminary by earlier runs
    "pace": 0.5,                  # multiplies every pause; 1.0 = slow and person-like
    "headless": False,
}
PACE = 1.0  # set from opts["pace"] at the start of search()


def _limit(v):
    return v if v else 10 ** 9  # 0 / None mean "no limit"


class Blocked(Exception):
    """LinkedIn showed a checkpoint, CAPTCHA or sign-in wall."""


def pause(lo, hi):
    t = random.uniform(lo, hi)
    if random.random() < 0.1:  # now and then, get "distracted"
        t += random.uniform(8, 25)
    time.sleep(t * PACE)


def snap(page, site):
    """Save a screenshot of what stopped us to blocked/, so we can see it rather than guess."""
    try:
        os.makedirs("blocked", exist_ok=True)
        path = f"blocked/{site}-{time.strftime('%Y%m%d-%H%M%S')}.png"
        page.screenshot(path=path, full_page=False)
        log.info("saved screenshot of the block: %s", path)
    except Exception as e:
        log.info("could not save block screenshot: %s", e)


def check_blocked(page):
    if any(m in page.url.lower() for m in BLOCK_MARKERS):
        snap(page, "linkedin")
        raise Blocked(page.url)
    # Job pages carry Google's invisible reCAPTCHA: a small "protected by reCAPTCHA" badge
    # (~256x60, src has size=invisible) that asks nothing. Only a real, visible challenge counts.
    for el in page.locator("iframe[src*='captcha'], #captcha-internal, form#challenge").all():
        if not el.is_visible():
            continue
        what = el.get_attribute("src") or el.get_attribute("id") or "form"
        box = el.bounding_box() or {}
        if "size=invisible" in what or box.get("height", 0) < 120:
            continue
        snap(page, "linkedin")
        raise Blocked(f"captcha element {what[:80]} ({int(box.get('width', 0))}x{int(box.get('height', 0))}px) "
                      f"on {page.url.split('?')[0]}")


def hover(page, el):
    """Move the mouse to a random point inside el along a multi-step path; return that point."""
    el.scroll_into_view_if_needed(timeout=5000)
    box = el.bounding_box()
    if not box:
        return None
    x = box["x"] + box["width"] * random.uniform(0.2, 0.8)
    y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
    page.mouse.move(x, y, steps=random.randint(12, 35))
    return x, y


def click(page, el):
    pt = hover(page, el)
    if not pt:
        return False
    pause(0.2, 0.9)
    page.mouse.click(*pt, delay=random.randint(40, 140))
    return True


def dismiss_signin(page):
    """Close LinkedIn's "Sign in to view more" pop-up with its X, as a person would."""
    for sel in DISMISS_SEL:
        for el in page.locator(sel).all():
            if el.is_visible():
                pause(0.8, 2.5)  # notice the pop-up before closing it
                click(page, el)
                pause(0.5, 1.5)
                log.info("closed sign-in pop-up on %s", page.url.split("?")[0])
                return True
    return False


def read_scroll(page, steps=(2, 6)):
    """Scroll down unevenly where the mouse is, sometimes scrolling back up to re-read."""
    for _ in range(random.randint(*steps)):
        page.mouse.wheel(0, random.randint(250, 700))
        pause(0.6, 2.2)
        if random.random() < 0.15:
            page.mouse.wheel(0, -random.randint(100, 300))
            pause(0.5, 1.5)


def first_text(page, selectors):
    for sel in selectors:
        el = page.locator(sel).first
        if el.count():
            txt = el.inner_text(timeout=5000).strip()
            if txt:
                return txt
    return ""


def card_info(a, title):
    """Company, location and posted date from the result card around link a (best effort)."""
    try:
        box = a.locator("xpath=ancestor::li[1]")
        box = box.first if box.count() else a.locator("xpath=..").first
        lines = [l.strip() for l in box.inner_text(timeout=3000).split("\n") if l.strip() and l.strip() != title]
        t = box.locator("time[datetime]")
        posted = (t.first.get_attribute("datetime") or "")[:10] if t.count() else ""
    except Exception:
        lines, posted = [], ""
    return {"title": title, "company": lines[0] if lines else "",
            "location": lines[1] if len(lines) > 1 else "", "posted": posted}


def card_job(site, url, c, status, reason):
    """A Job for a result card that wasn't opened, so it still shows in the list with why."""
    company = f"{c['company']} · {c['location']}" if c["location"] else c["company"]
    return Job(site, c["title"], company, url, posted=c["posted"], status=status, reason=reason)


def collect_cards(page):
    """Map job id -> card info (title, company, location, posted) for every job on the results page."""
    cards = {}
    for a in page.locator('a[href*="/jobs/view/"]').all():
        m = re.search(r"/jobs/view/(?:[^/?]*-)?(\d{6,})", a.get_attribute("href") or "")
        title = (a.inner_text() or "").strip().split("\n")[0].strip()
        if m and title and m.group(1) not in cards:
            cards[m.group(1)] = card_info(a, title)
    return cards


def job_url(jid):
    return f"https://www.linkedin.com/jobs/view/{jid}/"


def load_all_results(page, max_cards, on_more=None):
    """Scroll the results list to the end, pressing "See more jobs" when it appears, until no new cards load."""
    links = page.locator('a[href*="/jobs/view/"]')
    stalled = 0
    while links.count() < max_cards and stalled < 2:
        before = links.count()
        page.mouse.wheel(0, random.randint(2500, 4000))
        pause(1.5, 3)
        more = page.locator("button.infinite-scroller__show-more-button, button:has-text('See more jobs')").first
        if more.count() and more.is_visible():
            dismiss_signin(page)
            click(page, more)
            pause(2, 4)
        stalled = stalled + 1 if links.count() == before else 0
        if on_more:
            on_more(links.count())


def read_posting(target, jid, card):
    """Read an open job page; return a scored-ready Job, or a queued one if the description didn't load."""
    target.wait_for_load_state("domcontentloaded", timeout=15000)
    check_blocked(target)
    pause(1, 2.5)  # the pop-up appears a moment after load
    dismiss_signin(target)
    try:
        target.wait_for_selector(", ".join(DESC_SEL), timeout=10000)
    except Exception:
        dismiss_signin(target)  # a late pop-up may be covering it
    desc = first_text(target, DESC_SEL)
    company = first_text(target, COMPANY_SEL) or card["company"]
    title = first_text(target, TITLE_SEL) or card["title"]
    # Reading time grows with the posting's length.
    if desc:
        d = target.locator(DESC_SEL[0]).first
        if d.count():
            hover(target, d)
        read_scroll(target, (1, 4))
    base = min(3 + len(desc) / 1500, 12)
    pause(base * 0.6, base * 1.3)
    if not desc:
        log.info("linkedin %s: no description loaded, queued for next run", jid)
        return card_job("linkedin", job_url(jid), card, "queued", "opened, but the description didn't load; retried next run")
    company = company.split("\n")[0]
    if card["location"] and card["location"] not in company:
        company = f"{company} · {card['location']}"
    return Job("linkedin", title, company, job_url(jid), desc, posted=card["posted"])


def open_job(page, ctx, jid, card):
    """Click a job card like a person would and read the posting."""
    dismiss_signin(page)  # the pop-up can come back on the results page and swallow the click
    el = page.locator(f'a[href*="/jobs/view/"][href*="{jid}"]').first
    before = len(ctx.pages)
    if not el.count() or not click(page, el):
        return card_job("linkedin", job_url(jid), card, "queued", "couldn't click the card; retried next run")
    pause(2, 4)
    target = ctx.pages[-1] if len(ctx.pages) > before else page  # card may open a new tab
    try:
        return read_posting(target, jid, card)
    finally:
        if target is not page:
            target.close()
            pause(1, 3)
        elif "/jobs/view/" in page.url:
            page.go_back(wait_until="domcontentloaded")
            pause(2, 5)


def _opts(cfg):
    return {**DEFAULTS, **(cfg["sources"].get("linkedin_options") or {})}


def _launch(pw, opts):
    return pw.chromium.launch_persistent_context(
        opts["profile_dir"], channel="chrome", headless=opts["headless"], no_viewport=True,
        chromium_sandbox=True)  # Playwright turns the sandbox off by default; keep Chrome's protection on


last_block = None  # why the last search() stopped early, if it did


def search(cfg, seen=None, on_step=None, revisit=None):
    """Run the configured searches; return list[Job]. Stops LinkedIn for the run on any block.

    on_step(text) is called with a short description of what it's doing, for the progress view.
    revisit: earlier jobs left queued/preliminary, as dicts (url, title, company, posted); reopened by URL."""
    from playwright.sync_api import sync_playwright

    global last_block, PACE
    last_block = None
    step = on_step or (lambda text: None)
    opts, seen = _opts(cfg), seen or (lambda url: False)
    PACE = float(opts["pace"])
    queries = random.sample(opts["queries"], min(_limit(opts["max_queries_per_run"]), len(opts["queries"])))
    per_query, per_run = _limit(opts["max_jobs_per_query"]), _limit(opts["max_jobs_per_run"])
    # Every new card comes back: opened ones to be scored, the rest with a status and reason.
    jobs, opened, pending, cards, done = [], 0, [], {}, set()
    with sync_playwright() as pw:
        step("opening Chrome")
        ctx = _launch(pw, opts)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(30000)
        try:
            # Land on the jobs home first, as a person would, before searching.
            step("landing on LinkedIn Jobs")
            page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded")
            check_blocked(page)
            pause(3, 7)
            todo = [r for r in (revisit or []) if opts["revisit_pending"]][:per_run]
            for n, r in enumerate(todo, 1):
                m = re.search(r"/jobs/view/(\d+)", r["url"])
                if not m:
                    continue
                jid = m.group(1)
                step(f"revisiting earlier queued/preliminary job {n} of {len(todo)}")
                card = {"title": r["title"], "company": r["company"] or "", "location": "", "posted": r["posted"] or ""}
                page.goto(job_url(jid), wait_until="domcontentloaded")
                job = read_posting(page, jid, card)
                jobs.append(job)
                done.add(jid)
                opened += job.status != "queued"
                pause(2, 5)
            for i, q in enumerate(queries):
                if opened >= per_run:
                    break
                where = f"search {i + 1} of {len(queries)} “{q}”"
                if i:
                    step(f"pausing before {where}")
                    pause(15, 45)
                step(f"{where}: loading results")
                url = SEARCH_URL.format(q=quote_plus(q), loc=quote_plus(opts["location"]),
                                        secs=int(opts["posted_within_hours"]) * 3600)
                if opts["remote_only"]:
                    url += "&f_WT=2"
                page.goto(url, wait_until="domcontentloaded")
                check_blocked(page)
                try:
                    page.wait_for_selector('a[href*="/jobs/view/"]', timeout=15000)
                except Exception:
                    log.info("linkedin %r: no results", q)
                    continue
                pause(2, 5)
                dismiss_signin(page)
                first = page.locator('a[href*="/jobs/view/"]').first
                hover(page, first)  # put the mouse over the results list before scrolling it
                read_scroll(page)
                load_all_results(page, opts["max_cards_per_search"],
                                 lambda n: step(f"{where}: loading more results ({n} so far)"))
                cards = collect_cards(page)
                fresh = []
                for jid, c in cards.items():
                    if jid in done or seen(job_url(jid)):
                        continue  # already handled in this run (another search) or an earlier one
                    done.add(jid)
                    # Only click postings whose title matches a profile keyword; search engines
                    # fuzz terms like "X++" into "C++", and every extra click is extra exposure.
                    if match_profiles(Job("", c["title"], "", ""), cfg):
                        fresh.append(jid)
                    else:
                        jobs.append(card_job("linkedin", job_url(jid), c, "skipped",
                                             "not opened: title has no Business Central / F&O / Dynamics keyword"))
                budget = min(per_query, per_run - opened)
                picks = fresh[:budget]
                for jid in fresh[budget:]:
                    jobs.append(card_job("linkedin", job_url(jid), cards[jid], "queued",
                                         f"not opened yet: open limit for this run reached "
                                         f"(max_jobs_per_query={opts['max_jobs_per_query']}, "
                                         f"max_jobs_per_run={opts['max_jobs_per_run']})"))
                log.info("linkedin %r: %d cards, %d new with matching titles, opening %d", q, len(cards), len(fresh),
                         len(picks))
                pending = list(picks)
                for n, jid in enumerate(picks, 1):
                    step(f"{where}: reading job {n} of {len(picks)} ({len(cards)} results, {len(fresh)} new matching)")
                    job = open_job(page, ctx, jid, cards[jid])
                    pending.remove(jid)
                    jobs.append(job)
                    opened += job.status != "queued"
        except Blocked as e:
            last_block = str(e)
            log.warning("linkedin stopped: checkpoint/sign-in wall (%s). Not bypassing; try again later.", e)
            for jid in pending:  # picked for opening but never read
                jobs.append(card_job("linkedin", job_url(jid), cards[jid], "queued",
                                     "not opened yet: LinkedIn showed a CAPTCHA/sign-in wall first; retried next run"))
        except Exception as e:
            # E.g. the window was closed mid-run: keep everything listed so far instead of losing it all.
            last_block = f"stopped early ({e.__class__.__name__}: {str(e).splitlines()[0][:120]})"
            log.warning("linkedin %s", last_block)
            for jid in pending:
                jobs.append(card_job("linkedin", job_url(jid), cards[jid], "queued",
                                     "not opened yet: the LinkedIn run stopped early; retried next run"))
        finally:
            try:
                ctx.close()
            except Exception:
                pass  # already closed
    return jobs


def login(cfg):
    """Open the browser profile on the sign-in page; you sign in by hand, then close the window."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        ctx = _launch(pw, {**_opts(cfg), "headless": False})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.linkedin.com/login")
        print("Sign in to LinkedIn in the browser window, then close the window.")
        page.wait_for_event("close", timeout=0)
        ctx.close()


if __name__ == "__main__":
    import yaml

    from .main import load_env

    load_env()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = yaml.safe_load(open("config.yaml"))
    if "--login" in sys.argv:
        login(cfg)
    elif "--test" in sys.argv:
        opts = cfg["sources"].setdefault("linkedin_options", {})
        opts.update(max_queries_per_run=1, max_jobs_per_query=3, max_jobs_per_run=3, max_cards_per_search=60)
        for j in search(cfg):
            print(f"- [{j.status or 'opened'}] {j.title} | {j.company} | posted {j.posted or '?'} | "
                  f"{len(j.description)} chars | {j.reason}")
    else:
        print(__doc__)
