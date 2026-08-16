"""Papercli repo layout and state — paritex's produced files plus this app's overlay."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from paritex import MAIN_TEX, ORIGINAL, REPORT

from papercli import gitstore
from papercli.latex import parse_latex

REFS_JSON = "refs.json"
REVIEWS = "reviews"
BIBLIOGRAPHY_TEX = "bibliography.tex"
REVIEW_XML = "review.xml"
REVIEW_TEX = "review.tex"
SOURCES_JSON = "sources.json"
LOCK_FILE = ".papercli.lock"
PROPOSAL_PREFIX = "proposal/"

GITIGNORE_LINES = ("*.pdf", f"!{ORIGINAL}", ".claude/", LOCK_FILE)
RUNTIME_PATHS = (LOCK_FILE, ".claude")


def ensure_gitignore(repo: Path) -> None:
    """papercli's runtime files must be ignored in every repo, adopted ones included.

    An adopted directory usually already has a .gitignore, so missing lines are
    appended rather than the file replaced — if `.claude/` and the lock file stay
    unignored they surface as dirty paths and the edit gate rejects every run.
    """
    path = repo / ".gitignore"
    existing = path.read_text().splitlines() if path.is_file() else []
    missing = [line for line in GITIGNORE_LINES if line not in existing]
    if not missing:
        return
    block = ["", "# papercli", *missing] if existing else list(missing)
    path.write_text("\n".join([*existing, *block]).strip("\n") + "\n")


def untrack_runtime(repo: Path) -> None:
    """Drop runtime files a pre-papercli commit may have captured from the index."""
    gitstore.untrack(repo, list(RUNTIME_PATHS))


@dataclass(frozen=True)
class RepoState:
    accepted: bool
    from_pdf: bool
    parse_rounds: int
    reviews: list[int]
    exports: int
    proposal: str | None
    busy: bool


def is_repo(path: Path) -> bool:
    return (path / ".git").is_dir() and (path / MAIN_TEX).is_file()


def state(repo: Path) -> RepoState:
    tags = gitstore.tags(repo)
    return RepoState(
        accepted=any(t.startswith("parse/") for t in tags),
        from_pdf=(repo / ORIGINAL).is_file(),
        parse_rounds=_count(tags, "parse/"),
        reviews=sorted(_tag_ns(tags, "review/")),
        exports=_count(tags, "export/"),
        proposal=next(
            (b for b in gitstore.branches(repo) if b.startswith(PROPOSAL_PREFIX)),
            None,
        ),
        busy=(repo / LOCK_FILE).exists(),
    )


def next_n(repo: Path, prefix: str) -> int:
    return max(_tag_ns(gitstore.tags(repo), prefix), default=0) + 1


def review_dir(repo: Path, n: int) -> Path:
    return repo / REVIEWS / str(n)


def parity_report(repo: Path) -> dict | None:
    report = repo / REPORT
    return json.loads(report.read_text()) if report.is_file() else None


def paper_view(tex: str, items: dict[str, dict] | None) -> dict:
    """Parse view with dangling/uncited computed against the store once one exists."""
    view = asdict(parse_latex(tex))
    if items is not None:
        cited = set(view["citations"])
        view["unresolved"] = sorted(cited - set(items))
        view["uncited"] = sorted(set(items) - cited)
        view["references"] = []
    return view


def _tag_ns(tags: list[str], prefix: str) -> list[int]:
    return [int(t.removeprefix(prefix)) for t in tags if t.startswith(prefix)]


def _count(tags: list[str], prefix: str) -> int:
    return len(_tag_ns(tags, prefix))
