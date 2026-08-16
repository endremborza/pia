"""Layered config: defaults < user config.toml < repo pyproject [tool.papercli] < flags.

The PAPERCLI_CONFIG env var replaces the user-layer file path (tests point it at a
throwaway toml). papercli never writes config into a repo and never searches upward:
the only repo-level source is a pyproject.toml at the papercli repo's root.

Agent selection uses paritex's backend spec — one AI-invocation schema in the
system. Builtins: claude-code (default; the box's Claude Code login, Anthropic
auth env scrubbed so an exported API key can never bill silently) and claude-api
(requires ANTHROPIC_API_KEY, spends API credits deliberately). Pick with
`[agent] backend = "..."`, define others under `[agent.backends.<name>]`, or
override per-shell with PAPERCLI_AGENT_BACKEND. `model`/`effort` under [agent]
and [reconstruct] tune the claude builtins: [agent] defaults to the box's Claude
Code settings, [reconstruct] to sonnet/medium — reconstruction is transcription,
so a fast model plus the parity gate beats a slow one; custom backends own their
argv and ignore both keys.

Service identity comes from env first (the repo's gitignored .env, loaded by the
launcher: `uv run --env-file .env ...`), then config keys: HALLUBIB_MAILTO,
OPENALEX_API_KEY, S2_API_KEY. See .env.sample for the free-tier setup.
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hallubib import configure
from paritex import BUILTIN, Backend, claude_backend, parse_backend

from papercli.agentrun import AGENT_TOOLS

_USER_CONFIG = Path("~/.config/papercli/config.toml")
_PROJECTS_ROOT = Path("~/.local/share/papercli/projects")

_CLAUDE_BUILTINS = ("claude-code", "claude-api", "claude-gen")
_RECONSTRUCT_MODEL = "sonnet"
_RECONSTRUCT_EFFORT = "medium"


def _claude(name: str, model: str | None, effort: str | None) -> Backend:
    return claude_backend(
        name,
        auth="api" if name == "claude-api" else "login",
        allowed_tools=",".join(AGENT_TOOLS),
        mode="generate" if name == "claude-gen" else "agent",
        model=model,
        effort=effort,
    )


@dataclass(frozen=True)
class Config:
    projects_root: Path
    style: str | None
    agent: Backend
    reconstruct: Backend
    reconstruct_rounds: int
    reconstruct_target: float


def user_config_path() -> Path:
    override = os.environ.get("PAPERCLI_CONFIG")
    return Path(override) if override else _USER_CONFIG.expanduser()


def load_config(repo: Path | None = None, **flags: Any) -> Config:
    layers: list[tuple[dict[str, Any], Path]] = []
    user_path = user_config_path()
    if user_path.is_file():
        layers.append((tomllib.loads(user_path.read_text()), user_path.parent))
    if repo is not None:
        pyproject = repo / "pyproject.toml"
        if pyproject.is_file():
            table = tomllib.loads(pyproject.read_text())
            papercli_table = table.get("tool", {}).get("papercli", {})
            if papercli_table:
                layers.append((papercli_table, repo))
    merged: dict[str, Any] = {}
    custom: dict[str, Backend] = {}
    for data, layer_base in layers:
        # a backend's *_file paths resolve against the layer that declared it
        for name, spec in data.get("agent", {}).get("backends", {}).items():
            custom[name] = parse_backend(name, spec, layer_base)
        merged = _merge(merged, data)
    merged = _merge(merged, {k: v for k, v in flags.items() if v is not None})

    _configure_hallubib(merged)
    backends = dict(BUILTIN) | custom
    agent_table = merged.get("agent", {})
    agent_name = os.environ.get("PAPERCLI_AGENT_BACKEND") or agent_table.get(
        "backend", "claude-code"
    )
    reconstruct_table = merged.get("reconstruct", {})
    reconstruct_name = reconstruct_table.get("backend", agent_name)
    if agent_name not in backends:
        raise KeyError(f"[agent] backend {agent_name!r} is not defined")
    if reconstruct_name not in backends:
        raise KeyError(f"[reconstruct] backend {reconstruct_name!r} is not defined")

    def pick(name: str, model: str | None, effort: str | None) -> Backend:
        if name in _CLAUDE_BUILTINS and name not in custom:
            return _claude(name, model, effort)
        return backends[name]

    return Config(
        projects_root=Path(merged.get("projects_root", _PROJECTS_ROOT)).expanduser(),
        style=merged.get("style"),
        agent=pick(agent_name, agent_table.get("model"), agent_table.get("effort")),
        reconstruct=pick(
            reconstruct_name,
            reconstruct_table.get("model", _RECONSTRUCT_MODEL),
            reconstruct_table.get("effort", _RECONSTRUCT_EFFORT),
        ),
        reconstruct_rounds=int(reconstruct_table.get("rounds", 1)),
        reconstruct_target=float(reconstruct_table.get("target", 0.95)),
    )


def reconstruct_overrides(model: str | None, effort: str | None) -> dict[str, Any]:
    """Per-run model/effort in the shape load_config takes, for CLI flags and API bodies."""
    overrides = {k: v for k, v in (("model", model), ("effort", effort)) if v}
    return {"reconstruct": overrides} if overrides else {}


_hallubib_settings: tuple[str | None, str | None, str | None] | None = None


def _configure_hallubib(merged: dict[str, Any]) -> None:
    """hallubib's config is a global whose every change drops its HTTP session,
    and load_config runs per request — so only push when something changed."""
    global _hallubib_settings
    settings = (
        os.environ.get("HALLUBIB_MAILTO") or merged.get("mailto"),
        os.environ.get("S2_API_KEY") or merged.get("s2_api_key"),
        os.environ.get("OPENALEX_API_KEY") or merged.get("openalex_api_key"),
    )
    if settings == _hallubib_settings:
        return
    _hallubib_settings = settings
    mailto, s2_api_key, openalex_api_key = settings
    configure(mailto=mailto, s2_api_key=s2_api_key, openalex_api_key=openalex_api_key)


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out
