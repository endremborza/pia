from pathlib import Path

import pytest

from papercli.config import load_config


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PAPERCLI_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.delenv("PAPERCLI_AGENT_BACKEND", raising=False)


def test_defaults(tmp_path: Path):
    config = load_config()
    assert config.agent.name == "claude-code"
    assert "ANTHROPIC_API_KEY" in config.agent.drop_env
    assert "Bash(papercli:*)" in config.agent.argv[-1]
    assert config.projects_root.name == "projects"
    assert config.reconstruct_rounds == 1
    assert "--model" not in config.agent.argv
    reconstruct_argv = " ".join(config.reconstruct.argv)
    assert "--model sonnet" in reconstruct_argv
    assert "--effort medium" in reconstruct_argv


def test_reconstruct_flag_overrides(tmp_path: Path):
    config = load_config(reconstruct={"model": "opus", "effort": "high"})
    argv = " ".join(config.reconstruct.argv)
    assert "--model opus" in argv and "--effort high" in argv
    assert "--model" not in config.agent.argv


def test_api_backend_is_explicit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PAPERCLI_AGENT_BACKEND", "claude-api")
    config = load_config()
    assert config.agent.name == "claude-api"
    assert config.agent.require_env == ("ANTHROPIC_API_KEY",)
    assert config.agent.drop_env == ()


def test_user_layer_and_custom_backend(tmp_path: Path):
    (tmp_path / "config.toml").write_text(
        f"""
projects_root = "{tmp_path}/projects"
style = "apa"
[agent]
backend = "fake"
[agent.backends.fake]
argv = ["sh", "run.sh"]
"""
    )
    config = load_config()
    assert config.style == "apa"
    assert config.agent.name == "fake"
    assert config.agent.argv == ("sh", "run.sh")
    assert config.agent.timeout is not None
    assert config.projects_root == tmp_path / "projects"


def test_repo_layer_overrides_user(tmp_path: Path):
    (tmp_path / "config.toml").write_text('style = "apa"')
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[tool.papercli]\nstyle = "ieee"')
    assert load_config(repo).style == "ieee"
    assert load_config().style == "apa"


def test_unknown_backend_fails_loudly(tmp_path: Path):
    (tmp_path / "config.toml").write_text('[agent]\nbackend = "nope"')
    with pytest.raises(KeyError):
        load_config()


def test_backend_file_paths_resolve_against_their_own_layer(tmp_path: Path):
    """A repo layer must not move where the user layer's prompt_file is looked up."""
    (tmp_path / "prompt.txt").write_text("from the user layer")
    (tmp_path / "config.toml").write_text(
        '[agent]\nbackend = "fake"\n'
        '[agent.backends.fake]\nargv = ["sh"]\nprompt_file = "prompt.txt"\n'
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[tool.papercli]\nstyle = "ieee"')
    config = load_config(repo)
    assert config.agent.prompt == "from the user layer"
    assert config.style == "ieee"
