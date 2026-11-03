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
