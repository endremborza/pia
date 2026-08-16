"""Grounded source search over hallubib's clients, with a verbatim fetch log.

Every record returned to a caller is also appended to the run's sources.json —
the log validation later checks review source ids against. An id that was never
fetched cannot be cited; failures are returned as data, never swallowed.
"""

import json
from dataclasses import asdict
from pathlib import Path

from hallubib import Name, OnlineRecord
from hallubib.sources import (
    SourceError,
    search_openalex_title,
    search_semscholar_relevance,
)

from papercli.refs import source_ids


def search_sources(query: str, limit: int = 5) -> dict:
    records: list[dict] = []
    failures: list[dict] = []
    for name, call in (
        ("openalex", lambda: search_openalex_title(query, with_year_filter=False)),
        ("semanticscholar", lambda: search_semscholar_relevance(query, limit=limit)),
    ):
        try:
            records.extend(record_to_dict(r) for r in call()[:limit])
        except SourceError as err:
            failures.append({"source": name, "error": str(err)})
    return {"query": query, "records": records, "failures": failures}


def record_to_dict(record: OnlineRecord) -> dict:
    return asdict(record)


def record_from_dict(data: dict) -> OnlineRecord:
    return OnlineRecord(**{**data, "authors": [Name(**a) for a in data["authors"]]})


def log_records(log_path: Path, result: dict) -> None:
    log = json.loads(log_path.read_text()) if log_path.is_file() else {"queries": []}
    log["queries"].append(result)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log, indent=1, ensure_ascii=False))


def logged_ids(log_path: Path) -> dict[str, dict]:
    """Every source-native id in the fetch log, mapped to its record."""
    if not log_path.is_file():
        return {}
    log = json.loads(log_path.read_text())
    ids: dict[str, dict] = {}
    for entry in log["queries"]:
        for record in entry["records"]:
            for value in record.get("ids", {}).values():
                ids[value] = record
    return ids


def store_ids(items: dict[str, dict]) -> dict[str, str]:
    """Every source-native id in the store, mapped to its cite key."""
    return {value: key for key, item in items.items() for value in source_ids(item)}
