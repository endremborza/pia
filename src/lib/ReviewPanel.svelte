<script lang="ts">
	import { getReview } from './api';
	import Foldable from './Foldable.svelte';
	import type { Review } from './types';

	let {
		id,
		reviews,
		disabled,
		onstart
	}: { id: string; reviews: number[]; disabled: boolean; onstart: () => void } = $props();

	let review = $state<Review>();
	let loadError = $state<string>();
	let latest = $derived(reviews.at(-1));

	$effect(() => {
		if (latest === undefined) {
			review = undefined;
			return;
		}
		getReview(id, latest)
			.then((r) => {
				review = r;
				loadError = undefined;
			})
			.catch((err) => (loadError = err.message));
	});

	const verdictClass: Record<string, string> = {
		supported: 'ok',
		partial: 'warn',
		unsupported: 'bad'
	};
</script>

<Foldable>
	{#snippet summary()}
		Reviews
		{#each reviews as n (n)}<span class="chip">review/{n}</span>{/each}
	{/snippet}

	{#if !reviews.length}
		<p class="note">
			The review agent reads the paper, searches Semantic Scholar and OpenAlex for missing work,
			checks each claim against the cited work's abstract, and files findings that are only
			representable with a real source attached.
		</p>
	{/if}
	<button onclick={onstart} {disabled}>Request peer review</button>
	{#if loadError}<p class="error" role="alert">{loadError}</p>{/if}

	{#if review}
		<h4>
			Review {review.n} — {review.findings.length} finding{review.findings.length === 1 ? '' : 's'}
			<a class="pdf" href="/api/papers/{id}/reviews/{review.n}/pdf" target="_blank" rel="noreferrer">PDF</a>
		</h4>
		<ol class="findings">
			{#each review.findings as f, i (i)}
				<li>
					<p>
						<span class="kind">{f.kind}</span>
						<span class="sev {f.severity}">{f.severity}</span>
						<span class="conf">confidence {f.confidence}</span>
						{#if f.section}<span class="section">§ {f.section}</span>{/if}
						{#if f.verdict}<span class="verdict {verdictClass[f.verdict]}">{f.verdict}</span>{/if}
					</p>
					{#if f.claim}<blockquote>{f.claim}</blockquote>{/if}
					<p>{f.note}</p>
					{#if f.suggestion}<p class="suggestion">Suggested: {f.suggestion}</p>{/if}
					<p class="sources">
						{#if f.cites.length}
							cites {#each f.cites as key, c (c)}<code>{key}</code>{/each} ·
						{/if}
						{#each f.sources as s, j (j)}
							<a href={s.url} target="_blank" rel="noreferrer">{s.title ?? `${s.api}:${s.id}`}</a>
						{/each}
					</p>
				</li>
			{/each}
		</ol>
	{/if}
</Foldable>

<style>
	.chip {
		font-size: 0.8rem;
		background: #f3f4f6;
		color: #374151;
		border-radius: 0.6rem;
		padding: 0.15rem 0.5rem;
	}
	.findings li {
		margin-bottom: 1.25rem;
		border-left: 3px solid #d1d5db;
		padding-left: 0.75rem;
	}
	.kind {
		font-weight: 600;
	}
	.sev,
	.conf,
	.section,
	.verdict {
		font-size: 0.8rem;
		margin-left: 0.5rem;
		padding: 0.05rem 0.4rem;
		border-radius: 0.5rem;
		background: #f3f4f6;
		color: #374151;
	}
	.sev.major {
		background: #fee2e2;
		color: #b91c1c;
	}
	.verdict.ok {
		background: #dcfce7;
		color: #15803d;
	}
	.verdict.warn {
		background: #fef3c7;
		color: #b45309;
	}
	.verdict.bad {
		background: #fee2e2;
		color: #b91c1c;
	}
	blockquote {
		margin: 0.25rem 0;
		font-style: italic;
		color: #4b5563;
	}
	.suggestion {
		color: #0e7490;
	}
	.sources a {
		margin-right: 0.75rem;
	}
	.sources code {
		margin-right: 0.3rem;
	}
	.pdf {
		font-size: 0.85rem;
		margin-left: 0.75rem;
	}
	.note {
		font-size: 0.9rem;
		color: #4b5563;
	}
	.error {
		color: #b91c1c;
	}
</style>
