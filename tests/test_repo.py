import os
import subprocess
import sys
from pathlib import Path

import pytest

from papercli import gitstore
from papercli.ingest import adopt
from papercli.lock import RepoBusy, hold
from papercli.repo import LOCK_FILE


@pytest.fixture()
def adopted(tmp_path: Path) -> Path:
    """A real paper directory that is already a git repo with its own .gitignore."""
    repo = tmp_path / "paper"
    repo.mkdir()
    (repo / "main.tex").write_text("\\documentclass{article}\n")
    (repo / ".gitignore").write_text("*.aux\n")
    gitstore.init(repo)
    gitstore.commit_all(repo, "the author's own history")
    return repo


def test_adopt_ignores_runtime_files_in_an_existing_repo(adopted: Path):
    adopt(adopted)
    gitstore.commit_all(adopted, "papercli init")
    (adopted / ".claude" / "skills").mkdir(parents=True)
    (adopted / LOCK_FILE).write_text("1 edit")
    (adopted / "main.pdf").write_bytes(b"%PDF")
    assert gitstore.dirty_paths(adopted) == []
    assert "*.aux" in (adopted / ".gitignore").read_text()


def test_adopt_untracks_a_lock_file_an_earlier_run_committed(adopted: Path):
    (adopted / LOCK_FILE).write_text("1 resolve")
    gitstore.commit_all(adopted, "captured the lock file")
    assert LOCK_FILE in gitstore.ls_tree(adopted, "HEAD")
    adopt(adopted)
    gitstore.commit_all(adopted, "papercli init")
    assert LOCK_FILE not in gitstore.ls_tree(adopted, "HEAD")


def _reaped_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", ""])
    proc.wait()
    return proc.pid


def test_live_lock_is_respected(tmp_path: Path):
    (tmp_path / LOCK_FILE).write_text(f"{os.getpid()} resolve")
    with pytest.raises(RepoBusy, match="resolve"), hold(tmp_path, "review"):
        pass


def test_stale_lock_is_broken(tmp_path: Path):
    (tmp_path / LOCK_FILE).write_text(f"{_reaped_pid()} resolve")
    with hold(tmp_path, "review"):
        assert (tmp_path / LOCK_FILE).read_text() == f"{os.getpid()} review"
    assert not (tmp_path / LOCK_FILE).exists()
