"""In-process background runs, one per repo. Progress is streamed state, never persisted."""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

_log = logging.getLogger("papercli.run")
_MAX_RUNS = 200


@dataclass
class Run:
    paper_id: str
    kind: str
    status: str = "running"
    progress: list[str] = field(default_factory=list)
    error: str | None = None
    started: float = field(default_factory=time.monotonic)
    finished: float | None = None

    def emit(self, line: str) -> None:
        self.progress.append(line)
        _log.info("[%s %s] %s", self.paper_id, self.kind, line)

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "status": self.status,
            "progress": self.progress[-50:],
            "error": self.error,
            "elapsed": round((self.finished or time.monotonic()) - self.started),
        }


class RunInProgress(Exception):
    pass


class Runs:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._lock = threading.Lock()

    def start(self, paper_id: str, kind: str, task: Callable[[Run], object]) -> Run:
        with self._lock:
            current = self._runs.get(paper_id)
            if current is not None and current.status == "running":
                raise RunInProgress(f"a {current.kind} run is already in progress")
            run = Run(paper_id=paper_id, kind=kind)
            self._runs[paper_id] = run
            self._evict()
        _log.info("[%s %s] run started", paper_id, kind)

        def _target() -> None:
            try:
                task(run)
                run.status = "done"
                _log.info("[%s %s] run done", paper_id, kind)
            except Exception as err:  # noqa: BLE001 — thread boundary: every failure becomes run state
                run.error = str(err)
                run.status = "error"
                _log.warning("[%s %s] run failed: %s", paper_id, kind, err)
            finally:
                run.finished = time.monotonic()

        threading.Thread(target=_target, daemon=True).start()
        return run

    def get(self, paper_id: str) -> Run | None:
        return self._runs.get(paper_id)

    def _evict(self) -> None:
        """Progress is streamed state, not history — drop the oldest finished runs
        rather than growing a dict with every paper the process has ever seen."""
        excess = len(self._runs) - _MAX_RUNS
        if excess <= 0:
            return
        finished = sorted(
            (run for run in self._runs.values() if run.status != "running"),
            key=lambda run: run.finished or run.started,
        )
        for run in finished[:excess]:
            del self._runs[run.paper_id]
