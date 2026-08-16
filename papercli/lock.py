"""One run per repo: a lock file in the repo, shared by CLI and server processes.

The file records the holding pid, and a lock whose holder is gone is broken
rather than obeyed — otherwise a killed server leaves the repo busy forever and
the recorded pid is decoration.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from papercli.repo import LOCK_FILE

_ATTEMPTS = 3


class RepoBusy(Exception):
    def __init__(self, holder: str) -> None:
        super().__init__(f"someone is currently working on this repo ({holder})")
        self.holder = holder


@contextmanager
def hold(repo: Path, task: str) -> Iterator[None]:
    path = repo / LOCK_FILE
    _acquire(path, task)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def _acquire(path: Path, task: str) -> None:
    for _ in range(_ATTEMPTS):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            holder = _holder(path)
            if holder is None:
                continue  # released between our open and our read
            pid, held_task = holder
            if _alive(pid):
                raise RepoBusy(held_task) from None
            path.unlink(missing_ok=True)  # stale: the holder died
            continue
        with os.fdopen(fd, "w") as handle:
            handle.write(f"{os.getpid()} {task}")
        return
    raise RepoBusy("the lock keeps changing hands")


def _holder(path: Path) -> tuple[int, str] | None:
    try:
        text = path.read_text().strip()
    except FileNotFoundError:
        return None
    pid, _, held_task = text.partition(" ")
    return (int(pid) if pid.isdigit() else 0, held_task or "unknown task")


def _alive(pid: int) -> bool:
    if pid <= 0:
        return True  # unreadable holder: assume the lock is real
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by another user
    return True
