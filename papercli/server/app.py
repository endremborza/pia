"""The web adapter: every endpoint is a thin call into the same core the CLI drives.

The server executes no repo code but tectonic, reads committed state for every
view, and delegates agent work to background runs guarded by the repo lock.
"""

import base64
import json
import logging
import os
import re
import secrets
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from paritex import MAIN_TEX, ORIGINAL, REBUILT, REPORT

from papercli import (
    RepoBusy,
    ValidationError,
    approve,
    create_from_pdf,
    create_from_tex,
    delete,
    export,
    findings_json,
    gitstore,
    load_config,
    parse_latex,
    proposal_diff,
    reconstruct_candidate,
    refine_candidate,
    reject,
    render,
    resolve_repo,
    run_edit,
    run_review,
    state,
    store_summary,
)
from papercli.config import reconstruct_overrides
from papercli.ingest import accept as accept_candidate
from papercli.repo import REVIEW_TEX, paper_view
from papercli.server.runs import RunInProgress, Runs

app = FastAPI(title="papercli")
runs = Runs()

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_POLL_RE = re.compile(r"^/api/papers(/[a-z0-9-]+)?$")
_MODEL_RE = re.compile(r"^(haiku|sonnet|opus|claude-[a-z0-9.\[\]-]+)$")
_EFFORTS = ("low", "medium", "high", "xhigh")
_MAX_UPLOAD = 32 * 1024 * 1024


