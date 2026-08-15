# Paper Improvement Agent

Upload a research paper, get a peer review grounded in real academic search (Semantic Scholar + OpenAlex), and improve it with natural-language commands without breaking its citations.

## Three tools and a frontend

The app is the combination of three libraries, each with one job. Only hallubib existed before this take-home — the other two were written for it.

| Tool | Job | At kickoff |
| --- | --- | --- |
| [paritex](https://github.com/endremborza/paritex) | PDF → **papercli repo**: text/layout extraction, LLM-assisted reconstruction, word-level parity checking against the original | new, built alongside this app |
| **papercli** (this repo) | iterate on a papercli repo: parse, review, natural-language edit, export — the repo layout is defined here | new |
| [hallubib](https://pypi.org/project/hallubib/) | resolve and verify every reference against OpenAlex / Semantic Scholar / Crossref / arXiv; the confidence taxonomy | mine, partially built before — published on PyPI, used on my own submissions |

The web app is a thin frontend over that combination: it imports the same core functions `papercli` exposes as commands, never shells out to the CLI.

## Why a papercli repo, and not the PDF

A PDF is a rendering. For an LLM, working on a rendering is much closer to working on an image than to working on text — and models are dramatically worse there. A model will happily draw a hand with six fingers, but it will not complete *"the number of fingers a person usually has on one hand is"* with *"six"*. Same model, same fact; the only difference is the representation. Editing a paper as a PDF is the six-finger case: glyph runs and coordinates, no idea what a citation is. Editing it as source is the sentence case.

So conversion is the pipeline's first move, not its last. A PDF upload is reconstructed into a papercli repo before any review, edit or export happens, and every downstream step reads that one canonical representation. This is also what the assignment recommends — I just do it up front, and measure what the conversion cost.

A papercli repo is a directory with a fixed layout, under its own git repository:

- `main.tex` — canonical; the only thing edits ever touch.
- `refs.json` — the CSL-JSON store keyed by cite key, the single reference model; `refs.bib` is regenerated from it for builds.
- `assets/`, `report.json` (parity, PDF uploads only), `papercli.toml`, `reviews/N/review.xml`.
- and, when the repo came from a real paper project rather than a PDF: the code that generates the figures and tables.

### Git, because agents are good at it

There is no database. The repo is the only durable state — every pipeline step is a commit, milestones are tags (`parse/1`, `review/2`, `export/1`), and following a paper's progress is reading its history. That choice is not just storage minimalism: git is the one tool coding agents are already unusually fluent in, so "work on a branch, show a diff, merge or drop it" needs no bespoke mechanism. Agent runs happen on a proposal branch; approving is a server-side fast-forward merge, rejecting deletes the branch; the agent never advances main. And a paper whose history is a commit log is a step toward reproducible research for free.

### The layer a PDF cannot give back

In a real paper project, Figure 3 is not a picture — it is a script plus its data. A papercli repo keeps that: `papercli build` can run the project's own figure/table generation before tectonic, opt-in per project via `papercli.toml`. Start from a PDF and that layer is simply gone; reconstruction recovers text, structure and citations, never the code that produced the numbers. It is the strongest argument for keeping papers as source in the first place.

**Safety boundary:** the server never runs uploaded code. Web uploads are a single `.tex` file or a PDF, and the server only ever invokes tectonic on them. Multi-file projects — assets, build scripts, generation code — are adopted locally with `papercli init ./my-paper`, on code you already trust; running that code is a CLI-only feature, deliberately.

## Pipeline

1. **Ingest.** A PDF, a `.tex` upload, or `papercli init` on an existing project directory — the latter two skip reconstruction entirely (for arXiv papers the source exists anyway).
2. **Reconstruct** (PDF only). pymupdf text + layout extraction → structure heuristics → LLM-assisted LaTeX generation, into the papercli repo layout.
3. **Parity loop** (PDF only). tectonic compiles the reconstruction, paritex aligns it word-level against the original and scores the divergence, diverging blocks get patched, the loop reruns until parity converges. The report is committed and shown in the UI: the user sees exactly what survived verbatim before trusting any review or edit.
4. **Parse.** Structure and `\cite` markers come straight from the LaTeX. Reference entries go through hallubib — resolved against OpenAlex, Semantic Scholar, Crossref and arXiv — and matched records become CSL-JSON. Unresolved entries stay visible under hallubib's five-status confidence taxonomy; nothing is silently dropped. Citation style is detected from the markers and mapped to a CSL style, user-overridable.
5. **Review** (on request). Claims are extracted per section, Semantic Scholar and OpenAlex are searched for plausibly-missing work, and each existing citation's abstract is fetched so the agent can judge whether the claim is actually supported. Every finding carries a source id taken verbatim from an API response — ids are never generated.
6. **Edit.** A natural-language command is planned into typed operations (`insert_citation`, `tighten_section`, …) which code applies as LaTeX patches on a proposal branch. The user sees the diff and approves or rejects.
7. **Export.** tectonic builds the final PDF; the bibliography renders from CSL-JSON through citeproc with the paper's `.csl` style — no hand-formatted references anywhere in the system.

## Invariants

- **Citations survive edits by construction.** An in-text citation is a `\cite{key}`; its reference is a CSL-JSON record under the same key. Text can move, shrink or merge and the marker travels with it. A validator diffs the cite-key multiset and the reference store before and after every change, and refuses violating commits — "nothing breaks silently" is enforced by the store, not by convention.
- **Every intermediate state is a real, compilable paper.** tectonic renders it at any point, so the preview is always the actual export.
- **Code executes, the agent judges.** Parsing, hallubib resolution, parity scoring, citeproc rendering and validation are plain functions the server runs and commits. The agent is reserved for claim extraction, support verdicts, edit planning and reconstruction refinement — never for running a fixed command.
- **Source honesty.** Every id, DOI and title shown to the user is verbatim from an API response. Unresolved references, empty searches, low-confidence matches and parity gaps are surfaced, not swallowed.
- **Nothing regenerable is committed.** Rendered PDFs are rebuilt on demand; the original PDF is committed only when it was the upload, as reconstruction ground truth.

## Stack

- Backend: Python 3.13, uv-managed — `papercli` + FastAPI over one core, hallubib, paritex, pymupdf, citeproc-py, lxml.
- Agent runs: Claude Code headless (`claude -p`) behind a swappable runner interface, which natively picks up the skills defined in the repo; the Claude Agent SDK is the drop-in successor.
- Frontend: SvelteKit, Svelte 5, TypeScript. Deliberately plain: semantic HTML, small components, no CSS framework.
- tectonic for all LaTeX builds.

## Run

```bash
uv sync && npm install                        # deps (backend + frontend)
uv run uvicorn paper_agent.api:app --reload   # backend on :8000
npm run dev                                   # frontend on :5173, proxies /api
```

Working so far: upload with a LaTeX/PDF format choice; a `.tex` upload is parsed into a structure view (sections, in-text citations, references) that surfaces dangling citations and uncited references instead of hiding them. PDF upload states its limitation honestly until the paritex reconstruction lands.

```bash
uv run pytest    # backend unit tests
npm test         # end-to-end -- Playwright starts both servers itself
npm run demo     # headed, slowed-down walkthrough on an incomplete version of a real paper; screen-recordable
```

## System design

The two graded pieces, in depth:

- [docs/citation-parsing.md](docs/citation-parsing.md) — PDF → papercli repo → normalized CSL-JSON citations: pipeline steps, intermediate representation, style handling, failure surfacing.
- [docs/agent.md](docs/agent.md) — peer review and natural-language editing: command → plan → typed operations, Semantic Scholar / OpenAlex integration, citation integrity across edits.

## AI use

TBD -- where AI tools were used and what was verified by hand.

## Limitations

TBD -- known limitations and what would come next with more time.
