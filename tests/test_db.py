from jobhunter.db import DB
from jobhunter.models import Job


def test_queued_jobs_are_retried_then_kept(tmp_path):
    db = DB(str(tmp_path / "t.db"))
    j = Job("linkedin", "Business Central Developer", "A", "u1", status="queued", reason="open limit")
    db.save(j)
    assert not db.seen("u1")  # queued: next run may pick it up again
    j.status, j.score, j.reason = "scored", 80, "good fit"
    db.save(j)
    assert db.seen("u1")
    assert db.c.execute("SELECT status, score, reason FROM jobs").fetchone() == ("scored", 80, "good fit")
