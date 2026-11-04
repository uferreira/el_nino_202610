"""The update step shared by the two writers of main (enso.publish), and
the staleness check (enso.status).

The git tests use throwaway repositories: a bare "remote" and two clones,
one per writer, with a stand-in build whose output (docs/footer.txt) depends
on both writers' data, as the real footer date does.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from enso import publish, status


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repos(tmp_path, monkeypatch):
    for k, v in {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org",
                 "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.org"}.items():
        monkeypatch.setenv(k, v)
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    seed = tmp_path / "seed"
    _git(tmp_path, "clone", "-q", str(remote), str(seed))
    (seed / "data" / "series").mkdir(parents=True)
    for k in ("sst", "sea"):
        (seed / "data" / "series" / f"{k}.csv").write_text(f"{k} v0\n")
    _build(seed)
    _git(seed, "add", "-A")
    _git(seed, "commit", "-qm", "seed")
    _git(seed, "push", "-q", "origin", "main")
    clones = {}
    for name in ("ci", "pc"):
        clones[name] = tmp_path / name
        _git(tmp_path, "clone", "-q", str(remote), str(clones[name]))
    return SimpleNamespace(remote=remote, tmp=tmp_path, **clones)


def _build(root: Path) -> None:
    """docs/ as a pure function of all the data, like the real build."""
    data = sorted((root / "data" / "series").glob("*.csv"))
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "footer.txt").write_text("".join(p.read_text() for p in data))


def _cfg():
    def ds(key, kind):
        return SimpleNamespace(key=key, source={"type": kind}, group=SimpleNamespace(label=kind))
    datasets = [ds("sst", "noaa_sst"), ds("sea", "uhslc")]
    return SimpleNamespace(datasets=datasets, dataset=lambda k: next(d for d in datasets if d.key == k))


class Fake(publish.Publisher):
    def __init__(self, root, kind, value, before_publish=None, extra=None, **kw):
        super().__init__(_cfg(), kind, root=root, **kw)
        self.value, self.before_publish, self.extra = value, before_publish, extra

    def fetch(self):
        for k in self.keys:
            (self.root / "data" / "series" / f"{k}.csv").write_text(f"{k} {self.value}\n")
        if self.extra:
            (self.root / self.extra).write_text("not mine\n")
        return [(k, f"OK     {k}") for k in self.keys]

    def build(self):
        _build(self.root)

    def test(self):
        return True

    def message(self):
        return f"data: {self.source_type} {self.value}"

    def _publish(self):
        if self.before_publish:
            self.before_publish()
        super()._publish()


def _remote_file(repos, path):
    return _git(repos.remote, "show", f"main:{path}")


def test_one_writer_publishes(repos):
    assert Fake(repos.ci, "noaa_sst", "v1").run() == publish.EXIT_OK
    assert _remote_file(repos, "data/series/sst.csv") == "sst v1\n"
    assert _remote_file(repos, "docs/footer.txt") == "sea v0\nsst v1\n"


def test_nothing_new_commits_nothing(repos):
    head = _git(repos.remote, "rev-parse", "main")
    assert Fake(repos.ci, "noaa_sst", "v0").run() == publish.EXIT_OK
    assert _git(repos.remote, "rev-parse", "main") == head


def test_a_race_on_the_shared_docs_is_rebuilt_and_retried(repos):
    """The PC pushes while CI is between its commit and its push: both
    touched docs/footer.txt, so CI's rebase conflicts. CI resets to the
    remote, re-applies only its own data, rebuilds and pushes."""
    pc = Fake(repos.pc, "uhslc", "v1", write_status=True)
    ci = Fake(repos.ci, "noaa_sst", "v1", before_publish=pc.run)
    assert ci.run() == publish.EXIT_OK
    assert _remote_file(repos, "data/series/sst.csv") == "sst v1\n"
    assert _remote_file(repos, "data/series/sea.csv") == "sea v1\n"
    assert _remote_file(repos, "docs/footer.txt") == "sea v1\nsst v1\n"   # both writers' data
    assert "uhslc" in _remote_file(repos, "data/status/uhslc.json")
    log = _git(repos.remote, "log", "--format=%s", "main").split("\n")
    assert log[:2] == ["data: noaa_sst v1", "data: uhslc v1"]


def test_a_second_failure_stops_loudly_and_leaves_the_remote_alone(repos):
    hook = repos.remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho rejected by test >&2\nexit 1\n")
    hook.chmod(0o755)
    head = _git(repos.remote, "rev-parse", "main")
    with pytest.raises(publish.PublishError, match="failed twice"):
        Fake(repos.ci, "noaa_sst", "v1").run()
    assert _git(repos.remote, "rev-parse", "main") == head


def test_a_file_the_writer_does_not_own_stops_the_run(repos):
    head = _git(repos.remote, "rev-parse", "main")
    with pytest.raises(publish.PublishError, match="does not own"):
        Fake(repos.ci, "noaa_sst", "v1", extra="data/series/sea.csv").run()
    assert _git(repos.remote, "rev-parse", "main") == head
    assert (repos.ci / "data" / "series" / "sst.csv").read_text() == "sst v0\n"   # restored


def test_a_branch_without_upstream_stops_the_run(repos):
    _git(repos.ci, "branch", "--unset-upstream")
    with pytest.raises(publish.PublishError, match="no upstream"):
        Fake(repos.ci, "noaa_sst", "v1").run()


def test_a_dirty_tree_stops_the_run(repos):
    (repos.ci / "notes.txt").write_text("work in progress\n")
    with pytest.raises(publish.PublishError, match="uncommitted"):
        Fake(repos.ci, "noaa_sst", "v1").run()


def test_status_records_checked_dates_and_flags_stale_datasets(tmp_path):
    status.record("uhslc", [("callao", "OK     callao"), ("palau", "FAILED palau: timeout")],
                  day="2026-11-01", directory=tmp_path)
    status.record("uhslc", [("callao", "SAME   callao"), ("palau", "HELD   palau")],
                  day="2026-11-06", directory=tmp_path)
    d = status.read("uhslc", tmp_path)["datasets"]
    assert d["callao"] == {"last_attempt": "2026-11-06", "last_result": "SAME", "checked": "2026-11-06"}
    assert "checked" not in d["palau"]           # a failure or a held record is not a check
    keys = ["callao", "palau"]
    assert [p.split(":")[0] for p in status.stale("uhslc", keys, 15, "2026-11-20", tmp_path)] == ["palau"]
    stale = status.stale("uhslc", keys, 15, "2026-11-22", tmp_path)
    assert [p.split(":")[0] for p in stale] == ["callao", "palau"]          # 16 days


def test_checked_label_is_the_last_successful_download(tmp_path):
    status.record("noaa_sst", [("nino12", "SAME   nino12"), ("nino3", "FAILED nino3: timeout")],
                  day="2026-11-04", directory=tmp_path)
    assert status.checked_label("noaa_sst", "nino12", tmp_path) == "4 Nov 2026"
    assert status.checked_label("noaa_sst", "nino3", tmp_path) is None       # never succeeded


SSTOI = """ YR   MON  NINO1+2  ANOM   NINO3    ANOM   NINO4    ANOM NINO3.4    ANOM
 2026   9   25.27    4.69   28.65    3.64   29.62    0.95   29.60    2.84
 2026  10   26.12    5.25   29.24    4.16   29.88    1.20   30.01    3.25
