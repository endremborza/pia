"""Ingest: how a paper becomes a papercli repo.

Three doors — a .tex upload, a PDF (paritex reconstruction, gated by human
acceptance), or `papercli init` adopting a trusted local directory. All converge
on resolve_repo: references parsed, verified online through hallubib, stored as
CSL-JSON, derived files regenerated, everything committed and tagged parse/N.
"""

from collections.abc import Callable
from pathlib import Path

from paritex import (
    MAIN_TEX,
    ORIGINAL,
    REBUILT,
    REFS_BIB,
    REPORT,
    Progress,
    init_project,
    reconstruct,
    refine,
    report_to_dict,
)

from papercli import gitstore, render
from papercli.agentrun import sealed
from papercli.config import Config
from papercli.lock import hold
from papercli.refs import parse_repo_references, resolve, save_store
from papercli.repo import ensure_gitignore, next_n, state, untrack_runtime

OnProgress = Callable[[str], None]


def create_from_tex(dest: Path, tex: str, name: str) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / MAIN_TEX).write_text(tex)
    _init_git(dest, f"papercli ingest: {name}")
    return dest


def create_from_pdf(dest: Path, pdf: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    init_project(pdf, dest)
    _init_git(dest, f"papercli ingest: {ORIGINAL}")
    return dest


def adopt(path: Path) -> Path:
    if not (path / MAIN_TEX).is_file():
        raise FileNotFoundError(f"{path} has no {MAIN_TEX} — not a paper directory")
    if not (path / ".git").is_dir():
        _init_git(path, "papercli init")
        return path
    ensure_gitignore(path)
    untrack_runtime(path)
    return path


def reconstruct_candidate(
    repo: Path, config: Config, on_progress: OnProgress | None = None
) -> dict:
    emit = on_progress or (lambda _: None)
    with hold(repo, "reconstruct"):
        _require_unaccepted(repo)
        if not (repo / ORIGINAL).is_file():
            raise ValueError(f"no committed {ORIGINAL} to reconstruct from")
        return _reconstruct_locked(repo, config, emit)


def _reconstruct_locked(repo: Path, config: Config, emit: OnProgress) -> dict:
    for stale in (MAIN_TEX, REFS_BIB, REPORT, REBUILT):
        (repo / stale).unlink(missing_ok=True)
    emit(f"reconstruction started ({config.reconstruct.name})")
    try:
        with sealed(repo):
            report = reconstruct(
                repo,
                config.reconstruct,
                rounds=config.reconstruct_rounds,
                target=config.reconstruct_target,
                on_event=lambda p: emit(_progress_line(p)),
            )
    except Exception:
        gitstore.discard_all(repo)
        raise
    ratio = report.parity.ratio
    gitstore.commit_all(repo, f"papercli reconstruct: parity {ratio:.1%}")
    emit(f"candidate committed at parity {ratio:.1%} — awaiting your verdict")
    return report_to_dict(report)


def refine_candidate(
    repo: Path,
    config: Config,
    instruction: str | None = None,
    on_progress: OnProgress | None = None,
) -> dict:
    """A further backend pass over the unaccepted candidate, steered by the user."""
    emit = on_progress or (lambda _: None)
    with hold(repo, "refine"):
        _require_unaccepted(repo)
        if not (repo / MAIN_TEX).is_file():
            raise ValueError("no reconstruction candidate to refine")
        emit(f"refine pass started ({config.reconstruct.name})")
        try:
            with sealed(repo):
                report = refine(
                    repo,
                    config.reconstruct,
                    instruction=instruction,
                    rounds=config.reconstruct_rounds,
                    target=config.reconstruct_target,
                    on_event=lambda p: emit(_progress_line(p)),
                )
        except Exception:
            gitstore.discard_all(repo)
            raise
        ratio = report.parity.ratio
        gitstore.commit_all(repo, f"papercli refine: parity {ratio:.1%}")
        emit(f"candidate refined to parity {ratio:.1%} — awaiting your verdict")
        return report_to_dict(report)


def _progress_line(p: Progress) -> str:
    if p.stage == "backend":
        return p.detail if p.detail else f"round {p.round}: agent writing LaTeX"
    if p.stage == "render":
        if p.ok:
            return f"round {p.round}: compiled with tectonic"
        return f"round {p.round}: tectonic failed — feeding the log back to the agent"
    if p.stage == "bib":
        if p.ok:
            return f"round {p.round}: bibliography gate passed"
        return f"round {p.round}: bibliography gate failed — feeding violations back"
    ratio = f"{p.ratio:.1%}" if p.ratio is not None else "?"
    return (
        f"round {p.round}: word-level parity {ratio}, {p.divergences} diverging blocks"
    )


def resolve_repo(
    repo: Path, config: Config, on_progress: OnProgress | None = None
) -> None:
    emit = on_progress or (lambda _: None)
    with hold(repo, "resolve"):
        _resolve_locked(repo, config, emit)


def _resolve_locked(repo: Path, config: Config, emit: OnProgress) -> None:
    references = parse_repo_references(repo)
    emit(f"resolving {len(references)} references online")
    items = resolve(
        references,
        lambda done, total, key, status: emit(f"[{done}/{total}] {key}: {status}"),
    )
    save_store(repo, items)
    tex = render.ensure_input_line((repo / MAIN_TEX).read_text())
    (repo / MAIN_TEX).write_text(tex)
    render.refresh_derived(repo, items, config.style)
    gitstore.commit_all(repo, f"papercli parse: {len(items)} references resolved")
    n = next_n(repo, "parse/")
    gitstore.tag(repo, f"parse/{n}")
    emit(f"parse/{n} tagged")


def accept(repo: Path, config: Config, on_progress: OnProgress | None = None) -> None:
    _require_unaccepted(repo)
    if not (repo / MAIN_TEX).is_file():
        raise ValueError("no reconstruction candidate to accept")
    resolve_repo(repo, config, on_progress)


def _require_unaccepted(repo: Path) -> None:
    """No reconstruction stage may run over an accepted paper — it would replace
    the LaTeX the user signed off on. Past acceptance, changes go through edits."""
    if state(repo).accepted:
        raise ValueError("reconstruction already accepted — use an edit instead")


def _init_git(repo: Path, message: str) -> None:
    ensure_gitignore(repo)
    gitstore.init(repo)
    gitstore.commit_all(repo, message)
