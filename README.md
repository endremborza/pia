# Paper Improvement Agent

Upload a research paper, get a peer review grounded in real academic search (Semantic Scholar + OpenAlex), and improve it with natural-language commands without breaking its citations.

## Three tools and a frontend

The app is the combination of three libraries, each with one job.

| Tool | Job |
| --- | --- |
| [paritex](https://github.com/endremborza/paritex) | PDF → **papercli repo**: text/layout extraction, LLM-assisted reconstruction, word-level parity checking against the original |
| **papercli** (this repo) | iterate on a papercli repo: parse, review, natural-language edit, export — the repo layout is defined here |
| [hallubib](https://pypi.org/project/hallubib/) | resolve and verify every reference against OpenAlex / Semantic Scholar / Crossref / arXiv; the confidence taxonomy |

All three are libraries, this one included: this repo *is* the `papercli` package — `uvx papercli init ./my-paper` and it works on a paper without a web app anywhere in sight. The deliverable is a tool, not app glue.

The web app is a thin frontend over that combination: it imports the same core functions `papercli` exposes as commands, never shells out to the CLI. It ships as the package's optional `[server]` extra, so installing the library pulls in no web stack at all.

## Why a papercli repo, and not the PDF

A PDF is a rendering. For an LLM, working on a rendering is much closer to working on an image than to working on text — and models are dramatically worse there. A model will happily draw a hand with six fingers, but it will not complete *"the number of fingers a person usually has on one hand is"* with *"six"*. Same model, same fact; the only difference is the representation. Editing a paper as a PDF is the six-finger case: glyph runs and coordinates, no idea what a citation is. Editing it as source is the sentence case.

So conversion is the pipeline's first move, not its last. A PDF upload is reconstructed into a papercli repo before any review, edit or export happens, and every downstream step reads that one canonical representation. Rebuilding the paper as LaTeX is the usual advice for surviving an export round trip; the difference here is doing it up front, once, and measuring what the conversion cost.

A papercli repo is a directory with a fixed layout, under its own git repository:

- `main.tex` — canonical; the only thing edits ever touch.
- `refs.json` — the CSL-JSON store keyed by cite key, the single reference model; `refs.bib` is regenerated from it for builds.
- `assets/`, `report.json` (parity, PDF uploads only), `reviews/N/review.xml`.
- and, when the repo came from a real paper project rather than a PDF: the code that generates the figures and tables, plus the `pyproject.toml` that declares its dependencies — and, under `[tool.papercli]`, its papercli settings. There is no `papercli.toml`: a paper that builds its own figures is already a Python project, and config belongs next to the deps that make it runnable. Repos reconstructed from a PDF have no code, so they need no repo-level config at all.

### Git, because agents are good at it

There is no database. The repo is the only durable state — every pipeline step is a commit, milestones are tags (`parse/1`, `review/2`, `export/1`), and following a paper's progress is reading its history. That choice is not just storage minimalism: git is the one tool coding agents are already unusually fluent in, so "work on a branch, show a diff, merge or drop it" needs no bespoke mechanism. Agent runs happen on a proposal branch; approving is a server-side fast-forward merge, rejecting deletes the branch; the agent never advances main. And a paper whose history is a commit log is a step toward reproducible research for free.

### The layer a PDF cannot give back

In a real paper project, Figure 3 is not a picture — it is a script plus its data. A papercli repo keeps that: `papercli init` adopts the generation code and its `pyproject.toml` along with the paper, and versions them together. Start from a PDF and that layer is simply gone; reconstruction recovers text, structure and citations, never the code that produced the numbers. It is the strongest argument for keeping papers as source in the first place.

**Safety boundary:** the server never runs uploaded code. Web uploads are a single `.tex` file or a PDF, and the server only ever invokes tectonic on them. Multi-file projects — assets, build scripts, generation code — are adopted locally with `papercli init ./my-paper`, on code you already trust; running that code is a CLI-only feature, deliberately. Public deployments set `PAPERCLI_PASSWORD`, which gates every request (bar the health probe) behind HTTP Basic — uploads and agent runs cost real compute, so an open instance is a choice, never a default.

## Pipeline

1. **Ingest.** A PDF, a `.tex` upload, or `papercli init` on an existing project directory — the latter two skip reconstruction entirely (for arXiv papers the source exists anyway).
2. **Reconstruct** (PDF only). pymupdf text + layout extraction → structure heuristics → LLM-assisted LaTeX generation, into the papercli repo layout.
3. **Parity** (PDF only). tectonic compiles the reconstruction, paritex aligns it word-level against the original and scores the divergence; a structural bibliography gate runs alongside. The report is committed: reconstruction loss is measured up front, not discovered at export — and shown to the user before any further spend.
4. **Accept** (PDF only). The reconstruction is a *guess* — a paper's source is not recoverable from its rendering — so the user rules on it: rebuilt PDF beside the original, remaining divergences, extracted citations. Accept and the repo is tagged `parse/N`; refine and this candidate goes back to the agent with the user's instruction plus the measured divergences; re-run and a fresh reconstruction starts from the committed original, no re-upload — model and effort are the user's dials on every reconstruction pass. This is the only time a human validates what the paper *is*; everything after it is a reviewable diff.
5. **Parse.** Structure and `\cite` markers come straight from the LaTeX. Reference entries go through hallubib — resolved against OpenAlex, Semantic Scholar, Crossref and arXiv — and matched records become CSL-JSON. Unresolved entries stay visible under hallubib's five-status confidence taxonomy; nothing is silently dropped. Citation style is detected from the markers and mapped to a CSL style, user-overridable.
6. **Review** (on request). Claims are extracted per section, Semantic Scholar and OpenAlex are searched for plausibly-missing work, and each existing citation's abstract is fetched so the agent can judge whether the claim is actually supported. Every finding carries a source id taken verbatim from an API response — ids are never generated.
7. **Edit.** A natural-language command becomes an agent run inside the repo sandbox, on a proposal branch: the agent edits the LaTeX directly, then code enforces the contract — allowed paths only, tectonic must compile, the citation validator must pass — and a violating run is rejected wholesale. The user sees the diff and approves or rejects.
8. **Export.** tectonic builds the final PDF; the bibliography renders from CSL-JSON through citeproc with the paper's `.csl` style — no hand-formatted references anywhere in the system.

Steps 1–4 run once per paper. That is the point of converting up front: PDF parsing is the expensive, error-prone step, so it is paid for once and reviewed once, and every later round reads source instead of re-rolling the dice on a rendering.

## Invariants

- **Citations survive edits by construction.** An in-text citation is a `\cite{key}`; its reference is a CSL-JSON record under the same key. Text can move, shrink or merge and the marker travels with it. A validator diffs the cite-key multiset and the reference store before and after every change, and refuses violating commits — "nothing breaks silently" is enforced by the store, not by convention.
- **Every intermediate state is a real, compilable paper.** tectonic renders it at any point, so the preview is always the actual export.
- **Code executes, the agent judges.** Parsing, hallubib resolution, parity scoring, citeproc rendering and validation are plain functions the server runs and commits. The agent is reserved for claim extraction, support verdicts, edit planning and reconstruction refinement — never for running a fixed command.
- **Source honesty.** Every id, DOI and title shown to the user is verbatim from an API response. Unresolved references, empty searches, low-confidence matches and parity gaps are surfaced, not swallowed.
- **Nothing regenerable is committed.** Rendered PDFs are rebuilt on demand; the original PDF is committed only when it was the upload, as reconstruction ground truth.

## Stack

- Backend: Python 3.13, uv-managed, hatchling-built — the `papercli` package: CLI + FastAPI (an optional extra) over one core, hallubib, paritex, pymupdf, citeproc-py, lxml.
- Agent runs: Claude Code headless (`claude -p`) behind a swappable runner interface, which natively picks up the skills defined in the repo; the Claude Agent SDK is the drop-in successor.
- Frontend: SvelteKit, Svelte 5, TypeScript. Deliberately plain: semantic HTML, small components, no CSS framework.
- tectonic for all LaTeX builds.

## Run

```bash
make setup     # uv sync --extra server, npm install, .env from .env.sample
make dev       # backend on :8000 (loads .env) + frontend on :5173
```

`make help` lists every target; the Makefile is four commands deep, no magic — the raw invocations are one `cat Makefile` away.

`.env` (gitignored) holds service identity and agent selection; `.env.sample` documents every variable, including how far the free tiers go. The agent default is `claude-code` — the box's Claude Code login, with Anthropic auth env vars scrubbed so an exported API key can never bill silently; set `PAPERCLI_AGENT_BACKEND=claude-api` to spend API credits deliberately.

`uv sync` without `--extra server` gives you the library and the CLI alone — `uv run papercli parse paper.tex` needs no web stack.

The whole loop works in the browser: upload a `.tex` or PDF; PDFs are reconstructed by paritex and gated on your acceptance (rebuilt PDF beside the original, parity score, divergences); references resolve through hallubib into the CSL-JSON store with their confidence statuses shown as-is; peer review runs as an agent in the repo sandbox and lands as schema-validated, source-grounded findings; edits run on proposal branches behind the citation validator and reach you as diffs to approve; export builds the PDF with a citeproc-rendered bibliography. The same verbs work headless: `papercli init | status | review | do | approve | reject | export | accept | refine | rerun`.

```bash
make test        # unit tests + headless browser e2e (Playwright starts both servers itself)
make test-all    # also runs the hallubib and paritex suites
make check       # pyright + ruff + svelte-check
```

The browser walkthrough runs against a scripted backend (`e2e/fixtures/papercli-e2e.toml`), so it needs no LLM credentials — but it does resolve references against the live APIs, so it wants network and a `HALLUBIB_MAILTO`.

## System design

The two load-bearing pieces, in depth:

- [docs/citation-parsing.md](docs/citation-parsing.md) — PDF → papercli repo → normalized CSL-JSON citations: pipeline steps, intermediate representation, style handling, failure surfacing.
- [docs/agent.md](docs/agent.md) — peer review and natural-language editing: command → sandboxed agent run → code-enforced gates, Semantic Scholar / OpenAlex integration, citation integrity across edits.
