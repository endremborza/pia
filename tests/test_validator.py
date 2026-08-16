import pytest

from papercli.validator import PaperState, ValidationError, check_edit

ALLOWED = frozenset({"main.tex", "refs.json", "refs.bib", "bibliography.tex"})
FETCHED = frozenset({"W_fetched"})


def _state(tex: str, store: dict[str, str | None]) -> PaperState:
    """store maps cite key -> the source id grounding it (None = ungrounded)."""
    return PaperState(
        tex=tex,
        store={
            key: {"id": key, "custom": {"openalex": sid} if sid else {}}
            for key, sid in store.items()
        },
    )


def test_clean_edit_passes():
    before = _state(r"a \cite{x} b \cite{y}", {"x": "W1", "y": "W2"})
    after = _state(r"b \cite{y} moved \cite{x} plus \cite{x}", {"x": "W1", "y": "W2"})
    check_edit(before, after, ["main.tex"], ALLOWED, FETCHED)


def test_dropped_citation_rejected():
    before = _state(r"\cite{x} \cite{x} \cite{y}", {"x": "W1", "y": "W2"})
    after = _state(r"\cite{x} \cite{y}", {"x": "W1", "y": "W2"})
    with pytest.raises(ValidationError, match=r"citation dropped: x"):
        check_edit(before, after, ["main.tex"], ALLOWED, FETCHED)


def test_unknown_key_rejected():
    before = _state(r"\cite{x}", {"x": "W1"})
    after = _state(r"\cite{x} \cite{ghost}", {"x": "W1"})
    with pytest.raises(ValidationError, match="unknown key added: ghost"):
        check_edit(before, after, ["main.tex"], ALLOWED, FETCHED)


def test_store_removal_rejected():
    before = _state(r"\cite{x}", {"x": "W1", "extra": "W2"})
    after = _state(r"\cite{x}", {"x": "W1"})
    with pytest.raises(ValidationError, match="reference removed from store: extra"):
        check_edit(before, after, ["main.tex"], ALLOWED, FETCHED)


def test_disallowed_path_rejected():
    before = _state(r"\cite{x}", {"x": "W1"})
    after = _state(r"\cite{x}", {"x": "W1"})
    with pytest.raises(ValidationError, match="disallowed path"):
        check_edit(
            before, after, ["main.tex", "reviews/1/review.xml"], ALLOWED, FETCHED
        )


def test_violations_reported_together():
    before = _state(r"\cite{x}", {"x": "W1"})
    after = _state(r"\cite{ghost}", {"x": "W1"})
    with pytest.raises(ValidationError) as err:
        check_edit(before, after, ["evil.sh"], ALLOWED, FETCHED)
    assert len(err.value.violations) == 3


def test_fetched_store_key_and_cite_accepted():
    before = _state(r"\cite{x}", {"x": "W1"})
    after = _state(
        r"\cite{x} \cite[p.~3]{new2024}", {"x": "W1", "new2024": "W_fetched"}
    )
    check_edit(before, after, ["main.tex", "refs.json", "refs.bib"], ALLOWED, FETCHED)


def test_invented_reference_rejected():
    """refs.json is writable by the agent, so an entry it never fetched must not pass."""
    before = _state(r"\cite{x}", {"x": "W1"})
    after = _state(r"\cite{x} \cite{ghost2024}", {"x": "W1", "ghost2024": "W_invented"})
    with pytest.raises(ValidationError, match="not in the fetch log: ghost2024"):
        check_edit(before, after, ["main.tex", "refs.json"], ALLOWED, FETCHED)


def test_reference_without_any_source_id_rejected():
    before = _state(r"\cite{x}", {"x": "W1"})
    after = _state(r"\cite{x} \cite{ghost2024}", {"x": "W1", "ghost2024": None})
    with pytest.raises(ValidationError, match="without a source id: ghost2024"):
        check_edit(before, after, ["main.tex", "refs.json"], ALLOWED, FETCHED)
