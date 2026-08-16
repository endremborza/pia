import re
from collections import Counter
from dataclasses import dataclass

_COMMENT = re.compile(r"(?<!\\)%.*")
# Every \cite-family command, because the multiset this feeds is what the edit
# validator diffs: a form we do not match is a citation an edit may drop
# unnoticed. So: any command with `cite` in its name (natbib's \citep/\Citet,
# biblatex's \parencite/\autocite/\textcite/\footcite, \nocite), and up to two
# optional arguments — `\citep[see][p.~3]{key}` is ordinary natbib.
# Excluded: \citestyle{acmnumeric} (acmart, natbib) names a style, not a key.
_CITE = re.compile(
    r"\\[A-Za-z]*[cC]ite(?!style)[A-Za-z]*\*?\s*(?:\[[^\]]*\]\s*){0,2}\{"
)
_BIBITEM = re.compile(r"\\bibitem(?:\[[^\]]*\])?\{")
_WS = re.compile(r"\s+")

_SECTION_LEVELS = {"section": 1, "subsection": 2, "subsubsection": 3}


@dataclass(frozen=True)
class Section:
    level: int
    title: str


@dataclass(frozen=True)
class Reference:
    key: str
    text: str


@dataclass(frozen=True)
class ParsedPaper:
    title: str | None
    abstract: str | None
    sections: list[Section]
    citations: dict[str, int]
    references: list[Reference]
    unresolved: list[str]
    uncited: list[str]


def parse_latex(source: str) -> ParsedPaper:
    src = strip_comments(source)
    citations = _citations(src)
    references = _references(src)
    ref_keys = {r.key for r in references}
    return ParsedPaper(
        title=next((arg for _, arg in _command_args(src, "title")), None),
        abstract=_environment(src, "abstract"),
        sections=_sections(src),
        citations=dict(citations),
        references=references,
        unresolved=sorted(set(citations) - ref_keys),
        uncited=[r.key for r in references if r.key not in citations],
    )


def strip_comments(source: str) -> str:
    return _COMMENT.sub("", source)


def cite_multiset(source: str) -> Counter[str]:
    return _citations(strip_comments(source))


def _balanced(source: str, brace_at: int) -> tuple[str, int]:
    depth = 0
    for i in range(brace_at, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[brace_at + 1 : i], i + 1
    raise ValueError(f"unbalanced braces at offset {brace_at}")


def _command_args(source: str, name: str) -> list[tuple[int, str]]:
    pattern = re.compile(r"\\" + name + r"\*?(?:\[[^\]]*\])?\{")
    return [
        (m.start(), _balanced(source, m.end() - 1)[0]) for m in pattern.finditer(source)
    ]


def _environment(source: str, name: str) -> str | None:
    match = re.search(
        r"\\begin\{" + name + r"\}(.*?)\\end\{" + name + r"\}", source, re.DOTALL
    )
    return _WS.sub(" ", match.group(1)).strip() if match else None


def _sections(source: str) -> list[Section]:
    found = [
        (pos, Section(level, _WS.sub(" ", arg).strip()))
        for cmd, level in _SECTION_LEVELS.items()
        for pos, arg in _command_args(source, cmd)
    ]
    return [section for _, section in sorted(found, key=lambda p: p[0])]


def _citations(source: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for m in _CITE.finditer(source):
        keys, _ = _balanced(source, m.end() - 1)
        counts.update(k.strip() for k in keys.split(",") if k.strip())
    del counts["*"]  # \nocite{*} means "all of them", not a key named *
    return counts


def _references(source: str) -> list[Reference]:
    bib = _environment(source, "thebibliography")
    if bib is None:
        return []
    entries = []
    matches = list(_BIBITEM.finditer(bib))
    for m, next_m in zip(matches, [*matches[1:], None]):
        key, text_start = _balanced(bib, m.end() - 1)
        end = next_m.start() if next_m else len(bib)
        text = _WS.sub(" ", bib[text_start:end]).strip()
        entries.append(Reference(key=key.strip(), text=text))
    return entries
