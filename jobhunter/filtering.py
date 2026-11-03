import re


def match_profiles(job, cfg) -> list:
    """Return profile names whose keywords appear in the job text (word-boundary aware)."""
    text = f"{job.title} {job.description}".lower()
    hits = []
    for name, p in cfg["profiles"].items():
        for kw in p["keywords"]:
            pat = r"(?<![\w])" + re.escape(kw.lower()) + r"(?![\w])"
            if re.search(pat, text):
                hits.append(name)
                break
    return hits
