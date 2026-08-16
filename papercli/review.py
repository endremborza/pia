"""Peer review: an agent run whose only accepted output is schema-valid, grounded XML.

reviews/N/review.xml is canonical; the RelaxNG schema (package data) makes an
ungrounded finding unrepresentable, and the fetch-log check makes a fabricated
source id unwritable. review.tex, its citeproc bibliography and the frontend
JSON are all derived from the XML by code.

A review is read-only on the paper, and that is enforced rather than asked for:
the agent's diff is scoped to reviews/N/, so a run that touched main.tex or the
store is rejected wholesale before anything is finalized or committed.
"""

import json
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path

import lxml.etree as etree  # noqa: PLR0402 — the aliased form is what lxml's stubs type
from hallubib import Status, to_csl

from papercli import gitstore, render
from papercli.agentrun import run
from papercli.config import Config
from papercli.lock import hold
from papercli.prompts import REVIEW
from papercli.refs import gen_key, id_url, load_store, save_store
from papercli.repo import REVIEW_TEX, REVIEW_XML, SOURCES_JSON, next_n, review_dir
from papercli.search import logged_ids, record_from_dict, store_ids
from papercli.validator import ValidationError, check_review_cites, check_review_run

OnProgress = Callable[[str], None]


def run_review(
    repo: Path, config: Config, on_progress: OnProgress | None = None
) -> int:
    emit = on_progress or (lambda _: None)
    with hold(repo, "review"):
        n = next_n(repo, "review/")
        rdir = review_dir(repo, n)
        rdir.mkdir(parents=True, exist_ok=True)
        rel = rdir.relative_to(repo)
        emit(f"review {n}: agent run started ({config.agent.name})")
        prompt = REVIEW.format(
            review_xml=rel / REVIEW_XML,
            sources_json=rel / SOURCES_JSON,
            review_dir=rel,
        )
        try:
            run(repo, config.agent, prompt, on_line=emit)
            emit("agent run finished, checking gates")
            check_review_run(gitstore.dirty_paths(repo), str(rel))
            emit("validating findings")
            finalize_review(repo, n, config)
        except Exception:
            gitstore.discard_all(repo)
            raise
        gitstore.commit_all(repo, f"papercli review {n}")
        gitstore.tag(repo, f"review/{n}")
        emit(f"review {n} committed")
        return n


def finalize_review(repo: Path, n: int, config: Config) -> None:
    rdir = review_dir(repo, n)
    xml_path = rdir / REVIEW_XML
    if not xml_path.is_file():
        raise ValidationError([f"agent produced no {REVIEW_XML}"])
    tree = validate_xml(xml_path)
    items = load_store(repo)
    known = store_ids(items)
    fetched = logged_ids(rdir / SOURCES_JSON)

    unknown = [
        source.get("id")
        for source in tree.iter("source")
        if source.get("id") not in known and source.get("id") not in fetched
    ]
    if unknown:
        raise ValidationError(
            [f"source id not in fetch log or store: {i}" for i in unknown]
        )
    check_review_cites((c.get("key") for c in tree.iter("cite")), frozenset(items))

    new_records = {
        source.get("id"): fetched[source.get("id")]
        for source in tree.iter("source")
        if source.get("id") not in known
    }
    for record_dict in new_records.values():
        record = record_from_dict(record_dict)
        if any(i in known for i in record.ids.values()):
            continue
        key = gen_key(record_dict, set(items))
        item = to_csl(record, key)
        item["custom"] = dict(item.get("custom", {})) | {
            "status": str(Status.VERIFIED),
            "origin": f"review/{n}",
        }
        items[key] = item
        known.update({i: key for i in record.ids.values()})
    save_store(repo, items)
    style = render.refresh_derived(repo, items, config.style)
    (rdir / REVIEW_TEX).write_text(review_tex(tree, n, items, known, style))
    render.build(repo, str(rdir.relative_to(repo) / REVIEW_TEX))


def validate_xml(xml_path: Path) -> etree._Element:
    schema_text = files("papercli").joinpath("data/review.rng").read_text()
    schema = etree.RelaxNG(etree.fromstring(schema_text.encode()))
    tree = etree.parse(xml_path)
    if not schema.validate(tree):
        raise ValidationError(
            [f"review.xml schema violation: {e.message}" for e in schema.error_log]
        )
    return tree.getroot()


def findings_json(repo: Path, n: int) -> dict:
    xml = gitstore.show(repo, f"review/{n}", f"reviews/{n}/{REVIEW_XML}")
    store = json.loads(gitstore.show(repo, f"review/{n}", "refs.json"))
    known = store_ids(store)
    root = etree.fromstring(xml.encode())
    findings = []
    for f in root.iter("finding"):
        sources = []
        for s in f.iter("source"):
            key = known.get(s.get("id") or "")
            item = store.get(key, {}) if key else {}
            sources.append(
                {
                    "api": s.get("api"),
                    "id": s.get("id"),
                    "key": key,
                    "title": item.get("title"),
                    "url": item.get("URL") or id_url(s.get("api"), s.get("id")),
                }
            )
        findings.append(
            {
                "kind": f.get("kind"),
                "severity": f.get("severity"),
                "confidence": float(f.get("confidence") or 0),
                "section": _text(f, "section"),
                "claim": _text(f, "claim"),
                "cites": [c.get("key") for c in f.iter("cite")],
                "sources": sources,
                "verdict": _text(f, "verdict"),
                "note": _text(f, "note"),
                "suggestion": _text(f, "suggestion"),
            }
        )
    return {"n": n, "paper": root.get("paper"), "findings": findings}


def review_tex(
    root: etree._Element,
    n: int,
    items: dict[str, dict],
    known: dict[str, str],
    style: str,
) -> str:
    esc = render.escape_latex
    lines = [
        "\\documentclass{article}",
        "\\usepackage[margin=1in]{geometry}",
        f"\\title{{Review {n}: {esc(root.get('paper') or 'paper')}}}",
        "\\author{papercli review agent}",
        "\\begin{document}",
        "\\maketitle",
        "\\begin{enumerate}",
    ]
    used: list[str] = []
    for f in root.iter("finding"):
        keys = [c.get("key") or "" for c in f.iter("cite")]
        keys += [
            known[s.get("id") or ""] for s in f.iter("source") if s.get("id") in known
        ]
        keys = [k for k in dict.fromkeys(keys) if k]
        used += [k for k in keys if k not in used]
        parts = [f"\\item \\textbf{{{esc(f.get('kind') or '')}}}"]
        parts.append(
            f"({esc(f.get('severity') or '')}, confidence {f.get('confidence')})"
        )
        if section := _text(f, "section"):
            parts.append(f"--- {esc(section)}.")
        if claim := _text(f, "claim"):
            parts.append(f"\\emph{{``{esc(claim)}''}}")
        if verdict := _text(f, "verdict"):
            parts.append(f"Verdict: {esc(verdict)}.")
        parts.append(esc(_text(f, "note") or ""))
        if suggestion := _text(f, "suggestion"):
            parts.append(f"Suggested: {esc(suggestion)}")
        if keys:
            parts.append("\\cite{" + ",".join(keys) + "}")
        lines.append(" ".join(parts))
    lines.append("\\end{enumerate}")
    used_items = {k: items[k] for k in used if k in items}
    lines.append(render.bibliography_tex(used_items, style))
    lines.append("\\end{document}")
    return "\n".join(lines) + "\n"


def _text(element: etree._Element, tag: str) -> str | None:
    child = element.find(tag)
    return child.text.strip() if child is not None and child.text else None
