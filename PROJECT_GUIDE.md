# Job Hunter: full project guide

## 1. What you asked for
An automation that hunts for work for you, so you stop searching LinkedIn, Reddit and other
sites by hand. Target areas: **.NET, AI, AI in ERP, Microsoft Dynamics 365 Business Central, FinOps**.
Targets: jobs and freelance clients. Ideas you raised: scraping with Playwright (including LinkedIn)
and messaging recruiters/CEOs from your own profile.

Reference repos reviewed:
- `remoteintech/remote-jobs`: a curated list of remote-friendly companies (a lead list, not a scraper).
- `huginn/huginn`: a self-hosted Ruby agent/automation engine (like a private Zapier). Too heavy for this; we built a light Python pipeline instead.

## 2. Decisions made
| Topic | Decision |
|---|---|
| LinkedIn scraping | Not done. Violates LinkedIn's terms and risks banning your account. Use LinkedIn job-alert emails and Google-indexed posts instead. |
| Messaging recruiters/CEOs | Tool researches and drafts personalised messages; **you review and send manually** (~15-20/day). No automated DMs. |
| AI scoring | Gemini free tier (no Anthropic key needed). |
| Hosting | Runs on **your own PC** (home IP, not blocked by sites), started from the Windows Startup folder. |

## 3. What is built (branch `claude/zen-cori-9isegx`)
```
config.yaml              keyword profiles, candidate summary, min_score, sources
jobhunter/sources.py     RemoteOK, We Work Remotely, Remotive, HN "Who is hiring", Reddit RSS
jobhunter/filtering.py   word-boundary keyword match against your 5 profiles
jobhunter/scoring.py     Gemini scores each posting 0-100 (+ one-line reason); keyword fallback without key
jobhunter/db.py          SQLite (jobs.db) so you never see the same posting twice
jobhunter/notify.py      builds digest.md, optional Telegram message
jobhunter/main.py        pipeline: fetch -> dedupe -> filter -> score -> digest; loads .env
tests/                   tests (filtering, digest ordering, Discord, schedule)
```
Pipeline: **collect -> dedupe -> keyword filter -> Gemini score -> digest (+Telegram)**.
A failing source is logged and skipped; it never stops the run.

## 4. How to run it (your PC)
```bash
git clone https://github.com/hinjorr/job-hunter && cd job-hunter
git checkout claude/zen-cori-9isegx
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
```
Edit `.env`:
```
GEMINI_API_KEY=your_key            # free: https://aistudio.google.com/apikey
TELEGRAM_BOT_TOKEN=                # optional (create bot via @BotFather)
TELEGRAM_CHAT_ID=                  # optional
```
Run:
```bash
python -m jobhunter.main           # prints digest and writes digest.md
python -m pytest                   # run tests
```
Automatic runs: set "Run automatically every N hours" in the web page (see USER_GUIDE.md section 8).

Tuning: edit `config.yaml` (keywords, `min_score`, `max_new_per_run`, sources, `candidate_summary`).

## 5. Known caveats
- Fetchers were **not tested live** (the build sandbox blocks job sites). Expect to fix small
  issues on your first real run; send me the log.
- Reddit may return nothing from datacenter IPs; your home PC is better.
- Gemini free tier is rate-limited; the script retries and caps calls per run.

## 6. What is left to build
1. **LinkedIn alert-email parser**: read LinkedIn job-alert emails from your inbox (IMAP/Gmail) and feed them into the pipeline.
2. **Playwright scrapers** for company careers pages (seeded from remoteintech/remote-jobs) and sites without feeds or APIs. Run locally, low volume, respecting each site's terms/robots.txt.
3. **Client-hunting sources**: freelance boards and Reddit/HN posts like "looking for a Business Central developer".
4. **Recruiter/CEO outreach assistant**: build a target list and have Gemini draft a personalised message per person; you send it manually.
5. **Application tracker**: mark jobs applied / replied / interview, avoid double-contacting.
6. **More sources**: Himalayas, Adzuna/Jooble APIs, Google-search of LinkedIn posts.
7. **Email digest option** (besides Telegram and Discord).
