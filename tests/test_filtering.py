import yaml

from jobhunter.filtering import match_profiles
from jobhunter.models import Job
from jobhunter.notify import build_digest

CFG = yaml.safe_load(open("config.yaml"))


def test_matches_business_central():
    j = Job("t", "Senior Business Central Developer", "Acme", "http://x", "AL language work")
    assert "business_central" in match_profiles(j, CFG)


def test_word_boundaries():
    # "rag" must not match inside "storage"; "sap" not inside "sapphire"
    j = Job("t", "Storage engineer", "Sapphire", "http://x", "")
    assert match_profiles(j, CFG) == []


def test_dotnet():
    assert "dotnet" in match_profiles(Job("t", "Backend (.NET)", "A", "http://x"), CFG)


def test_digest_sorted():
    a, b = Job("s", "A", "c", "u1", score=70), Job("s", "B", "c", "u2", score=90)
    d = build_digest([a, b])
    assert d.index("[B]") < d.index("[A]")
