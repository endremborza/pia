<script lang="ts">
	import type { Run } from './types';

	let { run }: { run: Run } = $props();
	const labels: Record<string, string> = {
		resolve: 'Resolving references against OpenAlex, Semantic Scholar, Crossref and arXiv',
		reconstruct: 'Reconstructing LaTeX from the PDF',
		refine: 'Refining the reconstruction candidate',
		review: 'Peer review agent at work',
		edit: 'Edit agent at work'
	};

	const clock = (seconds: number) =>
		`${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;

	const shown = $derived(run.progress.slice(-8));
</script>

{#if run.status === 'running'}
	<aside class="banner running" aria-busy="true">
		<strong>{labels[run.kind] ?? run.kind}…</strong>
		<span class="elapsed">{clock(run.elapsed)}</span>
		{#if shown.length}
			<ol class="stream">
				{#each shown as line, i (run.progress.length - shown.length + i)}
					<li class:latest={i === shown.length - 1}>{line}</li>
				{/each}
			</ol>
		{/if}
	</aside>
{:else if run.status === 'error'}
	<aside class="banner error" role="alert">
		<strong>The {run.kind} run failed after {clock(run.elapsed)}.</strong>
		<p>{run.error}</p>
	</aside>
{/if}

<style>
	.banner {
		border: 1px solid;
		border-radius: 0.375rem;
		padding: 0.75rem 1rem;
		margin: 1rem 0;
		font-size: 0.92rem;
	}
	.running {
		border-color: #93c5fd;
		background: #eff6ff;
	}
	.error {
		border-color: #fca5a5;
		background: #fef2f2;
		color: #b91c1c;
	}
	.elapsed {
		float: right;
		font-variant-numeric: tabular-nums;
		color: #1d4ed8;
	}
	.stream {
		list-style: none;
		margin: 0.5rem 0 0;
		padding: 0.5rem 0.6rem;
		background: #ffffffb3;
		border-radius: 0.25rem;
		font-family: ui-monospace, monospace;
		font-size: 0.78rem;
		color: #6b7280;
		overflow-x: hidden;
	}
	.stream li {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.stream li.latest {
		color: #111827;
	}
	p {
		margin: 0.25rem 0 0;
		white-space: pre-wrap;
	}
</style>
