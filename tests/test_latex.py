from collections import Counter
from pathlib import Path

from papercli.latex import Section, cite_multiset, parse_latex

FIXTURE = Path(__file__).parents[1] / "e2e" / "fixtures" / "rankless-incomplete.tex"


def test_rankless_fixture():
    paper = parse_latex(FIXTURE.read_text())
    assert paper.title is not None and paper.title.startswith(
        "Rankless: Data-Specific Compilation"
    )
    assert paper.abstract is not None and "data-specific compilation" in paper.abstract
    assert [s.title for s in paper.sections if s.level == 1] == [
        "Introduction",
        "System Architecture",
        "Performance Evaluation",
        "Demonstration Scenario",
        "Related Work",
        "Conclusion",
    ]
    assert paper.citations["openalex"] == 3
    assert len(paper.references) == 5
    assert paper.unresolved == ["leiden"]
    assert paper.uncited == ["scimago"]


def test_nested_braces_comments_and_variants():
    src = r"""\title{The \texttt{nested} title}% trailing comment
% \cite{ghost} commented out entirely
\section{A \emph{fancy} section}
\cite{a,b}\citep{a}
\begin{thebibliography}{9}
\bibitem{a} Author A: Something (2020)
\bibitem{b} Author B: Else (2021)
\end{thebibliography}"""
    paper = parse_latex(src)
    assert paper.title == r"The \texttt{nested} title"
    assert paper.sections == [Section(1, r"A \emph{fancy} section")]
    assert paper.citations == {"a": 2, "b": 1}
    assert paper.unresolved == [] and paper.uncited == []


def test_citestyle_is_not_a_citation():
    paper = parse_latex(r"\citestyle{acmnumeric}\section{S}\cite{real}")
    assert paper.citations == {"real": 1}
    assert paper.unresolved == ["real"]


def test_every_cite_family_command_counts():
    """The multiset the edit validator diffs: a form missed here is a citation
    an edit can drop unnoticed, which is the one thing that must never happen."""
    src = r"""
    \cite{a} \citep{b} \Citet{c}
    \citep[see][p.~3]{d}
    \parencite{e} \autocite{f} \textcite{g} \footcite{h}
    \cite{i,j}
    \nocite{*}
    """
    assert dict(cite_multiset(src)) == {k: 1 for k in "abcdefghij"}


def test_style_setters_and_comments_are_not_citations():
    src = "\\citestyle{acmnumeric}\n\\bibliographystyle{plain}\n% \\cite{ghost}\n"
    assert cite_multiset(src) == Counter()


def test_no_bibliography_is_not_an_error():
    paper = parse_latex(r"\section{Only} \cite{orphan}")
    assert paper.references == []
    assert paper.unresolved == ["orphan"]