class _QuietPolls(logging.Filter):
    """Drop the frontend's 1.5s state-poll 200s from uvicorn's access log."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not (isinstance(args, tuple) and len(args) == 5):
            return True
        _, method, path, _, status = args
        return not (method == "GET" and status == 200 and _POLL_RE.match(str(path)))


# Run progress must reach the dev console (uvicorn only configures its own
# loggers), and the poll spam must not drown it out. An embedder that already
# configured logging keeps its own setup — importing the app never overrides it.
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logging.getLogger("uvicorn.access").addFilter(_QuietPolls())


def _authorized(header: str, password: str) -> bool:
    scheme, _, payload = header.partition(" ")
    if scheme.lower() != "basic":
        return False
    try:
        decoded = base64.b64decode(payload.strip(), validate=True).decode()
    except (ValueError, UnicodeDecodeError):
        return False
    _, _, supplied = decoded.partition(":")
    return secrets.compare_digest(supplied.encode(), password.encode())


if _password := os.environ.get("PAPERCLI_PASSWORD"):
    # The public-deployment switch: HTTP Basic (any username) on everything but
    # the health probe. Browsers prompt natively and re-send credentials on the
    # SPA's fetches and PDF embeds, so no frontend login flow exists to drift.
    _required_password: str = _password

    @app.middleware("http")
    async def _require_password(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        auth = request.headers.get("authorization", "")
        if request.url.path == "/api/health" or _authorized(auth, _required_password):
            return await call_next(request)
        return Response(
            status_code=401, headers={"WWW-Authenticate": 'Basic realm="papercli"'}
        )


@app.exception_handler(ValidationError)
async def _validation_error(_, err: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422, content={"detail": str(err), "violations": err.violations}
    )


@app.exception_handler(RepoBusy)
async def _busy(_, err: RepoBusy) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(err)})


@app.exception_handler(RunInProgress)
async def _run_in_progress(_, err: RunInProgress) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(err)})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/papers")
def list_papers() -> list[dict]:
    root = load_config().projects_root
    if not root.is_dir():
        return []
    papers = []
    for path in sorted(root.iterdir()):
        if not (path / ".git").is_dir():
            continue
        repo_state = state(path)
        papers.append(
            {"id": path.name, "title": _title(path), "accepted": repo_state.accepted}
        )
    return papers


@app.post("/api/papers")
def upload_paper(
    file: UploadFile,
    kind: Annotated[Literal["latex", "pdf"], Form()],
    model: Annotated[str | None, Form()] = None,
    effort: Annotated[str | None, Form()] = None,
) -> dict:
    config = load_config()
    name = file.filename or "paper"
    paper_id = _new_id(config.projects_root, name)
    dest = config.projects_root / paper_id
    content = _read_upload(file)
    if kind == "latex":
        try:
            tex = content.decode("utf-8")
        except UnicodeDecodeError as err:
            raise HTTPException(400, f"not valid UTF-8 LaTeX: {err}") from None
        create_from_tex(dest, tex, name)
        runs.start(
            paper_id,
            "resolve",
            lambda run: resolve_repo(dest, load_config(dest), run.emit),
        )
    else:
        flags = _reconstruct_flags(model, effort)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / ORIGINAL).write_bytes(content)
        create_from_pdf(dest, dest / ORIGINAL)
        runs.start(
            paper_id,
            "reconstruct",
            lambda run: reconstruct_candidate(
                dest, load_config(dest, **flags), run.emit
            ),
        )
    return {"id": paper_id}


@app.get("/api/papers/{paper_id}")
def paper_state(paper_id: str) -> dict:
    repo = _repo(paper_id)
    repo_state = state(repo)
    run = runs.get(paper_id)
    parse = _committed(repo, MAIN_TEX)
    store = _committed(repo, "refs.json")
    report = _committed(repo, REPORT)
    diff = None
    if repo_state.proposal is not None:
        diff = proposal_diff(repo)
    items = json.loads(store) if store else None
    return {
        "id": paper_id,
        "title": _title(repo),
        "state": asdict(repo_state),
        "run": run.as_dict() if run else None,
        "parse": paper_view(parse, items) if parse else None,
        "refs": store_summary(items) if items else [],
        "parity": json.loads(report) if report else None,
        "proposal": diff,
        "log": gitstore.log_oneline(repo, 20),
    }


@app.delete("/api/papers/{paper_id}")
def delete_paper(paper_id: str) -> dict:
    delete(_repo(paper_id))
    return {"deleted": True}


@app.post("/api/papers/{paper_id}/accept")
def accept_paper(paper_id: str) -> dict:
    repo = _repo(paper_id)
    runs.start(
        paper_id,
        "resolve",
        lambda run: accept_candidate(repo, load_config(repo), run.emit),
    )
    return {"started": True}


@app.post("/api/papers/{paper_id}/rerun")
def rerun_paper(paper_id: str, body: dict | None = None) -> dict:
    repo = _repo(paper_id)
    flags = _reconstruct_flags_from(body)
    runs.start(
        paper_id,
        "reconstruct",
        lambda run: reconstruct_candidate(repo, load_config(repo, **flags), run.emit),
    )
    return {"started": True}


@app.post("/api/papers/{paper_id}/refine")
def refine_paper(paper_id: str, body: dict | None = None) -> dict:
    repo = _repo(paper_id)
    flags = _reconstruct_flags_from(body)
    instruction = ((body or {}).get("instruction") or "").strip() or None
    runs.start(
        paper_id,
        "refine",
        lambda run: refine_candidate(
            repo, load_config(repo, **flags), instruction, run.emit
        ),
    )
    return {"started": True}


@app.post("/api/papers/{paper_id}/review")
def review_paper(paper_id: str) -> dict:
    repo = _repo(paper_id)
    runs.start(
        paper_id,
        "review",
        lambda run: run_review(repo, load_config(repo), run.emit),
    )
    return {"started": True}


@app.get("/api/papers/{paper_id}/reviews/{n}")
def review_findings(paper_id: str, n: int) -> dict:
    try:
        return findings_json(_repo(paper_id), n)
    except gitstore.GitError:
        raise HTTPException(404, f"review {n} not found") from None


@app.get("/api/papers/{paper_id}/reviews/{n}/pdf")
def review_pdf(paper_id: str, n: int) -> FileResponse:
    """A GET that may run tectonic: review.pdf is gitignored, so it is rebuilt
    from committed review.tex when missing. Idempotent, and it touches no git
    state — unlike export, which is why that one is a POST."""
    repo = _repo(paper_id)
    pdf = repo / "reviews" / str(n) / "review.pdf"
    if not pdf.is_file():
        if not (repo / "reviews" / str(n) / REVIEW_TEX).is_file():
            raise HTTPException(404, f"review {n} not found")
        render.build(repo, f"reviews/{n}/{REVIEW_TEX}")
    return FileResponse(pdf, media_type="application/pdf")


@app.post("/api/papers/{paper_id}/do")
def do_edit(paper_id: str, body: dict) -> dict:
    repo = _repo(paper_id)
    command = (body.get("command") or "").strip()
    if not command:
        raise HTTPException(400, "command is required")
    runs.start(
        paper_id,
        "edit",
        lambda run: run_edit(repo, command, load_config(repo), run.emit),
    )
    return {"started": True}


@app.post("/api/papers/{paper_id}/approve")
def approve_proposal(paper_id: str) -> dict:
    approve(_repo(paper_id))
    return {"merged": True}


@app.post("/api/papers/{paper_id}/reject")
def reject_proposal(paper_id: str) -> dict:
    reject(_repo(paper_id))
    return {"rejected": True}


@app.post("/api/papers/{paper_id}/export")
def export_paper(paper_id: str) -> FileResponse:
    """POST, not GET: exporting commits the refreshed derived files and tags
    export/N, so it must not be reachable by a link prefetch."""
    repo = _repo(paper_id)
    pdf = export(repo, load_config(repo))
    return FileResponse(pdf, media_type="application/pdf", filename=f"{paper_id}.pdf")


@app.get("/api/papers/{paper_id}/original.pdf")
def original_pdf(paper_id: str) -> FileResponse:
    return _pdf(_repo(paper_id) / ORIGINAL)


@app.get("/api/papers/{paper_id}/candidate.pdf")
def candidate_pdf(paper_id: str) -> FileResponse:
    return _pdf(_repo(paper_id) / REBUILT)


def _pdf(path: Path) -> FileResponse:
    if not path.is_file():
        raise HTTPException(404, f"{path.name} not available")
    return FileResponse(path, media_type="application/pdf")


def _read_upload(file: UploadFile) -> bytes:
    """Bounded read — an upload here is one paper, never a stream."""
    if file.size is not None and file.size > _MAX_UPLOAD:
        raise HTTPException(413, f"file exceeds {_MAX_UPLOAD // (1024 * 1024)} MB")
    content = file.file.read(_MAX_UPLOAD + 1)
    if len(content) > _MAX_UPLOAD:
        raise HTTPException(413, f"file exceeds {_MAX_UPLOAD // (1024 * 1024)} MB")
    return content


def _reconstruct_flags_from(body: dict | None) -> dict:
    body = body or {}
    return _reconstruct_flags(body.get("model"), body.get("effort"))


def _reconstruct_flags(model: str | None, effort: str | None) -> dict:
    """The same overrides the CLI builds, but from untrusted input — validated here."""
    if model and not _MODEL_RE.match(model):
        raise HTTPException(400, f"unknown model {model!r}")
    if effort and effort not in _EFFORTS:
        raise HTTPException(400, f"effort must be one of {', '.join(_EFFORTS)}")
    return reconstruct_overrides(model, effort)


def _repo(paper_id: str) -> Path:
    if not _ID_RE.match(paper_id):
        raise HTTPException(404, "no such paper")
    path = load_config().projects_root / paper_id
    if not (path / ".git").is_dir():
        raise HTTPException(404, "no such paper")
    return path


def _committed(repo: Path, path: str) -> str | None:
    try:
        return gitstore.show(repo, "main", path)
    except gitstore.GitError:
        return None


def _title(repo: Path) -> str:
    tex = _committed(repo, MAIN_TEX)
    if tex:
        parsed = parse_latex(tex)
        if parsed.title:
            return parsed.title
    return repo.name


def _new_id(root: Path, filename: str) -> str:
    stem = Path(filename).stem.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")[:40] or "paper"
    return f"{slug}-{uuid.uuid4().hex[:6]}"


def _attach_static(root: Path) -> None:
    """Serve a built SPA (any static dir with an index.html fallback) next to the
    API — the deployment story: one process, one port. The package still knows
    nothing about what frontend produced the directory."""
    index = root / "index.html"
    if not index.is_file():
        raise FileNotFoundError(f"PAPERCLI_STATIC has no index.html: {root}")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "no such endpoint")
        file = (root / path).resolve()
        if file.is_file() and file.is_relative_to(root.resolve()):
            return FileResponse(file)
        return FileResponse(index)


if _static := os.environ.get("PAPERCLI_STATIC"):
    _attach_static(Path(_static))
