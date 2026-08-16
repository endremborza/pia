"""The one module that invokes an LLM: materialize the sandbox toolbox, run the backend.

Headless `claude -p` today, the Agent SDK as a drop-in — both behind paritex's
backend spec, selected by the config's [agent] table. Nothing outside this module
knows which backend runs.
"""

import json
import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from importlib.resources import as_file, files
from pathlib import Path
from typing import Final

from paritex import Backend, run_backend

from papercli.validator import ValidationError

# The agent's tool boundary, stated once. `--allowedTools` in the backend argv is
# what enforces it; the settings.json copy is advisory only — a workspace the
# agent has not been told to trust ignores project permissions — so both are
# derived from these tuples instead of drifting into two different policies.
AGENT_TOOLS: Final = ("Bash(tectonic:*)", "Bash(papercli:*)")
DENIED_TOOLS: Final = ("Bash(git push:*)", "Bash(git commit:*)")

_SETTINGS = {"permissions": {"allow": list(AGENT_TOOLS), "deny": list(DENIED_TOOLS)}}


def materialize_toolbox(repo: Path) -> None:
    claude_dir = repo / ".claude"
    shutil.rmtree(claude_dir, ignore_errors=True)
    (claude_dir / "skills").mkdir(parents=True)
    (claude_dir / "settings.json").write_text(json.dumps(_SETTINGS, indent=1))
    skills = files("papercli").joinpath("data/skills")
    with as_file(skills) as skills_path:
        for skill in Path(skills_path).iterdir():
            shutil.copytree(skill, claude_dir / "skills" / skill.name)


@contextmanager
def sealed(repo: Path) -> Iterator[None]:
    """`.git/config` is out of bounds for a run, and unlike every other path that
    cannot be expressed as an allowlist rule — git does not report its own
    directory as dirty, so no diff gate can see a change there.

    It matters because several config keys name commands git runs for us:
    `diff.external`, `core.fsmonitor`, `core.hooksPath`, a `filter.*.clean`
    driver that `git add` invokes. gitstore forces the known ones on the command
    line; this catches the rest of the class. The file is restored before the
    rejection propagates, so the caller's rollback never runs against a poisoned
    config either.
    """
    path = repo / ".git" / "config"
    before = path.read_bytes()
    try:
        yield
    finally:
        if path.read_bytes() != before:
            path.write_bytes(before)
            raise ValidationError(["the run modified .git/config"])


def run(
    repo: Path,
    backend: Backend,
    prompt: str,
    on_line: Callable[[str], None] | None = None,
) -> None:
    materialize_toolbox(repo)
    with sealed(repo):
        run_backend(backend, prompt, repo, on_line)
