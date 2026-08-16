import argparse
import json
from dataclasses import asdict
from pathlib import Path


def main() -> None:
    from papercli import __version__

    parser = argparse.ArgumentParser(prog="papercli")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("parse", help="parse a .tex file to structure JSON")
    p.add_argument("path", type=Path)
    p.set_defaults(handler=_parse)

    p = sub.add_parser("init", help="adopt a directory as a papercli repo")
    p.add_argument("repo", type=Path, nargs="?", default=Path("."))
    p.set_defaults(handler=_init)

    p = sub.add_parser("status", help="repo state as JSON")
    _repo_arg(p).set_defaults(handler=_status)

    p = sub.add_parser("review", help="run the peer-review agent")
    _repo_arg(p).set_defaults(handler=_review)

    p = sub.add_parser("do", help="apply a natural-language edit on a proposal branch")
    p.add_argument("instruction")
    _repo_arg(p).set_defaults(handler=_do)

    p = sub.add_parser("approve", help="fast-forward merge the open proposal")
    _repo_arg(p).set_defaults(handler=_approve)

    p = sub.add_parser("reject", help="delete the open proposal branch")
    _repo_arg(p).set_defaults(handler=_reject)

    p = sub.add_parser("export", help="build the paper PDF and tag export/N")
    _repo_arg(p).set_defaults(handler=_export)

    p = sub.add_parser("accept", help="accept the PDF reconstruction candidate")
    _repo_arg(p).set_defaults(handler=_accept)

    p = sub.add_parser(
        "rerun", help="re-run reconstruction from the committed original"
    )
    _reconstruct_args(_repo_arg(p)).set_defaults(handler=_rerun)

    p = sub.add_parser(
        "refine", help="another agent pass over the unaccepted candidate"
    )
    p.add_argument(
        "instruction", nargs="?", help="steer the pass; omit for parity-only"
    )
    _reconstruct_args(_repo_arg(p)).set_defaults(handler=_refine)

    p = sub.add_parser("search", help="grounded source search (logs every record)")
    p.add_argument("query")
    p.add_argument("--log", type=Path, required=True)
    p.set_defaults(handler=_search)

    p = sub.add_parser("abstracts", help="cite key -> abstract JSON from the store")
    _repo_arg(p).set_defaults(handler=_abstracts)

    p = sub.add_parser("validate", help="citation validator on the working tree")
    _repo_arg(p).set_defaults(handler=_validate)

    p = sub.add_parser(
        "addref", help="add a logged record to the store; prints its key"
    )
    p.add_argument("source_id")
    p.add_argument("--log", type=Path, required=True)
    p.set_defaults(handler=_addref)

    p = sub.add_parser("serve", help="run the web API (needs the server extra)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true")
    p.add_argument(
        "--static",
        type=Path,
        help="also serve this built SPA dir (index.html fallback)",
    )
    p.set_defaults(handler=_serve)

    args = parser.parse_args()
    try:
        args.handler(args)
    except Exception as err:  # fail loudly, but with the message, not a traceback
        if _passthrough(err):
            raise
        raise SystemExit(f"papercli {args.command}: {err}") from err


def _repo_arg(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
    p.add_argument("repo", type=Path, nargs="?", default=Path("."))
    return p


def _reconstruct_args(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
    p.add_argument("--model", help="reconstruction model (default: sonnet)")
    p.add_argument("--effort", help="reconstruction effort (default: medium)")
    return p


def _passthrough(err: Exception) -> bool:
    return isinstance(err, (SystemExit, KeyboardInterrupt))


def _parse(args: argparse.Namespace) -> None:
    from papercli.latex import parse_latex

    parsed = parse_latex(args.path.read_text())
    print(json.dumps(asdict(parsed), indent=2))


def _init(args: argparse.Namespace) -> None:
    from papercli.config import load_config
    from papercli.ingest import adopt, resolve_repo

    repo = adopt(args.repo)
    resolve_repo(repo, load_config(repo), print)


def _status(args: argparse.Namespace) -> None:
    from papercli.repo import state

    print(json.dumps(asdict(state(args.repo)), indent=2))


def _review(args: argparse.Namespace) -> None:
    from papercli.config import load_config
    from papercli.review import run_review

    n = run_review(args.repo, load_config(args.repo), print)
    print(f"review {n} ready: reviews/{n}/")


def _do(args: argparse.Namespace) -> None:
    from papercli.config import load_config
    from papercli.edit import proposal_diff, run_edit

    run_edit(args.repo, args.instruction, load_config(args.repo), print)
    print(proposal_diff(args.repo)["diff"])


def _approve(args: argparse.Namespace) -> None:
    from papercli.edit import approve

    approve(args.repo)


def _reject(args: argparse.Namespace) -> None:
    from papercli.edit import reject

    reject(args.repo)


def _export(args: argparse.Namespace) -> None:
    from papercli.config import load_config
    from papercli.export import export

    print(export(args.repo, load_config(args.repo)))


def _accept(args: argparse.Namespace) -> None:
    from papercli.config import load_config
    from papercli.ingest import accept

    accept(args.repo, load_config(args.repo), print)


def _rerun(args: argparse.Namespace) -> None:
    from papercli.config import load_config, reconstruct_overrides
    from papercli.ingest import reconstruct_candidate

    overrides = reconstruct_overrides(args.model, args.effort)
    reconstruct_candidate(args.repo, load_config(args.repo, **overrides), print)


def _refine(args: argparse.Namespace) -> None:
    from papercli.config import load_config, reconstruct_overrides
    from papercli.ingest import refine_candidate

    overrides = reconstruct_overrides(args.model, args.effort)
    refine_candidate(
        args.repo, load_config(args.repo, **overrides), args.instruction, print
    )


def _search(args: argparse.Namespace) -> None:
    from papercli.config import load_config
    from papercli.search import log_records, search_sources

    load_config(Path("."))  # for its side effect: hallubib's service identity
    result = search_sources(args.query)
    log_records(args.log, result)
    print(json.dumps(result, indent=1, ensure_ascii=False))


def _abstracts(args: argparse.Namespace) -> None:
    from papercli.refs import abstracts, load_store

    print(json.dumps(abstracts(load_store(args.repo)), indent=1, ensure_ascii=False))


def _validate(args: argparse.Namespace) -> None:
    from papercli.edit import validate_worktree

    violations = validate_worktree(args.repo)
    for violation in violations:
        print(f"- {violation}")
    if violations:
        raise SystemExit(1)
    print("ok")


def _addref(args: argparse.Namespace) -> None:
    from papercli.config import load_config
    from papercli.edit import add_ref

    repo = Path(".")
    print(add_ref(repo, args.source_id, args.log, load_config(repo)))


def _serve(args: argparse.Namespace) -> None:
    try:
        import uvicorn
    except ImportError:
        raise SystemExit(
            "papercli serve needs the server extra: uv add 'papercli[server]'"
        ) from None
    if args.static:
        import os

        os.environ["PAPERCLI_STATIC"] = str(args.static.resolve())
    uvicorn.run(
        "papercli.server:app", host=args.host, port=args.port, reload=args.reload
    )
