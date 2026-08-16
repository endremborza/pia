import json
import os
import shutil
from pathlib import Path

import pytest
from paritex import Backend

from papercli import gitstore
from papercli.config import Config
from papercli.edit import approve, proposal_diff, reject, run_edit
from papercli.lock import RepoBusy
from papercli.repo import LOCK_FILE, state
from papercli.validator import ValidationError

needs_tectonic = pytest.mark.skipif(
    shutil.which("tectonic") is None, reason="tectonic not installed"
)

TEX = """\\documentclass{article}
\\begin{document}
\\title{T}\\maketitle
Grounded claim \\cite{x}.
\\input{bibliography}
\\end{document}
"""

ITEM = {
    "id": "x",
    "type": "article-journal",
    "title": "The X paper",
    "author": [{"family": "Xu", "given": "A"}],
    "issued": {"date-parts": [[2020]]},
    "custom": {"status": "Verified"},
}


def _config(script: str) -> Config:
    backend = Backend(name="fake", argv=("sh", "-c", script))
    return Config(
        projects_root=Path("/tmp"),
        style=None,
        agent=backend,
        reconstruct=backend,
        reconstruct_rounds=1,
        reconstruct_target=1.0,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "paper"
    repo.mkdir()
    (repo / "main.tex").write_text(TEX)
    (repo / "refs.json").write_text(json.dumps({"x": ITEM}))
    (repo / "bibliography.tex").write_text(
        "\\begin{thebibliography}{1}\n\\bibitem{x} Xu, The X paper.\n\\end{thebibliography}\n"
    )
    (repo / ".gitignore").write_text("*.pdf\n.claude/\n.papercli.lock\n")
    gitstore.init(repo)
    gitstore.commit_all(repo, "ingest")
    gitstore.tag(repo, "parse/1")
    return repo


@needs_tectonic
def test_good_edit_becomes_proposal_and_merges(repo: Path):
    run_edit(repo, "add a sentence", _config("printf ' Another sentence.' >> main.tex"))
    st = state(repo)
    assert st.proposal is not None
    diff = proposal_diff(repo)
    assert "Another sentence." in diff["diff"]
    assert diff["command"] == "add a sentence"
    before = gitstore.head(repo)
    approve(repo)
    assert state(repo).proposal is None
    assert gitstore.head(repo) != before
    assert "Another sentence." in (repo / "main.tex").read_text()


def test_dropped_cite_rejected_and_cleaned(repo: Path):
    with pytest.raises(ValidationError, match="citation dropped: x"):
        run_edit(
            repo,
            "remove the citation",
            _config("sed -i 's/\\\\cite{x}//' main.tex"),
        )
    assert state(repo).proposal is None
    assert gitstore.current_branch(repo) == "main"
    assert not gitstore.dirty_paths(repo)


def test_disallowed_file_rejected(repo: Path):
    with pytest.raises(ValidationError, match="disallowed path"):
        run_edit(repo, "hack", _config("echo pwned > evil.txt"))
    assert state(repo).proposal is None


INVENT_REFERENCE = """
python3 - <<'EOF'
import json
store = json.load(open('refs.json'))
store['ghost2024'] = {
    'id': 'ghost2024',
    'title': 'A paper nobody wrote',
    'custom': {'doi': '10.0000/ghost', 'status': 'Verified'},
}
json.dump(store, open('refs.json', 'w'))
EOF
printf ' As shown elsewhere \\\\cite{ghost2024}.' >> main.tex
"""


def test_invented_reference_rejected(repo: Path):
    """The store is an allowed path, so grounding has to be checked, not assumed."""
    with pytest.raises(ValidationError, match="not in the fetch log: ghost2024"):
        run_edit(repo, "cite something new", _config(INVENT_REFERENCE))
    assert state(repo).proposal is None
    assert "ghost2024" not in (repo / "refs.json").read_text()


@needs_tectonic
def test_reject_deletes_branch(repo: Path):
    run_edit(repo, "add text", _config("printf ' More.' >> main.tex"))
    reject(repo)
    assert state(repo).proposal is None
    assert "More." not in gitstore.show(repo, "main", "main.tex")


POISON_GIT_CONFIG = """
printf '\\n[diff]\\n\\texternal = /bin/sh -c "touch pwned; exit 0"\\n' >> .git/config
printf ' A harmless sentence.' >> main.tex
"""


def test_git_config_write_is_rejected(repo: Path):
    """`.git/` is inside the sandbox and never shows up as a dirty path, so no
    allowlist can see this — but `diff.external` is a command the harness runs."""
    with pytest.raises(ValidationError, match=r"modified \.git/config"):
        run_edit(repo, "poison the config", _config(POISON_GIT_CONFIG))
    assert "diff" not in (repo / ".git" / "config").read_text()
    assert not (repo / "pwned").exists()
    assert state(repo).proposal is None


def test_approve_and_reject_respect_the_repo_lock(repo: Path):
    (repo / LOCK_FILE).write_text(f"{os.getpid()} edit")
    try:
        with pytest.raises(RepoBusy):
            approve(repo)
        with pytest.raises(RepoBusy):
            reject(repo)
    finally:
        (repo / LOCK_FILE).unlink()