"""


def _site(tmp_path, ends):
    import json
    for key, last in ends.items():
        p = tmp_path / "data" / "phase" / f"{key}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"periods": ["2026-08", last]}), encoding="utf-8")
    return tmp_path


def test_behind_flags_a_month_noaa_has_and_the_site_lacks(tmp_path):
    assert status.latest_in_sstoi(SSTOI) == "2026-10"
    docs = _site(tmp_path, {"nino12": "2026-09", "nino3": "2026-10"})
    problems = status.behind("2026-10", ["nino12", "nino3", "nino4"], docs)
    assert [p.split(":")[0] for p in problems] == ["nino12", "nino4"]        # behind; missing
    assert "2026-10" in problems[0] and "2026-09" in problems[0]
    assert status.behind("2026-09", ["nino12", "nino3"], docs) == []
    with pytest.raises(ValueError):
        status.latest_in_sstoi("no data here\n")


def test_behind_command_turns_red_when_noaa_is_ahead(monkeypatch, capsys):
    """Against the committed docs/: red for a month the site lacks, green for its own."""
    site_month = status.site_latest("nino12")
    monkeypatch.setitem(status.UPSTREAM, "noaa_sst", lambda: "2099-01")
    assert status.main(["--behind", "noaa_sst"]) == 1
    out = capsys.readouterr().out      # "BEHIND nino12", or "::error::site behind nino12" on GitHub
    assert "BEHIND nino12" in out or "::error::site behind nino12" in out
    monkeypatch.setitem(status.UPSTREAM, "noaa_sst", lambda: site_month)
    assert status.main(["--behind", "noaa_sst"]) == 0


def test_sst_workflow_runs_on_the_4th_records_its_check_and_goes_red_when_behind():
    wf = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "update-sst.yml").read_text()
    import re
    cron = re.search(r"cron: '([^']+)'", wf).group(1).split()
    assert cron[:2] == ["0", "6"]
    assert "4" in cron[2].split(",") and "1" in cron[2].split(",")
    assert "enso.publish --source-type noaa_sst --status" in wf
    step = wf[wf.index("python -m enso.status --behind noaa_sst") - 200:]
    assert "if: always()" in step[:200]
