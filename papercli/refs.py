"""The CSL-JSON reference store (refs.json), keyed by cite key.

Every reference in the system converges here — parsed bibitems, .bib entries,
review-discovered sources — and everything downstream (refs.bib, bibliographies,
the UI reference list) derives from it. Verified entries take the online record's
normalized fields; provenance and resolution status ride in `custom`.
"""

import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Final

from hallubib import (
    CheckResult,
    Reference,
    Status,
    check_references_iter,
    parse_bib,
    parse_tex,
    to_bib,
    to_csl,
)
from paritex import MAIN_TEX, REFS_BIB

from papercli.repo import REFS_JSON

OnProgress = Callable[[int, int, str, str], None]

# The source-native ids a reference can be grounded by, and where each one
# resolves. Every consumer — the store summary, review findings, the grounding
# check — reads these two names; none restates them.
ID_FIELDS: Final = ("doi", "openalex", "semanticscholar", "arxiv")
_ID_URLS: Final = {
    "doi": "https://doi.org/{}",
    "crossref": "https://doi.org/{}",
    "openalex": "https://openalex.org/{}",
    "semanticscholar": "https://www.semanticscholar.org/paper/{}",
    "arxiv": "https://arxiv.org/abs/{}",
}

_NORMALIZED = (Status.VERIFIED, Status.AUTO_CORRECTABLE)
# papercli's own resolution metadata inside `custom` — never bibliographic fields
_BOOKKEEPING = ("status", "notes", "diffs", "origin", "source")


def load_store(repo: Path) -> dict[str, dict]:
    path = repo / REFS_JSON
    return json.loads(path.read_text()) if path.is_file() else {}


def save_store(repo: Path, items: dict[str, dict]) -> None:
    ordered = {key: items[key] for key in sorted(items)}
    (repo / REFS_JSON).write_text(json.dumps(ordered, indent=1, ensure_ascii=False))


def parse_repo_references(repo: Path) -> list[Reference]:
    bib = repo / REFS_BIB
    if bib.is_file():
        return parse_bib(bib.read_text())
    return parse_tex((repo / MAIN_TEX).read_text())


def resolve(
    references: list[Reference], on_progress: OnProgress | None = None
) -> dict[str, dict]:
    items: dict[str, dict] = {}
    total = len(references)
    for done, (index, result) in enumerate(check_references_iter(references), start=1):
        reference = references[index]
        items[reference.key] = _to_item(reference, result)
        if on_progress is not None:
            on_progress(done, total, reference.key, str(result.status))
    return items


def resolved_item(key: str, result: CheckResult) -> dict:
    return _to_item(result.reference, result, key=key)


def derive_bib(repo: Path, items: dict[str, dict]) -> None:
    """refs.bib carries bibliographic fields only.

    hallubib writes unrecognized `custom` entries back out as BibTeX fields, which
    is how it round-trips a source .bib — but papercli's own resolution bookkeeping
    lives in the same place and would land in the file as invented fields.
    """
    ordered = [_bibliographic(items[key]) for key in sorted(items)]
    (repo / REFS_BIB).write_text(to_bib(ordered))


def _bibliographic(item: dict) -> dict:
    custom = {
        name: value
        for name, value in (item.get("custom") or {}).items()
        if name not in _BOOKKEEPING
    }
    return item | {"custom": custom}


def id_url(api: str | None, value: str | None) -> str | None:
    template = _ID_URLS.get(api or "")
    return template.format(value) if template and value else None


def source_ids(item: dict) -> set[str]:
    """The source-native ids a store entry is grounded by, if any."""
    custom = item.get("custom") or {}
    return {str(custom[name]) for name in ID_FIELDS if custom.get(name)}


def source_links(item: dict) -> list[dict]:
    custom = item.get("custom") or {}
    return [
        {"api": name, "id": custom[name], "url": id_url(name, custom[name])}
        for name in ID_FIELDS
        if custom.get(name)
    ]


def store_summary(items: dict[str, dict]) -> list[dict]:
    return [
        {
            "key": key,
            "status": (item.get("custom") or {}).get("status", str(Status.UNKNOWN)),
            "title": item.get("title", ""),
            "author": _author_line(item),
            "year": _year(item),
            "ids": source_links(item),
            "url": item.get("URL"),
            "notes": (item.get("custom") or {}).get("notes", []),
        }
        for key, item in sorted(items.items())
    ]


def abstracts(items: dict[str, dict]) -> dict[str, str]:
    return {
        key: item["abstract"] for key, item in items.items() if item.get("abstract")
    }


def _to_item(reference: Reference, result: CheckResult, key: str | None = None) -> dict:
    key = key or reference.key
    match = result.best_match
    normalized = match if result.status in _NORMALIZED and match is not None else None
    base = to_csl(normalized if normalized is not None else reference, key)
    # Only an accepted match may speak for the reference: an abstract from a
    # rejected candidate would describe a different paper, and the review agent
    # reads these as evidence about the cited work.
    if normalized is not None and normalized.abstract and "abstract" not in base:
        base["abstract"] = normalized.abstract
    custom = dict(base.get("custom", {}))
    custom["status"] = str(result.status)
    if result.notes:
        custom["notes"] = list(result.notes)
    if result.diffs:
        custom["diffs"] = [
            {
                "field": d.field_name,
                "local": d.local_value,
                "online": d.online_value,
                "kind": str(d.kind),
            }
            for d in result.diffs
        ]
    base["custom"] = custom
    return base


def gen_key(record: dict, existing: set[str]) -> str:
    authors = record.get("authors") or []
    family = (
        (authors[0].get("family") or authors[0].get("literal") or "ref")
        if authors
        else "ref"
    )
    base = "".join(c for c in family.lower() if c.isalnum()) or "ref"
    base += str(record.get("year") or "")
    key = base
    for suffix in "bcdefghijklmnop":
        if key not in existing:
            return key
        key = base + suffix
    raise ValueError(f"cannot generate unique key for {base}")


def _author_line(item: dict) -> str:
    names = [
        a.get("literal") or a.get("family") or a.get("given", "")
        for a in item.get("author", [])
    ]
    return ", ".join(n for n in names if n)


def _year(item: dict) -> int | None:
    parts = item.get("issued", {}).get("date-parts", [[]])
    return parts[0][0] if parts and parts[0] else None


def keys_of(items: Iterable[dict]) -> set[str]:
    return {item["id"] for item in items}
