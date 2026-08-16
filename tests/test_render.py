from papercli.render import (
    AUTHOR_YEAR_STYLE,
    NUMERIC_STYLE,
    bibliography_tex,
    detect_style,
    ensure_input_line,
    escape_latex,
)

ITEMS = {
    "priem2022": {
        "id": "priem2022",
        "type": "article-journal",
        "title": "OpenAlex: an index with 100% coverage & more",
        "author": [{"family": "Priem", "given": "Jason"}],
        "issued": {"date-parts": [[2022]]},
    },
    "shannon2003": {
        "id": "shannon2003",
        "type": "article-journal",
        "title": "Cytoscape",
        "author": [
            {"family": "Shannon", "given": "Paul"},
            {"family": "Markiel", "given": "Andrew"},
            {"family": "Ozier", "given": "Owen"},
        ],
        "container-title": "Genome Research",
        "issued": {"date-parts": [[2003]]},
    },
}


def test_detect_style():
    assert detect_style(r"\cite{a} plain") == NUMERIC_STYLE
    assert detect_style(r"\citep{a} natbib") == AUTHOR_YEAR_STYLE
    assert detect_style("\\usepackage{natbib}\n\\cite{a}") == AUTHOR_YEAR_STYLE
    assert detect_style("% \\citep{a} commented\n\\cite{a}") == NUMERIC_STYLE


def test_numeric_bibliography_escapes_and_orders():
    tex = bibliography_tex(ITEMS, NUMERIC_STYLE)
    assert tex.index("priem2022") < tex.index("shannon2003")
    assert r"100\% coverage \& more" in tex
    assert tex.startswith("\\begin{thebibliography}")


def test_author_year_labels():
    tex = bibliography_tex(ITEMS, AUTHOR_YEAR_STYLE)
    assert "\\bibitem[{Priem(2022)}]{priem2022}" in tex
    assert "\\bibitem[{Shannon et al.(2003)}]{shannon2003}" in tex


def test_ensure_input_line_replaces_inline_bibliography():
    tex = "body\n\\begin{thebibliography}{9}\\bibitem{a} x\\end{thebibliography}\n\\end{document}"
    out = ensure_input_line(tex)
    assert "thebibliography" not in out
    assert "\\input{bibliography}" in out
    assert ensure_input_line(out) == out


def test_ensure_input_line_replaces_bibtex_commands():
    tex = "body\n\\bibliographystyle{plain}\n\\bibliography{refs}\n\\end{document}"
    out = ensure_input_line(tex)
    assert "\\bibliographystyle" not in out
    assert "\\input{bibliography}" in out


def test_ensure_input_line_appends_when_absent():
    out = ensure_input_line("body\n\\end{document}")
    assert out.index("\\input{bibliography}") < out.index("\\end{document}")


def test_escape_latex():
    assert escape_latex(r"50% of $x & #1_2") == r"50\% of \$x \& \#1\_2"
    assert escape_latex("pp. 2498–2504, “quoted”") == "pp. 2498--2504, ``quoted''"
    assert escape_latex("a {braced} title") == r"a \{braced\} title"


MIXED_CASE = {
    "Smith2020": {
        "id": "Smith2020",
        "type": "article-journal",
        "title": "Mixed case key",
        "author": [{"family": "Smith", "given": "Ada"}],
        "issued": {"date-parts": [[2020]]},
    }
}


def test_cite_key_case_survives_citeproc():
    """citeproc folds ids to lowercase; \\bibitem must still match the paper's \\cite."""
    for style in (NUMERIC_STYLE, AUTHOR_YEAR_STYLE):
        assert "{Smith2020}" in bibliography_tex(MIXED_CASE, style)
