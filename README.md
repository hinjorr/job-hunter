# job-hunter

Daily job/client finder: pulls postings from RemoteOK, We Work Remotely, Remotive,
HN "Who is hiring" and Reddit, keyword-filters them against your profiles
(.NET, AI, AI-in-ERP, Business Central, FinOps), scores them with Gemini, and sends a digest.

## Setup
1. Repo → Settings → Secrets and variables → Actions → add:
   - `GEMINI_API_KEY` (free key from https://aistudio.google.com/apikey)
   - `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (optional; create a bot with @BotFather)
2. Actions tab → **job-hunt** → *Run workflow* to test. It then runs daily.
3. The digest is also uploaded as a workflow artifact (`digest.md`).

Tune keywords, `min_score` and sources in `config.yaml`.

## Local run
```bash
pip install -r requirements.txt
GEMINI_API_KEY=... python -m jobhunter.main
python -m pytest
```
Without `GEMINI_API_KEY` it falls back to a simple keyword-based score.

## Run on your own PC (no GitHub Actions needed)
```bash
git clone <repo> && cd job-hunter
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then fill in GEMINI_API_KEY (and Telegram if wanted)
python -m jobhunter.main    # digest printed + saved to digest.md
```
Schedule it daily:
- **Windows:** `schtasks /create /tn JobHunter /tr "C:\path\to\job-hunter\run_daily.bat" /sc daily /st 09:00`
- **Mac/Linux:** `crontab -e` → `0 9 * * * cd /path/to/job-hunter && .venv/bin/python -m jobhunter.main >> run.log 2>&1`

Running from your home IP also avoids the datacenter blocks that GitHub's servers hit.
