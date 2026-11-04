# Job Hunter: user guide

Job Hunter finds **Microsoft Dynamics 365 Business Central** and **Finance & Operations (X++)** jobs for you.
It collects postings from several sites, filters them by your keywords, has Google Gemini score each one
(0–100) against your profile with a one-line reason, and shows everything in a local web page.

Sources: **LinkedIn** (through a real Chrome window, logged out), RemoteOK, We Work Remotely, Remotive,
Hacker News "Who is hiring" and Reddit.

---

## 1. What you need

| Requirement | Notes |
|---|---|
| Windows 10/11 | Mac/Linux also work; their commands are shown where they differ. |
| [Python 3.10+](https://www.python.org/downloads/) | Tested with 3.12. During install, tick **"Add python.exe to PATH"**. |
| [Git](https://git-scm.com/downloads) | To download the code. |
| [Google Chrome](https://www.google.com/chrome/) | The LinkedIn source drives your installed Chrome. No extra browser download is needed. |
| A free **Gemini API key** | Create one at <https://aistudio.google.com/apikey>. Without a key, jobs get a simple keyword score instead. |

---

## 2. Install

Open a terminal (PowerShell or Command Prompt) in the folder where you keep projects.

**1. Download the code**
```bash
git clone https://github.com/hinjorr/job-hunter
cd job-hunter
```

**2. Create a virtual environment.** Everything installs into the project's own `.venv` folder,
not into your system Python.
```bash
python -m venv .venv
```

**3. Activate it**
```bash
.venv\Scripts\activate
```
On Mac/Linux: `source .venv/bin/activate`. Your prompt now starts with `(.venv)`.

**4. Install the packages**
```bash
pip install -r requirements.txt
```
This installs `requests`, `feedparser`, `pyyaml`, `playwright`, `flask` and `pytest`.
You do **not** need `playwright install`: the LinkedIn source uses your installed Google Chrome.

**5. Add your Gemini key.** Copy the example settings file:
```bash
copy .env.example .env
```
(Mac/Linux: `cp .env.example .env`). Open `.env` in a text editor and paste your key:
```
GEMINI_API_KEY=your-key-here
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=
```
The Telegram and Discord lines are optional; leave them empty for now. `.env` is git-ignored, so your key
is never committed.

**Discord (optional).** To get the digest as a Discord message: in your own Discord server, open the
channel's **Edit Channel → Integrations → Webhooks → New Webhook → Copy Webhook URL**, and paste it after
`DISCORD_WEBHOOK_URL=`. The Discord app is not needed on the PC; Job Hunter posts to that link directly.
Keep the link private: anyone who has it can post in that channel.

**6. Check the install**
```bash
python -m pytest
```
All tests should pass.

---

## 3. Start it

Double-click **`start_ui.bat`** in the `job-hunter` folder, or run:
```bash
.venv\Scripts\python -m jobhunter.web
```
Your browser opens **http://127.0.0.1:8765**. Keep the black terminal window open while you use
the page; closing it stops Job Hunter.

Press **Re-run** to start a hunt, or let it run by itself (see [8. Automatic runs](#8-automatic-runs)).

### While a run is going
- **Progress** lists every stage (each source, filtering, Gemini scoring, digest) with what it is doing
  right now, e.g. *"search 2 of 7 'X++ developer': reading job 4 of 12"*. It shows the time elapsed,
  not an estimate.
- A **Chrome window opens for LinkedIn. Don't click, scroll or close it** while it works; that breaks the run.
- Each source's jobs appear in the list as soon as that source finishes.
- **Log** (under Progress) shows the detailed log if something goes wrong.

A full run with LinkedIn can take 30–60 minutes, because it opens and reads every matching posting.

### Reading the job list
Every posting a source returns is listed with a **status** and a **reason**:

| Status | Meaning |
|---|---|
| **Score (0–100)** | Gemini read the full posting and scored it. The reason is Gemini's. |
| **Score + PRELIM** | Scored from the LinkedIn search card only (title, company, location). It is opened and re-scored in full next run. |
| **QUEUED** | Not finished yet (e.g. LinkedIn stopped early). Retried next run. |
| **SKIPPED** | Ruled out, e.g. no Business Central / F&O / Dynamics keyword, or posted more than 30 days ago. |

Filters: **Status** (default: scored + preliminary), **Source** (e.g. only LinkedIn), **Score** (minimum),
**New in last run**, and a text search. **How jobs are picked** explains the exact rules using your settings.

Click a job title to open the posting.

---

## 4. Settings (`config.yaml`)

Open `config.yaml` in a text editor. Changes apply on the next **Re-run**; no restart needed.

| Setting | What it does |
|---|---|
| `profiles` | Keyword groups. A job is considered only if its title or description contains one of these. |
| `candidate_summary` | Your profile in plain words. Gemini scores every job against this, so keep it accurate. |
| `min_score` | Minimum score for the digest and the default score filter (default 60). |
| `max_new_per_run` | Most jobs Gemini fully scores in one run (extra ones are queued). |
| `workplace_filter` | `true` (default) skips jobs that are on-site or hybrid outside Pakistan, listed as SKIPPED with a reason starting "NOT REMOTE". Clear cases are caught from the posting text before Gemini (no request used); otherwise Gemini decides after reading the posting. Logged-out LinkedIn doesn't show the On-site/Remote label, so this reads what the posting says. `false` turns it off. |
| `max_age_days` | Jobs posted longer ago than this are skipped (default 30). |
| `max_card_scores_per_run` | Most LinkedIn cards that get a preliminary score in one run. |
| `gemini_model` | The Gemini model. If Google retires it (you'll see a 404 error), change it to a current "flash-lite" model. |
| `sources` | Turn each source on/off (`true`/`false`). |
| `remotive_terms`, `reddit_feeds` | Search terms / feeds for those sources. |

**LinkedIn** (`linkedin_options`):

| Setting | What it does |
|---|---|
| `queries` | The searches to run. Add or remove lines. |
| `location`, `remote_only` | Where to search; `remote_only: true` adds LinkedIn's "Remote" filter. |
| `posted_within_hours` | Only jobs posted in this window (default 24). |
| `max_queries_per_run` | How many of the queries to run (0 = all). |
| `max_jobs_per_query`, `max_jobs_per_run` | How many postings to open (0 = every matching one). |
| `max_cards_per_search` | Stop loading more result pages after this many cards. |
| `revisit_pending` | Reopen jobs left queued/preliminary by earlier runs. |
| `pace` | Speed of the clicking and pauses: `1.0` slow and person-like, `0.5` default, `0.3` fast. |
| `headless` | `false` shows the Chrome window (recommended). |

LinkedIn runs **logged out** by default; it doesn't use your account. To search signed in (use a
separate account, not your main one), run this once, sign in by hand in the window that opens, then close it:
```bash
.venv\Scripts\python -m jobhunter.linkedin --login
```

---

## 5. Other commands

Run these from the `job-hunter` folder.

| Command | Purpose |
|---|---|
| `.venv\Scripts\python -m jobhunter.main` | Run a hunt without the web page; prints the digest. |
| `.venv\Scripts\python -m jobhunter.linkedin --test` | Quick LinkedIn check: one search, opens 3 postings, prints what it found (saves nothing). |
| `.venv\Scripts\python -m jobhunter.web --no-browser` | Start the web page without opening a browser tab. |
| `.venv\Scripts\python -m pytest` | Run the tests. |

---

## 6. Files it creates

All are in the `job-hunter` folder and git-ignored.

| File / folder | What it is |
|---|---|
| `jobs.db` | Every job seen, with status, score and reason. Delete it to start fresh (all jobs are re-checked next run). |
| `digest.md` | The latest digest: scored jobs at `min_score`+. |
| `.linkedin-profile/` | LinkedIn's own Chrome profile (cookies, sign-in if you used `--login`). |
| `blocked/` | A screenshot whenever LinkedIn stops at a CAPTCHA/checkpoint, so you can see what happened. |
| `schedule.json` | Your automatic-run setting from the page, and when the last run started. |
| `.env` | Your Gemini key. Never share or commit it. |

---

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| Sources fail with **"Failed to resolve … getaddrinfo failed"** | Your internet provider's DNS is unreliable. Set Windows DNS to `1.1.1.1` / `8.8.8.8`: Settings → Network & internet → your connection → Hardware properties → DNS server assignment → Edit → Manual. Job Hunter already retries once after 15 seconds. |
| **Gemini 404 "no longer available"** | The model was retired. Put a current model in `gemini_model` in `config.yaml`. |
| **Gemini 429 / 503** (busy or rate-limited) | It retries automatically; if it still fails, that job gets a keyword score. Lower `max_new_per_run` if it keeps happening. |
| LinkedIn shows **"stopped at a sign-in wall/CAPTCHA"** | LinkedIn asked for verification. Look at the screenshot in `blocked/`. Wait a few hours, or raise `pace` to `1.0`. Unfinished jobs are queued and retried next run. |
| **"Opening in existing browser session" / profile already in use** | A LinkedIn Chrome window from an earlier run or `--login` is still open. Close it and run again. |
| **"Target page, context or browser has been closed"** | The LinkedIn Chrome window was closed or clicked during the run. Leave it alone while it works. |
| The page says **"Can't reach the Job Hunter server"** | The terminal window running `start_ui.bat` was closed. Start it again. |
| **Port 8765 already in use** | Job Hunter is already running in another window. Use that one, or close it first. |
| Reddit feeds fail with **HTTPError / 429** | Reddit limits automated requests; it usually works on the next run. |

---

## 8. Automatic runs

At the top of the page, tick **Run automatically every** and pick how often (3–24 hours; 6 is the default).
The status line shows when the next automatic run is. The setting is saved in `schedule.json` and kept
across restarts.

- The next run is counted from when the last run **started**, including runs you start with **Re-run**.
- When Job Hunter starts (for example after Windows boots) and a run is overdue, it waits 2 minutes for
  the internet connection, then runs. If the last run was recent, it waits for the normal time.
- It only runs while Job Hunter is running and the PC is awake.

**Start Job Hunter with Windows:** put a shortcut to `start_ui.bat` in your Startup folder (press
Win+R, type `shell:startup`, Enter). It starts when you sign in, so it needs automatic sign-in to run
after a reboot with nobody at the PC.
