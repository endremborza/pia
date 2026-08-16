<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import {
		acceptPaper,
		approveProposal,
		deletePaper,
		doEdit,
		exportPaper,
		getPaper,
		refinePaper,
		rejectProposal,
		rerunPaper,
		startReview
	} from '$lib/api';
	import AcceptView from '$lib/AcceptView.svelte';
	import EditPanel from '$lib/EditPanel.svelte';
	import ParseView from '$lib/ParseView.svelte';
	import RefsView from '$lib/RefsView.svelte';
	import ReviewPanel from '$lib/ReviewPanel.svelte';
	import RunBanner from '$lib/RunBanner.svelte';
	import type { PaperDetail } from '$lib/types';

	const id = $derived(page.params.id!);
	let paper = $state<PaperDetail>();
	// An action's failure stays until the next action; a poll's clears itself, so
	// a momentary blip cannot leave a stale alert on screen forever.
	let error = $state<string>();
	let pollError = $state<string>();
	let lastPayload = '';

	async function refresh() {
		try {
			const next = await getPaper(id);
			pollError = undefined;
			const payload = JSON.stringify(next);
			if (payload !== lastPayload) {
				lastPayload = payload;
				paper = next;
			}
		} catch (err) {
			pollError = err instanceof Error ? err.message : String(err);
		}
	}

	$effect(() => {
		void id;
		refresh();
		const timer = setInterval(refresh, 1500);
		return () => clearInterval(timer);
	});

	async function act(action: () => Promise<unknown>) {
		error = undefined;
		try {
			await action();
			await refresh();
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
		}
	}

	const running = $derived(paper?.run?.status === 'running');
	const busy = $derived(running || (paper?.state.busy ?? false));

	async function remove() {
		if (!paper || !confirm(`Delete "${paper.title}"? This cannot be undone.`)) return;
		error = undefined;
		try {
			await deletePaper(id);
			await goto('/');
		} catch (err) {
			error = err instanceof Error ? err.message : 'Delete failed.';
		}
	}
</script>

<svelte:head>
	<title>{paper ? `${paper.title} — papercli` : 'papercli'}</title>
</svelte:head>

<main>
	<nav>
		<a href="/">← papers</a>
		{#if paper}
			<button type="button" class="delete" onclick={remove} disabled={busy}>Delete</button>
		{/if}
	</nav>

	{#if !paper}
		<p aria-busy="true">Loading…</p>
	{:else}
		<h1>{paper.title}</h1>
		<p class="chips">
			{#if paper.state.accepted}<span class="chip ok">parse/{paper.state.parse_rounds}</span>{/if}
			{#each paper.state.reviews as n (n)}<span class="chip">review/{n}</span>{/each}
			{#if paper.state.exports}<span class="chip">export/{paper.state.exports}</span>{/if}
			{#if busy}<span class="chip busy">working…</span>{/if}
		</p>

		{#if error}
			<p class="error" role="alert">{error}</p>
		{/if}
		{#if pollError}
			<p class="stale" role="status">Lost contact with the server — retrying…</p>
		{/if}
		{#if paper.run}
			<RunBanner run={paper.run} />
		{/if}

		{#if !paper.state.accepted}
			{#if paper.state.from_pdf && paper.parse}
				<AcceptView
					{paper}
					{busy}
					onaccept={() => act(() => acceptPaper(id))}
					onrerun={(opts) => act(() => rerunPaper(id, opts))}
					onrefine={(opts) => act(() => refinePaper(id, opts))}
				/>
			{:else if paper.parse}
				<ParseView paper={paper.parse} />
			{/if}
		{:else}
			{#if paper.parse}
				<ParseView paper={paper.parse} />
			{/if}
			{#if paper.refs.length}
				<RefsView refs={paper.refs} />
			{/if}

			<ReviewPanel
				{id}
				reviews={paper.state.reviews}
				disabled={busy}
				onstart={() => act(() => startReview(id))}
			/>

			<EditPanel
				proposal={paper.proposal}
				disabled={busy}
				onsubmit={(command) => act(() => doEdit(id, command))}
				onapprove={() => act(() => approveProposal(id))}
				onreject={() => act(() => rejectProposal(id))}
			/>

			<section>
				<h3>Export</h3>
				<p class="note">
					tectonic builds the paper from its canonical LaTeX; the bibliography renders from the
					CSL-JSON store through citeproc, in the paper's detected style.
				</p>
				<button onclick={() => act(() => exportPaper(id))} disabled={busy}>Export PDF</button>
			</section>
		{/if}

		<section>
			<h3>History</h3>
			<p class="note">The repo is the only state — every step is a commit, milestones are tags.</p>
			<pre class="log">{paper.log.join('\n')}</pre>
		</section>
	{/if}
</main>

<style>
	main {
		max-width: 52rem;
		margin: 2rem auto;
		padding: 0 1rem;
		font-family: system-ui, sans-serif;
		line-height: 1.5;
	}
	nav {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 1rem;
	}
	.delete {
		font-size: 0.85rem;
		color: #b91c1c;
		background: none;
		border: 1px solid #fca5a5;
		border-radius: 0.3rem;
		padding: 0.15rem 0.5rem;
		cursor: pointer;
	}
	.delete:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.chips {
		margin: 0.25rem 0 1rem;
	}
	.chip {
		font-size: 0.8rem;
		background: #f3f4f6;
		color: #374151;
		border-radius: 0.6rem;
		padding: 0.15rem 0.5rem;
		margin-right: 0.4rem;
	}
	.chip.ok {
		background: #dcfce7;
		color: #15803d;
	}
	.chip.busy {
		background: #eff6ff;
		color: #1d4ed8;
	}
	.error {
		color: #b91c1c;
	}
	.stale {
		color: #b45309;
		font-size: 0.9rem;
	}
	.log {
		background: #f9fafb;
		border: 1px solid #e5e7eb;
		border-radius: 0.375rem;
		padding: 0.75rem;
		font-size: 0.82rem;
		overflow-x: auto;
	}
	.note {
		font-size: 0.9rem;
		color: #4b5563;
	}
</style>
