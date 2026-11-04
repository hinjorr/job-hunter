import yaml

from jobhunter.filtering import match_profiles
from jobhunter.models import Job
from jobhunter.notify import build_digest

CFG = yaml.safe_load(open("config.yaml"))


def test_matches_business_central():
    j = Job("t", "Senior Business Central Developer", "Acme", "http://x", "AL language work")
    assert "business_central" in match_profiles(j, CFG)


def test_word_boundaries():
    # "al developer" must not match inside "global developer"; ".NET" roles are out of scope
    j = Job("t", "Global developer (.NET)", "Acme", "http://x", "")
    assert match_profiles(j, CFG) == []


def test_finance_operations():
    j = Job("t", "D365 F&O Technical Consultant", "A", "http://x", "X++ and data entities")
    assert "finance_operations" in match_profiles(j, CFG)


def test_digest_sorted():
    a, b = Job("s", "A", "c", "u1", score=70), Job("s", "B", "c", "u2", score=90)
    d = build_digest([a, b])
    assert d.index("[B]") < d.index("[A]")
