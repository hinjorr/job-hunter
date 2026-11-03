import datetime
import logging
import os

import requests

log = logging.getLogger(__name__)


def build_digest(jobs) -> str:
    today = datetime.date.today().isoformat()
    if not jobs:
        return f"# Job digest {today}\n\nNothing new above the score threshold today.\n"
    lines = [f"# Job digest {today}", ""]
    for j in sorted(jobs, key=lambda x: -x.score):
        lines.append(f"- **{j.score}** [{j.title}]({j.url}) — {j.company or 'n/a'} "
                     f"({j.source}; {', '.join(j.profiles)})\n  {j.reason}")
    return "\n".join(lines) + "\n"


def send_telegram(text: str):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        log.info("Telegram not configured; digest only written to digest.md")
        return
    for i in range(0, len(text), 3900):  # Telegram limit is 4096
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text[i:i + 3900],
                            "disable_web_page_preview": True}, timeout=30).raise_for_status()
