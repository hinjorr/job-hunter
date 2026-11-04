import json

import pytest

from jobhunter import scheduler

H = 3600
T0 = 1_800_000_000  # a fixed "now" for the tests


def make(tmp_path, data=None):
    p = tmp_path / "schedule.json"
    if data is not None:
        p.write_text(json.dumps(data), encoding="utf-8")
    return scheduler.Schedule(p, now=T0), p


def test_defaults_on_every_6_hours_first_run_after_startup_delay(tmp_path):
    s, _ = make(tmp_path)
    assert s.settings()["enabled"] is True and s.settings()["every_hours"] == 6
    assert s.next_run(T0) == T0 + scheduler.STARTUP_DELAY  # never ran: soon after start, not instantly


def test_recent_run_waits_full_interval(tmp_path):
    s, _ = make(tmp_path, {"enabled": True, "every_hours": 6, "last_run": T0 - 1 * H})
    assert s.next_run(T0) == T0 + 5 * H


def test_overdue_after_boot_runs_after_delay(tmp_path):
    s, _ = make(tmp_path, {"enabled": True, "every_hours": 6, "last_run": T0 - 20 * H})
    assert s.next_run(T0) == T0 + scheduler.STARTUP_DELAY


def test_mark_run_and_update_are_saved(tmp_path):
    s, p = make(tmp_path)
    s.update(True, 4)
    s.mark_run(T0 + 500)
    saved = json.loads(p.read_text(encoding="utf-8"))
    assert saved == {"enabled": True, "every_hours": 4, "last_run": T0 + 500}
    assert s.next_run(T0 + 600) == T0 + 500 + 4 * H


def test_off_means_no_next_run(tmp_path):
    s, _ = make(tmp_path)
    s.update(False, 6)
    assert s.next_run(T0) is None


def test_bad_values_rejected_and_bad_file_falls_back(tmp_path):
    s, _ = make(tmp_path, {"enabled": True, "every_hours": 7})
    assert s.settings()["every_hours"] == 6
    with pytest.raises(ValueError):
        s.update(True, 2)
    with pytest.raises(ValueError):
        s.update("yes", 6)
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    assert scheduler.Schedule(tmp_path / "broken.json").settings()["every_hours"] == 6
