from pathlib import Path

from hallubib import categorize, parse_tex

from papercli.refs import (
    derive_bib,
    gen_key,
    load_store,
    resolved_item,
    save_store,
    store_summary,
)

FIXTURE = Path(__file__).parent.parent / "e2e" / "fixtures" / "rankless-incomplete.tex"


def _offline_items() -> dict[str, dict]:
    references = parse_tex(FIXTURE.read_text())
    return {r.key: resolved_item(r.key, categorize(r, [])) for r in references}


def test_store_round_trip(tmp_path: Path):
    items = _offline_items()
    save_store(tmp_path, items)
    loaded = load_store(tmp_path)
    assert loaded == items
    assert all("status" in item["custom"] for item in loaded.values())


def test_derived_bib_reparses(tmp_path: Path):
    from hallubib import parse_bib

    items = _offline_items()
    derive_bib(tmp_path, items)
    reparsed = parse_bib((tmp_path / "refs.bib").read_text())
    assert {r.key for r in reparsed} == set(items)


def test_summary_shape():
    summary = store_summary(_offline_items())
    keys = {s["key"] for s in summary}
    assert "openalex" in keys and "cytoscape" in keys
    cytoscape = next(s for s in summary if s["key"] == "cytoscape")
    assert cytoscape["title"].startswith("Cytoscape")
    assert cytoscape["status"] == "Unknown"


def test_gen_key_dedup():
    record = {
        "authors": [{"family": "Priem", "given": "J", "literal": ""}],
        "year": 2022,
    }
    assert gen_key(record, set()) == "priem2022"
    assert gen_key(record, {"priem2022"}) == "priem2022b"
    assert gen_key({"authors": [], "year": None}, set()) == "ref"
