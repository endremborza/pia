from pathlib import Path

import pytest

from papercli.review import validate_xml
from papercli.validator import ValidationError

GOOD = """<review paper="Rankless">
  <finding kind="missing-citation" severity="minor" confidence="0.8">
    <section>Related Work</section>
    <claim>bibliometrics tooling exists</claim>
    <source api="openalex" id="W2741809807"/>
    <note>Consider engaging the OpenAlex index paper.</note>
    <suggestion>Cite it in related work.</suggestion>
  </finding>
  <finding kind="unsupported-claim" severity="major" confidence="0.6">
    <claim>the cited work proves X</claim>
    <cite key="openalex"/>
    <source api="semanticscholar" id="abc123"/>
    <verdict>unsupported</verdict>
    <note>The abstract does not mention X.</note>
  </finding>
</review>
"""

UNGROUNDED = """<review paper="p">
  <finding kind="other" severity="minor" confidence="0.5">
    <note>a finding with no source at all</note>
  </finding>
</review>
"""

BAD_KIND = """<review paper="p">
  <finding kind="vibes" severity="minor" confidence="0.5">
    <source api="openalex" id="W1"/>
    <note>n</note>
  </finding>
</review>
"""


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "review.xml"
    path.write_text(content)
    return path


def test_valid_review_accepted(tmp_path: Path):
    root = validate_xml(_write(tmp_path, GOOD))
    assert len(root.findall("finding")) == 2


def test_sourceless_finding_unrepresentable(tmp_path: Path):
    with pytest.raises(ValidationError, match="schema violation"):
        validate_xml(_write(tmp_path, UNGROUNDED))


def test_unknown_kind_rejected(tmp_path: Path):
    with pytest.raises(ValidationError, match="schema violation"):
        validate_xml(_write(tmp_path, BAD_KIND))
