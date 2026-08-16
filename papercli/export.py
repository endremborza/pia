"""Export: regenerate derived files from the store, build with tectonic, tag."""

from pathlib import Path

from papercli import gitstore, render
from papercli.config import Config
from papercli.lock import hold
from papercli.refs import load_store
from papercli.repo import next_n


def export(repo: Path, config: Config) -> Path:
    with hold(repo, "export"):
        render.refresh_derived(repo, load_store(repo), config.style)
        pdf = render.build(repo)
        if gitstore.dirty_paths(repo):
            gitstore.commit_all(repo, "papercli export: refresh derived files")
        gitstore.tag(repo, f"export/{next_n(repo, 'export/')}")
        return pdf
