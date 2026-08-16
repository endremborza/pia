---
name: edit-contract
description: The rules every edit to main.tex must satisfy, and the validate/addref commands that keep an edit inside them.
---

The gate that runs after you finish enforces: only `main.tex` (plus store-derived files) may change; the paper must compile with `tectonic main.tex`; no `\cite` key may be dropped; new `\cite` keys must exist in `refs.json`; and every reference *added* to `refs.json` must carry a source id from this run's fetch log. A violating run is rejected wholesale.

Self-check before finishing:

    papercli validate

prints the violations the gate would raise (exit 0 = clean). Fix them, don't argue with them.

To cite a work that is not in the store yet: find it with the search-sources skill, then

    papercli addref <source-id> --log <sources.json path>

adds that fetched record to refs.json under a generated cite key and prints the key; only then may you `\cite` it. Never edit refs.json, refs.bib or bibliography.tex by hand — an entry written directly into the store has no fetch-log id behind it and fails the gate, taking the whole run with it.
