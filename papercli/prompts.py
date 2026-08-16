"""One small prompt per run type; capability lives in the sandbox skills, not here."""

REVIEW = """Peer-review the paper in this repo. main.tex is the paper; refs.json holds its resolved references.

Write your findings to {review_xml} in exactly this structure (validated against a schema afterwards):

<review paper="short paper title">
  <finding kind="missing-citation" severity="minor" confidence="0.8">
    <section>Related Work</section>
    <claim>the claim or gap this finding is about, quoted or paraphrased from the paper</claim>
    <source api="openalex" id="W2741809807"/>
    <note>What a careful human reviewer would say, in full sentences.</note>
    <suggestion>The concrete action the author should take.</suggestion>
  </finding>
  <finding kind="unsupported-claim" severity="major" confidence="0.7">
    <section>Introduction</section>
    <claim>the sentence carrying the citation</claim>
    <cite key="somekey"/>
    <source api="semanticscholar" id="abc123"/>
    <verdict>unsupported</verdict>
    <note>Why the cited work does not back this claim.</note>
  </finding>
</review>

Element order inside a finding is fixed: section?, claim?, cite*, source+, verdict?, note, suggestion?. Allowed kinds: missing-citation, unsupported-claim, weak-support, structure, other. Severity: minor|major. Confidence: 0-1, your honest estimate. Verdict, on findings that judge an existing citation: supported|partial|unsupported and nothing else — a weak-support finding still takes partial or unsupported.

Rules:
- Every source id must come verbatim from the search-sources skill, logged to {sources_json}. For unsupported-claim/weak-support findings about a cited work, the source is that work itself — its ids are in refs.json under custom.
- Judge existing citations with the cited-abstracts skill: claim against abstract, then a verdict.
- Every <cite key> must exist in refs.json.
- Write nothing outside {review_dir}. A review never edits the paper or the reference store: afterwards the diff is checked against that directory and a run that strayed is rejected whole, findings included.
- Aim for the handful of findings a good human reviewer would actually raise — specific, actionable, grounded — not bulk.
"""

EDIT = """Apply this instruction to the paper in main.tex:

{command}

Follow the edit-contract skill: edit only main.tex, keep it compiling with tectonic, never drop a \\cite key, cite only keys present in refs.json — adding new ones via search-sources + addref (log to {sources_json}) when the instruction needs sources that are not in the store. Run `papercli validate` before finishing and fix what it reports. Stay minimal and preserve the author's voice.
"""
