"""Fetch one source type, rebuild, test, commit and push: the update step
shared by both writers of main.

    python -m enso.publish --source-type noaa_sst             # GitHub Actions, every 5 days
    python -m enso.publish --source-type uhslc --status       # this PC, Task Scheduler
    python -m enso.publish --source-type uhslc --no-push      # local trial: commit only

Two writers share main: CI for SST, a PC for sea level. Each one changes only
its own files:

* data/series/<key>.csv for the datasets of its source type,
* data/status/<source type>.json (with --status),
* docs/, which is shared but is a pure function of the committed code and
  data, so either writer can rebuild it from scratch (the footer's
  "data fetched" date is the latest date over all records, for example).

Any other change in the working tree stops the run before it commits.

Publishing: ``git pull --rebase``, rebuild docs/ (the other writer's data may
have arrived), amend, push. If the rebase conflicts (both rebuilt docs/) or
the push is rejected (the other writer pushed in between), it retries once:
reset to the remote branch, put its own data files back, rebuild, commit,
push. A second failure stops loudly with exit code 2 and leaves the
remote untouched.

Exit codes: 0 published (or nothing new), 1 published but some downloads
failed (they keep their committed records), 2 nothing published.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from enso import series, status
from enso.config import ROOT, Config, load_config

EXIT_OK, EXIT_PARTIAL, EXIT_FAILED = 0, 1, 2


class PublishError(RuntimeError):
    pass


def log(msg: str) -> None:
    print(msg, flush=True)


class Publisher:
    """One update run. Tests override fetch, build, test and message."""

    def __init__(self, cfg: Config, source_type: str, root: Path = ROOT,
                 write_status: bool = False, run_tests: bool = True, push: bool = True):
        self.cfg, self.source_type, self.root = cfg, source_type, Path(root)
        self.write_status, self.run_tests, self.push = write_status, run_tests, push
        self.keys = [d.key for d in cfg.datasets if d.source["type"] == source_type]
        if not self.keys:
            raise PublishError(f"no dataset has source type {source_type!r}")

    # -- the parts tests replace ------------------------------------------

    def fetch(self) -> list[tuple[str, str]]:
        from enso import fetch
        return fetch.fetch_many(self.keys, self.cfg)

    def build(self) -> None:
        from enso import build
        build.build(self.root / "docs", self.cfg)

    def test(self) -> bool:
        cmd = [sys.executable, "-m", "pytest", "-q", "-m", "not browser"]
        return self._run(cmd).returncode == 0

    def message(self) -> str:
        group = self.cfg.dataset(self.keys[0]).group.label
        last = max(series.read(k, self.root / "data" / "series").last_period for k in self.keys)
        return f"data: {group} through {last} [auto]"

    # -- own files ----------------------------------------------------------

    @property
    def data_paths(self) -> list[str]:
        paths = [f"data/series/{k}.csv" for k in self.keys]
        if self.write_status:
            paths.append(f"data/status/{self.source_type}.json")
        return paths

    @property
    def own_paths(self) -> list[str]:
        return [*self.data_paths, "docs"]

    def _owned(self, path: str) -> bool:
        return path in self.data_paths or path == "docs" or path.startswith("docs/")

    # -- git ----------------------------------------------------------------

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        p = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        for line in (p.stdout + p.stderr).splitlines():
            if line.strip():
                log(f"  {line}")
        return p

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        log(f"> git {' '.join(args)}")
        p = self._run(["git", *args])
        if check and p.returncode != 0:
            raise PublishError(f"git {' '.join(args)} failed")
        return p

    def _changes(self) -> list[str]:
        out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"],
                             cwd=self.root, capture_output=True, text=True, check=True).stdout
        return [line[3:].strip().strip('"') for line in out.splitlines() if line.strip()]

    def _staged(self) -> bool:
        return subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=self.root).returncode != 0

    def _ahead(self) -> int:
        p = subprocess.run(["git", "rev-list", "--count", "@{u}..HEAD"], cwd=self.root,
                           capture_output=True, text=True)
        return int(p.stdout.strip() or 0) if p.returncode == 0 else 0

    def _restore(self) -> None:
        """Put the own paths back as committed, so the next run starts clean."""
        self.git("checkout", "--", *self._tracked(self.own_paths), check=False)
        self.git("clean", "-fdq", "--", *self.own_paths, check=False)

    def _tracked(self, paths: list[str]) -> list[str]:
        tracked = subprocess.run(["git", "ls-files", "--", *paths], cwd=self.root,
                                 capture_output=True, text=True).stdout.splitlines()
        return [p for p in paths if p in tracked or any(t.startswith(p + "/") for t in tracked)]

    def _commit(self) -> bool:
        self.git("add", "-A", "--", *self.own_paths)
        if not self._staged():
            return False
        self.git("commit", "-m", self.message())
        return True

    # -- the run ------------------------------------------------------------

    def run(self) -> int:
        if self._changes():
            raise PublishError("the working tree has uncommitted changes:\n  "
                               + "\n  ".join(self._changes()))
        if self.push:
            upstream = subprocess.run(["git", "rev-parse", "--abbrev-ref", "@{u}"], cwd=self.root,
                                      capture_output=True, text=True)
            if upstream.returncode != 0:
                raise PublishError("the branch has no upstream to push to; "
                                   "run 'git push -u origin main' once")
            if self.git("pull", "--rebase", check=False).returncode != 0:
                self.git("rebase", "--abort", check=False)
                raise PublishError("git pull --rebase failed before the update; "
                                   "a local commit conflicts with the remote")

        results = self.fetch()
        failed = [k for k, line in results if line.startswith("FAILED")]
        if len(failed) == len(results):
            self._restore()
            raise PublishError("every download failed: " + ", ".join(failed))
        if self.write_status:
            status.record(self.source_type, results, directory=self.root / "data" / "status")

        self.build()
        if self.run_tests and not self.test():
            self._restore()
            raise PublishError("the tests failed on the new data; nothing committed")

        stray = [p for p in self._changes() if not self._owned(p)]
        if stray:
            self._restore()
            raise PublishError("the update changed files it does not own:\n  " + "\n  ".join(stray))

        if self._commit():
            log("committed")
        else:
            log("nothing new: no commit")
        if self.push and self._ahead():
            self._publish()
        return EXIT_PARTIAL if failed else EXIT_OK

    def _publish(self) -> None:
        saved = {p: (self.root / p).read_bytes() for p in self.data_paths if (self.root / p).exists()}
        if self.git("pull", "--rebase", check=False).returncode == 0:
            if not self._ahead():         # the remote already had our change
                return
            self.build()                  # docs/ for both writers' data
            self.git("add", "-A", "--", "docs")
            if self._staged():
                self.git("commit", "--amend", "--no-edit")
            if self.git("push", check=False).returncode == 0:
                return
            log("push rejected: retrying once")
        else:
            self.git("rebase", "--abort", check=False)
            log("rebase conflict: retrying once")

        # Retry: start from the remote, re-apply only our data, rebuild.
        self.git("fetch")
        self.git("reset", "--hard", "@{u}")
        for p, data in saved.items():
            (self.root / p).parent.mkdir(parents=True, exist_ok=True)
            (self.root / p).write_bytes(data)
        self.build()
        if not self._commit():
            log("nothing left to publish after the rebuild")
            return
        if self.git("push", check=False).returncode != 0:
            raise PublishError("git push failed twice. The new commit is kept locally; "
                               "see README, 'Recovery'")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-type", required=True)
    ap.add_argument("--status", action="store_true",
                    help="record download dates in data/status/<source type>.json")
    ap.add_argument("--no-push", action="store_true", help="commit locally; no pull, no push")
    ap.add_argument("--skip-tests", action="store_true")
    args = ap.parse_args(argv)
    try:
        pub = Publisher(load_config(), args.source_type, write_status=args.status,
                        run_tests=not args.skip_tests, push=not args.no_push)
        code = pub.run()
    except PublishError as exc:
        prefix = "::error::" if "GITHUB_ACTIONS" in os.environ else ""
        first, *rest = str(exc).splitlines()
        print(f"{prefix}PUBLISH FAILED: {first}", *rest, sep="\n", file=sys.stderr, flush=True)
        return EXIT_FAILED
    if code == EXIT_PARTIAL:
        log("published, but some downloads failed (their committed records were kept)")
    return code


if __name__ == "__main__":
    sys.exit(main())
