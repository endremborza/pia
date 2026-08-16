"""Bibliography rendering: CSL-JSON through citeproc with .csl styles, never templates.

The store renders into bibliography.tex (a generated thebibliography block that
main.tex inputs), and refs.bib is derived alongside for LaTeX-toolchain interop.
tectonic builds go through paritex.render — the one tectonic wrapper in the system.
"""

import atexit
import re
from contextlib import ExitStack
from importlib.resources import as_file, files
from pathlib import Path

from citeproc import (
    Citation,
    CitationItem,
    CitationStylesBibliography,
    CitationStylesStyle,
    formatter,
)
from citeproc.source.json import CiteProcJSON
from paritex import MAIN_TEX, render

from papercli.latex import cite_multiset, strip_comments
from papercli.refs import derive_bib
from papercli.repo import BIBLIOGRAPHY_TEX

NUMERIC_STYLE = "ieee"
AUTHOR_YEAR_STYLE = "apa"

_AUTHOR_YEAR_MARKERS = re.compile(
    r"\\citep\b|\\citet\b|\\usepackage(?:\[[^\]]*\])?\{natbib\}"
)
_ESCAPES = {c: f"\\{c}" for c in "&%$#_{}"}
_ESCAPES |= {
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
    "–": "--",
    "—": "---",
    "“": "``",
    "”": "''",
    "‘": "`",
    "’": "'",
}
_ESCAPE_RE = re.compile("|".join(re.escape(c) for c in _ESCAPES))


def detect_style(tex: str) -> str:
    return (
        AUTHOR_YEAR_STYLE
        if _AUTHOR_YEAR_MARKERS.search(strip_comments(tex))
        else NUMERIC_STYLE
    )


_resources = ExitStack()
atexit.register(_resources.close)


def style_path(style: str) -> Path:
    if style.endswith(".csl"):
        return Path(style).expanduser()
    bundled = files("papercli").joinpath(f"data/styles/{style}.csl")
    return Path(_resources.enter_context(as_file(bundled)))


def render_entries(items: list[dict], style: str) -> dict[str, str]:
    """Render each item, keyed by the store's cite key.

    citeproc normalizes item ids to lowercase, so its keys are folded back onto
    the originals — otherwise a `Smith2020` entry renders as `\\bibitem{smith2020}`
    and the paper's own `\\cite{Smith2020}` finds nothing.
    """
    source = CiteProcJSON(
        [{k: v for k, v in item.items() if k != "custom"} for item in items]
    )
    csl = CitationStylesStyle(str(style_path(style)), validate=False)
    bibliography = CitationStylesBibliography(csl, source, formatter.plain)
    for item in items:
        bibliography.register(Citation([CitationItem(item["id"])]))
    rendered = [str(entry) for entry in bibliography.bibliography()]
    original = {str(item["id"]).lower(): str(item["id"]) for item in items}
    keys = [original.get(str(k).lower(), str(k)) for k in bibliography.keys]
    if len(keys) != len(rendered):
        raise ValueError(
            f"citeproc rendered {len(rendered)} entries for {len(keys)} keys"
        )
    return dict(zip(keys, rendered))


def bibliography_tex(items: dict[str, dict], style: str) -> str:
    if not items:
        return "% no references\n"
    entries = render_entries(list(items.values()), style)
    lines = [f"\\begin{{thebibliography}}{{{len(items)}}}"]
    for key, text in entries.items():
        label = _natbib_label(items[key]) if style == AUTHOR_YEAR_STYLE else None
        opt = f"[{{{escape_latex(label)}}}]" if label else ""
        lines.append(
            f"\\bibitem{opt}{{{key}}} {escape_latex(_strip_leading_number(text))}"
        )
    lines.append("\\end{thebibliography}")
    return "\n".join(lines) + "\n"


def write_bibliography(repo: Path, items: dict[str, dict], style: str) -> None:
    (repo / BIBLIOGRAPHY_TEX).write_text(bibliography_tex(items, style))


def refresh_derived(
    repo: Path, items: dict[str, dict], style: str | None = None
) -> str:
    """Regenerate everything derived from the store; returns the style used.

    The single place refs.bib and bibliography.tex are written — ingest, export,
    edits and reviews all land here instead of restating the sequence. Only
    in-text-cited entries reach the paper, in first-citation order.
    """
    tex = (repo / MAIN_TEX).read_text()
    resolved = style or detect_style(tex)
    derive_bib(repo, items)
    cited = cite_multiset(tex)
    write_bibliography(repo, {k: items[k] for k in cited if k in items}, resolved)
    return resolved


def build(repo: Path, tex: str = MAIN_TEX) -> Path:
    return render(repo, tex)


def _natbib_label(item: dict) -> str:
    families = [a.get("family") or a.get("literal", "") for a in item.get("author", [])]
    families = [f for f in families if f]
    parts = item.get("issued", {}).get("date-parts", [[]])
    year = str(parts[0][0]) if parts and parts[0] else "n.d."
    if not families:
        head = item.get("title", "?")[:24]
    elif len(families) == 1:
        head = families[0]
    elif len(families) == 2:
        head = f"{families[0]} and {families[1]}"
    else:
        head = f"{families[0]} et al."
    return f"{head}({year})"


def _strip_leading_number(entry: str) -> str:
    return re.sub(r"^\[?\d+\]?\s*", "", entry)


def escape_latex(text: str) -> str:
    return _ESCAPE_RE.sub(lambda m: _ESCAPES[m.group(0)], text)


def ensure_input_line(tex: str) -> str:
    """Normalize main.tex to input the generated bibliography exactly once."""
    input_line = f"\\input{{{BIBLIOGRAPHY_TEX.removesuffix('.tex')}}}"
    if input_line in tex:
        return tex
    replaced = re.sub(
        r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}",
        lambda _: input_line,
        tex,
        count=1,
        flags=re.DOTALL,
    )
    if replaced != tex:
        return replaced
    replaced = re.sub(r"\\bibliographystyle\{[^}]*\}\s*", "", tex)
    replaced, n = re.subn(
        r"\\bibliography\{[^}]*\}", lambda _: input_line, replaced, count=1
    )
    if n:
        return replaced
    return tex.replace("\\end{document}", input_line + "\n\\end{document}", 1)


__all__ = [
    "AUTHOR_YEAR_STYLE",
    "NUMERIC_STYLE",
    "bibliography_tex",
    "build",
    "detect_style",
    "ensure_input_line",
    "escape_latex",
    "refresh_derived",
    "render_entries",
    "write_bibliography",
]
