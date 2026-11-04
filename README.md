# job-hunter

Finds Microsoft Dynamics 365 **Business Central** and **Finance & Operations (X++)** jobs. Pulls postings from
LinkedIn (real Chrome window, logged out), RemoteOK, We Work Remotely, Remotive, HN "Who is hiring" and Reddit,
filters them by keyword, scores each with Gemini against your profile, and shows them in a local web page with
live run progress. Every posting is listed as scored, preliminary, queued or skipped, with the reason.

**Installation and usage: see [USER_GUIDE.md](USER_GUIDE.md).**

Quick start (Windows):
```bash
git clone https://github.com/hinjorr/job-hunter
cd job-hunter
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
start_ui.bat
```
Put your Gemini key (free: https://aistudio.google.com/apikey) in `.env` before the first run, then press
**Re-run** on http://127.0.0.1:8765. Tune keywords, your profile summary and sources in `config.yaml`.

`.github/workflows/hunt.yml` is an older optional cloud run; it predates the LinkedIn source, which needs a
desktop Chrome, so set `linkedin: false` if you use it.
