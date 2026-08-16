# API budgets

What the free tiers of the source APIs allow, what a papercli operation costs against them, and where the keys go. Numbers checked against the providers' docs on 2026-08-15; the linked pages are authoritative if they drift.

## Where the keys go

Everything is set in the repo's gitignored `.env` (start from [`.env.sample`](../.env.sample)); launchers load it (`uv run --env-file .env ...`, Playwright reads it itself). Env beats config-file keys.

- `HALLUBIB_MAILTO` — your contact address, sent in the User-Agent to OpenAlex, Crossref and arXiv (the "polite pool"). Free, no signup, always set it.
- `OPENALEX_API_KEY` — make an account and copy the key from [openalex.org/settings/api](https://openalex.org/settings/api) (~30 seconds); docs: [authentication](https://help.openalex.org/api/authentication/), [costs](https://help.openalex.org/access/example-costs/).
- `S2_API_KEY` — request the free key via the form at [semanticscholar.org/product/api](https://www.semanticscholar.org/product/api); it arrives by email.
- Crossref, arXiv and doi.org need no key at all.

## The tiers

| Service | Keyless | Free key | Hard limits |
| --- | --- | --- | --- |
| OpenAlex | $0.10/day of credits (~100 searches) | $1/day (~1,000 searches) | 100 req/s; by-ID/DOI fetches are free, filtered lists ~$0.0001, searches ~$0.001 |
| Semantic Scholar | one globally shared, throttled pool — expect 429s | a steady 1 request/second, no daily cap | hallubib already paces S2 at 1.1s, so the free key removes the constraint entirely |
| Crossref | no quotas, etiquette-based | — | identify via mailto, honor rate-limit headers, back off on 4xx; hallubib paces at 20/s and caches |
| arXiv | no quotas | — | 3s between requests per their ToS; hallubib paces at 3.0s |

OpenAlex's keyless daily budget is what a day of anonymous testing exhausts (observed as a 429 with retry-after ≈ 7.5h). The Semantic Scholar shared pool is what 429'd 13 of 14 review-agent queries in one real run.

## What papercli costs per operation

hallubib's resolution ladder means a DOI-carrying reference costs a free OpenAlex by-DOI fetch, while a title-resolved reference costs 1–2 OpenAlex searches plus paced Semantic Scholar / Crossref / arXiv calls. Results are disk-cached for 30 days, so re-running on the same paper is essentially free.

- Resolving a 30-reference paper: ~$0.01–0.06 of OpenAlex credits, ≤30 S2 calls (~35s at 1 rps); wall time is pacing-bound, not quota-bound.
- A peer review: the agent's 4–10 search-skill queries ≈ $0.01 of OpenAlex credits plus as many S2 relevance calls.
- Edits and exports: no API calls at all (store and cache only).

## What that buys per day

- Keyless + mailto only: roughly 1–3 cold paper resolutions plus a review or two — workable for cached development, tight for anything more.
- Both free keys: ~15–30 cold papers or ~50–100 reviews — the whole dev/demo/example-deployment cycle at $0, comfortably inside the free tiers.
