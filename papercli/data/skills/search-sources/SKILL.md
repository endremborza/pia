---
name: search-sources
description: Search Semantic Scholar and OpenAlex for real papers on a topic, claim or title. The only permitted way to find sources.
---

Run from the repo root:

    papercli search --log <sources.json path given in your task> "<query>"

It prints JSON: `{"query", "records": [{source, title, authors, year, journal, doi, url, abstract, ids: {...}}], "failures": [...]}` and appends the same records to the log file.

Grounding rule: any `<source api="..." id="..."/>` you write must copy an id verbatim from a record's `ids` field in this command's output. Never invent, complete, or adapt an id. An empty result or a failure entry is a reportable fact — report it, do not guess around it.

Search by claim or topic, not just title; run several targeted queries rather than one broad one.
