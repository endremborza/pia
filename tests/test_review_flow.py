"""The review run's two guarantees: it cannot edit the paper, and it cannot cite
a source it never fetched. Both are enforced after the agent finishes, so a fake
backend that misbehaves exactly the way a real one might is the whole test."""

import json
import shutil
from pathlib import Path

import pytest
from paritex import Backend

from papercli import gitstore
from papercli.config import Config
from papercli.repo import state
from papercli.review import run_review
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
    "custom": {"status": "Verified", "openalex": "W_known"},
}

FETCHED_RECORD = {
    "source": "openalex",
    "title": "The paper the agent actually found",
    "authors": [{"family": "Priem", "given": "Jason", "literal": ""}],
    "year": 2022,
    "ids": {"openalex": "W_fetched"},
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
        "\\begin{thebibliography}{1}\n\\bibitem{x} Xu, The X paper.\n"
        "\\end{thebibliography}\n"
    )
    (repo / ".gitignore").write_text("*.pdf\n.claude/\n.papercli.lock\n")
    gitstore.init(repo)
    gitstore.commit_all(repo, "ingest")
    gitstore.tag(repo, "parse/1")
    return repo


def _review_xml(source_id: str) -> str:
    return f"""<review paper="T">
  <finding kind="missing-citation" severity="minor" confidence="0.8">
    <section>Introduction</section>
    <claim>the claim this finding is about</claim>
    <source api="openalex" id="{source_id}"/>
    <note>A careful reviewer would raise this.</note>
  </finding>
</review>
"""


def _writes(files: dict[str, str], extra: str = "") -> str:
    """A fake backend: a shell script writing exactly these files, then `extra`."""
    lines = ["mkdir -p reviews/1"]
    for path, content in files.items():
        lines.append(f"cat > {path} <<'PAPERCLI_EOF'\n{content}PAPERCLI_EOF")
    return "\n".join([*lines, extra])


GOOD_LOG = json.dumps({"queries": [{"query": "q", "records": [FETCHED_RECORD]}]})


@needs_tectonic
def test_grounded_review_is_committed_and_tagged(repo: Path):
    run_review(
        repo,
        _config(
            _writes(
                {
                    "reviews/1/review.xml": _review_xml("W_fetched"),
                    "reviews/1/sources.json": GOOD_LOG + "\n",
                }
            )
        ),
    )
    assert state(repo).reviews == [1]
    store = json.loads(gitstore.show(repo, "review/1", "refs.json"))
    assert "priem2022" in store, "the fetched source joins the store under a new key"
    assert store["priem2022"]["custom"]["origin"] == "review/1"


def test_fabricated_source_id_is_rejected(repo: Path):
    """The id is schema-valid and looks real; it is simply not in the fetch log."""
    with pytest.raises(ValidationError, match="W_invented"):
        run_review(
            repo,
            _config(
                _writes(
                    {
                        "reviews/1/review.xml": _review_xml("W_invented"),
                        "reviews/1/sources.json": GOOD_LOG + "\n",
                    }
                )
            ),
        )
    assert state(repo).reviews == []
    assert not gitstore.dirty_paths(repo)


@needs_tectonic
def test_source_already_in_the_store_needs_no_log(repo: Path):
    """Judging a work the paper already cites is grounded by the store itself, so
    a claim-support finding needs no search — and writes no new reference."""
    run_review(repo, _config(_writes({"reviews/1/review.xml": _review_xml("W_known")})))
    assert state(repo).reviews == [1]
    assert set(json.loads(gitstore.show(repo, "review/1", "refs.json"))) == {"x"}


def test_review_that_edits_the_paper_is_rejected(repo: Path):
    """The prompt says findings only; the gate is what makes that true."""
    with pytest.raises(ValidationError, match="disallowed path changed: main.tex"):
        run_review(
            repo,
            _config(
                _writes(
                    {
                        "reviews/1/review.xml": _review_xml("W_fetched"),
                        "reviews/1/sources.json": GOOD_LOG + "\n",
                    },
                    extra="printf ' Slipped in.' >> main.tex",
                )
            ),
        )
    assert state(repo).reviews == []
    assert "Slipped in." not in (repo / "main.tex").read_text()
    assert not gitstore.dirty_paths(repo)


def test_review_that_writes_the_store_is_rejected(repo: Path):
    """Adding a reference is the harness's job, from the log — never the agent's."""
    with pytest.raises(ValidationError, match="disallowed path changed: refs.json"):
        run_review(
            repo,
            _config(
                _writes(
                    {
                        "reviews/1/review.xml": _review_xml("W_fetched"),
                        "reviews/1/sources.json": GOOD_LOG + "\n",
                        "refs.json": json.dumps({"x": ITEM, "ghost2024": {"id": "g"}}),
                    }
                )
            ),
        )
    assert json.loads((repo / "refs.json").read_text()) == {"x": ITEM}
