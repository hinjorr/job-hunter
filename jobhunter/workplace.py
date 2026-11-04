"""Is a job workable from Pakistan? Logged-out LinkedIn pages don't show the On-site/Hybrid/Remote
label, so this reads what the posting itself says. Two layers:

1. onsite_elsewhere(): a free text check before Gemini. Skips only clear cases: the posting says
   on-site/hybrid/office-based, never mentions remote, and isn't in Pakistan.
2. Gemini's "remote_from_pakistan" answer (yes/no/unclear) after it reads the posting; see scoring.py.
"""
import re

NOT_REMOTE = "NOT REMOTE"  # reason prefix for jobs skipped by this filter

_ONSITE = re.compile(r"\b(on[- ]?site|in[- ]office|office[- ]based|work(?:ing)? from (?:the |our )?office|"
                     r"hybrid|relocat(?:e|ion) (?:to|required))\b", re.I)
_REMOTE = re.compile(r"\b(remote|remotely|work from home|wfh|work from anywhere|anywhere in the world|"
                     r"fully distributed|telecommut\w*)\b", re.I)
_PAKISTAN = re.compile(r"\b(pakistan|karachi|lahore|islamabad|rawalpindi|faisalabad|peshawar|multan)\b", re.I)


def onsite_elsewhere(job):
    """The on-site wording found, when the posting is clearly on-site/hybrid outside Pakistan; else None."""
    text = " ".join((job.title or "", job.company or "", job.description or ""))
    if not job.description or _PAKISTAN.search(text) or _REMOTE.search(text):
        return None  # card only, in Pakistan, or remote mentioned at all: let Gemini judge
    m = _ONSITE.search(text)
    return m.group(0) if m else None


def skip_reason(why):
    return f"{NOT_REMOTE}: {why}, and not in Pakistan (workplace_filter)"
