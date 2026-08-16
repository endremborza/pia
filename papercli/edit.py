"""Natural-language editing: an agent run on a proposal branch, gated wholesale.

The agent edits main.tex directly in the sandbox; afterwards code enforces the
contract — allowed paths, tectonic compile, citation validator — and only a
fully passing run is committed on the branch. Approve is a fast-forward merge,
reject deletes the branch; main only ever advances by approval.
"""

import json
from collections.abc import Callable
from pathlib import Path

from hallubib import Status, to_csl
from paritex import MAIN_TEX, REFS_BIB

from papercli import gitstore, render
from papercli.agentrun import run
from papercli.config import Config
from papercli.lock import hold
from papercli.prompts import EDIT
from papercli.refs import gen_key, load_store, save_store
from papercli.repo import (
    BIBLIOGRAPHY_TEX,
    PROPOSAL_PREFIX,
    REFS_JSON,
    RepoState,
    state,
)
from papercli.search import logged_ids, record_from_dict, store_ids
from papercli.validator import PaperState, ValidationError, check_edit

ALLOWED_PATHS = frozenset({MAIN_TEX, REFS_JSON, REFS_BIB, BIBLIOGRAPHY_TEX})
_EDIT_SOURCES = ".claude/edit-sources.json"


def run_edit(
    repo: Path,
    command: str,
    config: Config,
    on_progress: Callable[[str], None] | None = None,
) -> str:
    emit = on_progress or (lambda _: None)
    with hold(repo, "edit"):
        if state(repo).proposal is not None:
            raise ValidationError(
                ["a proposal is already open — approve or reject it first"]
            )
        branch = _branch_name(command)
        before = _paper_state(repo, "main")
        gitstore.create_branch(repo, branch, "main")
        start = gitstore.head(repo)
        emit(f"agent run started on {branch} ({config.agent.name})")
        try:
            run(
                repo,
                config.agent,
                EDIT.format(command=command, sources_json=_EDIT_SOURCES),
                on_line=emit,
            )
            emit("agent run finished, checking gates")
            _enforce_gates(repo, before, start, config)
        except Exception:
            gitstore.discard_all(repo)
            gitstore.checkout(repo, "main")
            gitstore.delete_branch(repo, branch)
            raise
        gitstore.commit_all(repo, f"papercli do: {command}")
        gitstore.checkout(repo, "main")
        emit(f"proposal ready on {branch}")
        return branch


def _enforce_gates(repo: Path, before: PaperState, start: str, config: Config) -> None:
    if gitstore.head(repo) != start:
        raise ValidationError(["agent moved HEAD — history manipulation rejected"])
    after = _paper_state_worktree(repo)
    check_edit(before, after, gitstore.dirty_paths(repo), ALLOWED_PATHS, _fetched(repo))
    render.refresh_derived(repo, after.store, config.style)
    render.build(repo)


def _fetched(repo: Path) -> frozenset[str]:
    """Every source id this run actually pulled from an API, per its own log."""
    return frozenset(logged_ids(repo / _EDIT_SOURCES))


def proposal_diff(repo: Path) -> dict:
    proposal = state(repo).proposal
    if proposal is None:
        raise ValidationError(["no open proposal"])
    message = gitstore.git(repo, "log", "-1", "--format=%s", proposal).strip()
    return {
        "branch": proposal,
        "command": message.removeprefix("papercli do: "),
        "diff": gitstore.diff(repo, "main", proposal),
    }


def approve(repo: Path) -> None:
    """Under the lock: both verdicts check out main, and a run in flight is on
    the proposal branch — the UI disables the buttons, which is not enforcement."""
    with hold(repo, "approve"):
        proposal = _require_proposal(state(repo))
        gitstore.checkout(repo, "main")
        gitstore.merge_ff(repo, proposal)
        gitstore.delete_branch(repo, proposal)


def reject(repo: Path) -> None:
    with hold(repo, "reject"):
        proposal = _require_proposal(state(repo))
        gitstore.checkout(repo, "main")
        gitstore.delete_branch(repo, proposal)


def validate_worktree(repo: Path) -> list[str]:
    """The agent's self-check: the same gate the harness runs, as a report."""
    try:
        check_edit(
            _paper_state(repo, "HEAD"),
            _paper_state_worktree(repo),
            gitstore.dirty_paths(repo),
            ALLOWED_PATHS,
            _fetched(repo),
        )
    except ValidationError as err:
        return err.violations
    return []


def add_ref(repo: Path, source_id: str, log_path: Path, config: Config) -> str:
    """Move a fetched record from the run's log into the store, verbatim; print the key."""
    items = load_store(repo)
    known = store_ids(items)
    if source_id in known:
        return known[source_id]
    fetched = logged_ids(_in_repo(repo, log_path))
    if source_id not in fetched:
        raise ValidationError([f"source id not in fetch log: {source_id}"])
    record_dict = fetched[source_id]
    key = gen_key(record_dict, set(items))
    item = to_csl(record_from_dict(record_dict), key)
    item["custom"] = dict(item.get("custom", {})) | {"status": str(Status.VERIFIED)}
    items[key] = item
    save_store(repo, items)
    render.refresh_derived(repo, items, config.style)
    return key


def _in_repo(repo: Path, path: Path) -> Path:
    """A fetch log is a sandbox artifact; never ground a reference in one outside it."""
    resolved = (repo / path).resolve()
    if not resolved.is_relative_to(repo.resolve()):
        raise ValidationError([f"log path outside the repo: {path}"])
    return resolved


def _require_proposal(repo_state: RepoState) -> str:
    if repo_state.proposal is None:
        raise ValidationError(["no open proposal"])
    return repo_state.proposal


def _paper_state(repo: Path, ref: str) -> PaperState:
    tex = gitstore.show(repo, ref, MAIN_TEX)
    try:
        store = json.loads(gitstore.show(repo, ref, REFS_JSON))
    except gitstore.GitError:
        store = {}
    return PaperState(tex=tex, store=store)


def _paper_state_worktree(repo: Path) -> PaperState:
    return PaperState(tex=(repo / MAIN_TEX).read_text(), store=load_store(repo))


def _branch_name(command: str) -> str:
    slug = "-".join(
        "".join(c for c in word.lower() if c.isalnum()) for word in command.split()[:4]
    ).strip("-")
    return f"{PROPOSAL_PREFIX}{slug or 'edit'}"
