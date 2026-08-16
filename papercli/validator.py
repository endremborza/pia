"""The citation-integrity gate: every change to the paper passes through here.

An edit is valid iff the diff stays on allowed paths, no cite key is dropped from
the in-text multiset, every added key exists in the reference store, the store
itself never loses an entry, and every entry the run *added* to the store carries
a source id the run actually fetched. That last check is what makes grounding
mechanical on the edit path too: refs.json is writable by the agent, so a
reference it invented there would otherwise satisfy every other rule.
Violations are reported all at once, never partially.
"""

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from papercli.latex import cite_multiset
from papercli.refs import source_ids


class ValidationError(Exception):
    def __init__(self, violations: list[str]) -> None:
        super().__init__("edit rejected:\n" + "\n".join(f"- {v}" for v in violations))
        self.violations = violations


@dataclass(frozen=True)
class PaperState:
    tex: str
    store: dict[str, dict]
    cites: Counter[str] = field(init=False)
    store_keys: frozenset[str] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cites", cite_multiset(self.tex))
        object.__setattr__(self, "store_keys", frozenset(self.store))


def path_violations(
    changed_paths: list[str], allowed: Callable[[str], bool]
) -> list[str]:
    return [
        f"disallowed path changed: {path}"
        for path in changed_paths
        if not allowed(path)
    ]


def check_review_run(changed_paths: list[str], review_dir: str) -> None:
    """A review reads the paper and files findings; it never edits either.

    Scoping the agent's whole diff to `reviews/N/` subsumes "main.tex unchanged"
    and "the store unchanged" in one rule. The harness may touch those after this
    gate passes — adding fetched sources, regenerating the bibliography — but that
    is code, from the fetch log, not the agent writing wherever it likes.
    """
    prefix = review_dir.rstrip("/") + "/"
    violations = path_violations(changed_paths, lambda path: path.startswith(prefix))
    if violations:
        raise ValidationError(violations)


def check_edit(
    before: PaperState,
    after: PaperState,
    changed_paths: list[str],
    allowed_paths: frozenset[str],
    fetched: frozenset[str],
) -> None:
    violations = path_violations(changed_paths, allowed_paths.__contains__)
    dropped = before.cites - after.cites
    for key, count in sorted(dropped.items()):
        violations.append(f"citation dropped: {key} (×{count})")
    added = after.cites - before.cites
    for key in sorted(set(added) - after.store_keys):
        violations.append(f"citation of unknown key added: {key}")
    for key in sorted(before.store_keys - after.store_keys):
        violations.append(f"reference removed from store: {key}")
    violations += check_store_additions(before.store, after.store, fetched)
    if violations:
        raise ValidationError(violations)


def check_store_additions(
    before: dict[str, dict], after: dict[str, dict], fetched: frozenset[str]
) -> list[str]:
    """Every reference the run added must carry an id the run actually fetched."""
    violations = []
    for key in sorted(set(after) - set(before)):
        ids = source_ids(after[key])
        if not ids:
            violations.append(f"reference added without a source id: {key}")
        elif not ids & fetched:
            listed = ", ".join(sorted(ids))
            violations.append(f"reference not in the fetch log: {key} ({listed})")
    return violations


def check_review_cites(
    cite_keys: Iterable[str | None], store_keys: frozenset[str]
) -> None:
    unknown = sorted({k for k in cite_keys if k} - store_keys)
    if unknown:
        raise ValidationError([f"review cites unknown key: {k}" for k in unknown])
