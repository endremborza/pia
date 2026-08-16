<script lang="ts">
	import AgentSelects from './AgentSelects.svelte';
	import type { PaperDetail, ReconstructOpts } from './types';

	let {
		paper,
		busy,
		onaccept,
		onrerun,
		onrefine
	}: {
		paper: PaperDetail;
		busy: boolean;
		onaccept: () => void;
		onrerun: (opts: ReconstructOpts) => void;
		onrefine: (opts: ReconstructOpts & { instruction?: string }) => void;
	} = $props();

	let parity = $derived(paper.parity);
	let ratio = $derived(parity ? parity.parity.ratio : null);
	let model = $state('sonnet');
	let effort = $state('medium');
	let instruction = $state('');

	function refine() {
		onrefine({ model, effort, instruction: instruction.trim() || undefined });
		instruction = '';
	}
</script>

<section>
	<h2>Is this your paper?</h2>
	<p>
		This is your paper rendered from our idea of what it is. A reconstruction is a guess — a PDF does
		not contain its source — so nothing runs on it until you accept it.
	</p>

	{#if ratio !== null && parity}
		<p>
			Word-level parity with your original: <strong>{(ratio * 100).toFixed(1)}%</strong>
			({parity.pages_rebuilt} pages rebuilt of {parity.pages_original}).
		</p>
	{/if}

	<div class="side-by-side">
		<figure>
			<figcaption>Your original</figcaption>
			<object title="original PDF" data="/api/papers/{paper.id}/original.pdf" type="application/pdf">
				<p>Inline PDFs are not available here — <a href="/api/papers/{paper.id}/original.pdf">open the original</a>.</p>
			</object>
		</figure>
		<figure>
			<figcaption>Reconstructed</figcaption>
			<object title="reconstructed PDF" data="/api/papers/{paper.id}/candidate.pdf" type="application/pdf">
				<p>Inline PDFs are not available here — <a href="/api/papers/{paper.id}/candidate.pdf">open the reconstruction</a>.</p>
			</object>
		</figure>
	</div>

	{#if parity && parity.parity.divergences.length}
		<details>
			<summary>{parity.parity.divergences.length} diverging block{parity.parity.divergences.length > 1 ? 's' : ''}</summary>
			<ul>
				{#each parity.parity.divergences.slice(0, 40) as d, i (i)}
					<li>
						<em>{d.kind}</em>{#if d.page}&nbsp;(p{d.page}){/if}:
						<del>{d.original.slice(0, 120)}</del> → <ins>{d.rebuilt.slice(0, 120)}</ins>
					</li>
				{/each}
			</ul>
		</details>
	{/if}

	{#if paper.parse}
		<details>
			<summary>{Object.keys(paper.parse.citations).length} in-text citation keys extracted</summary>
			<ul>
				{#each Object.entries(paper.parse.citations) as [key, count] (key)}
					<li><code>{key}</code> ×{count}</li>
				{/each}
			</ul>
		</details>
	{/if}

	<div class="actions">
		<button onclick={onaccept} disabled={busy}>Accept — this is my paper</button>
		<button class="secondary" onclick={() => onrerun({ model, effort })} disabled={busy}>
			Re-run from scratch
		</button>
		<AgentSelects bind:model bind:effort disabled={busy} />
	</div>
	<div class="refine">
		<input
			aria-label="refine instruction"
			placeholder="e.g. the table on page 2 is missing its last column"
			bind:value={instruction}
			disabled={busy}
			onkeydown={(e) => e.key === 'Enter' && !busy && refine()}
		/>
		<button class="secondary" onclick={refine} disabled={busy}>Refine this candidate</button>
	</div>
	<p class="note">
		Accepting resolves every reference online and unlocks review, editing and export — nothing is
		verified before your verdict. Refining sends this candidate back to the agent with your
		instruction and the measured divergences; re-running starts fresh from your committed original —
		no re-upload.
	</p>
</section>

<style>
	.side-by-side {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
		margin: 1rem 0;
	}
	figure {
		margin: 0;
	}
	figcaption {
		font-size: 0.85rem;
		color: #4b5563;
		margin-bottom: 0.25rem;
	}
	object {
		width: 100%;
		height: 24rem;
		border: 1px solid #d1d5db;
	}
	.actions {
		display: flex;
		gap: 0.75rem;
		align-items: center;
		flex-wrap: wrap;
		margin: 1rem 0 0.5rem;
	}
	.refine {
		display: flex;
		gap: 0.75rem;
		margin: 0.5rem 0;
	}
	.refine input {
		flex: 1;
		min-width: 12rem;
	}
	.secondary {
		background: none;
	}
	del {
		color: #b91c1c;
	}
	ins {
		color: #15803d;
		text-decoration: none;
	}
	.note {
		font-size: 0.9rem;
		color: #4b5563;
	}
</style>
