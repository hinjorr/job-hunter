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


def send_all(text: str):
    """Send the digest to every configured channel. One failing never stops the others or the run."""
    for name, send in (("Telegram", send_telegram), ("Discord", send_discord)):
        try:
            send(text)
        except Exception as e:  # network/HTTP errors: the digest is still in digest.md
            log.warning("%s send failed: %s", name, e)


def _chunks(text: str, limit: int):
    """Split on line breaks so links aren't cut in half; hard-split any single over-long line."""
    out, cur = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:
            if cur:
                out.append(cur)
                cur = ""
            out.append(line[:limit])
            line = line[limit:]
        if len(cur) + len(line) > limit:
            out.append(cur)
            cur = ""
        cur += line
    if cur.strip():
        out.append(cur)
    return out


def send_discord(text: str):
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        log.info("Discord not configured; digest only written to digest.md")
        return
    for part in _chunks(text, 1900):  # Discord limit is 2000 characters per message
        requests.post(url, json={"content": part,
                                 "flags": 4,  # no link previews, keeps the channel compact
                                 "allowed_mentions": {"parse": []}},  # job text can't ping @everyone
                      timeout=30).raise_for_status()


def send_telegram(text: str):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        log.info("Telegram not configured; digest only written to digest.md")
        return
    for i in range(0, len(text), 3900):  # Telegram limit is 4096
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text[i:i + 3900],
                            "disable_web_page_preview": True}, timeout=30).raise_for_status()
