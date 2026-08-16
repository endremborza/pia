"""All git subprocess calls live here; no other module shells out to git."""

import subprocess
from pathlib import Path

# `.git/` is inside the sandbox the agent writes to, and git never reports its
# own directory as dirty — so no path allowlist can see a change there. Several
# git config keys name commands git runs on our behalf: `core.fsmonitor` fires
# on `git status`, `core.hooksPath` on `git commit`, `diff.external` and
# `diff.*.textconv` on `git diff`. A repo-local config could therefore turn the
# harness into the agent's shell. Command-line settings beat any config file, so
# stating them here covers every call site at once; the diff pair are flags
# rather than `-c` keys because an empty `diff.external` is a command git tries
# to exec, not an absent one. agentrun.sealed catches the rest of the class.
_SEALED = (
    "-c",
    "core.fsmonitor=false",
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "protocol.ext.allow=never",
)
_NO_DIFF_PROGRAMS = ("--no-ext-diff", "--no-textconv")


class GitError(Exception):
    def __init__(self, argv: list[str], log: str) -> None:
        super().__init__(f"git {' '.join(argv)} failed:\n{log}")
        self.log = log


def git(repo: Path, *args: str) -> str:
    argv = ["git", *_SEALED, *args]
    proc = subprocess.run(argv, cwd=repo, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise GitError(list(args), (proc.stderr + proc.stdout).strip())
    return proc.stdout


def init(repo: Path) -> None:
    git(repo, "init", "--quiet", "--initial-branch=main")
    git(repo, "config", "user.name", "papercli")
    git(repo, "config", "user.email", "papercli@localhost")


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "--allow-empty", "-m", message)
    return head(repo)


def head(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD").strip()


def current_branch(repo: Path) -> str:
    return git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()


def tag(repo: Path, name: str) -> None:
    git(repo, "tag", name)


def tags(repo: Path) -> list[str]:
    out = git(repo, "tag", "--list")
    return [t for t in out.splitlines() if t]


def show(repo: Path, ref: str, path: str) -> str:
    return git(repo, "show", f"{ref}:{path}")


def ls_tree(repo: Path, ref: str) -> list[str]:
    out = git(repo, "ls-tree", "-r", "--name-only", ref)
    return [p for p in out.splitlines() if p]


def create_branch(repo: Path, name: str, start: str = "main") -> None:
    git(repo, "checkout", "--quiet", "-b", name, start)


def checkout(repo: Path, name: str) -> None:
    git(repo, "checkout", "--quiet", name)


def delete_branch(repo: Path, name: str) -> None:
    git(repo, "branch", "--quiet", "-D", name)


def branches(repo: Path) -> list[str]:
    out = git(repo, "branch", "--format=%(refname:short)")
    return [b for b in out.splitlines() if b]


def merge_ff(repo: Path, branch: str) -> None:
    git(repo, "merge", "--quiet", "--ff-only", branch)


def diff(repo: Path, base: str, target: str = "HEAD") -> str:
    return git(repo, "diff", *_NO_DIFF_PROGRAMS, f"{base}..{target}")


def changed_paths(repo: Path, base: str, target: str = "HEAD") -> list[str]:
    out = git(repo, "diff", *_NO_DIFF_PROGRAMS, "--name-only", f"{base}..{target}")
    return [p for p in out.splitlines() if p]


def dirty_paths(repo: Path) -> list[str]:
    """Every changed path, one file per entry.

    `-uall` matters: by default git collapses a wholly-new directory to `dir/`,
    which a gate matching on a `reviews/N/` prefix would read as out of bounds.
    """
    out = git(repo, "status", "--porcelain", "--untracked-files=all")
    return [line[3:] for line in out.splitlines() if line]


def untrack(repo: Path, paths: list[str]) -> None:
    """Drop paths from the index, leaving the working tree alone; no-op if untracked."""
    git(repo, "rm", "-r", "--cached", "--force", "--quiet", "--ignore-unmatch", *paths)


def discard_all(repo: Path) -> None:
    git(repo, "reset", "--hard", "--quiet")
    git(repo, "clean", "-fdq")


def log_oneline(repo: Path, limit: int = 50) -> list[str]:
    out = git(repo, "log", "--oneline", f"-{limit}")
    return [line for line in out.splitlines() if line]
