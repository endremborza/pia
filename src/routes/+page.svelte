<script lang="ts">
	import { goto } from '$app/navigation';
	import AgentSelects from '$lib/AgentSelects.svelte';
	import { deletePaper, listPapers, uploadPaper } from '$lib/api';
	import type { PaperListItem } from '$lib/types';

	let kind = $state<'latex' | 'pdf'>('pdf');
	let error = $state<string>();
	let uploading = $state(false);
	let ready = $state(false);
	let papers = $state<PaperListItem[]>([]);
	let deleting = $state<string>();

	$effect(() => {
		ready = true;
		listPapers().then((p) => (papers = p)).catch(() => {});
	});

	async function remove(p: PaperListItem) {
		if (!confirm(`Delete "${p.title}"? This cannot be undone.`)) return;
		deleting = p.id;
		error = undefined;
		try {
			await deletePaper(p.id);
			papers = papers.filter((x) => x.id !== p.id);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Delete failed.';
		} finally {
			deleting = undefined;
		}
	}

	async function upload(e: SubmitEvent) {
		e.preventDefault();
		error = undefined;
		uploading = true;
		try {
			const { id } = await uploadPaper(new FormData(e.currentTarget as HTMLFormElement));
			await goto(`/papers/${id}`);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Upload failed.';
		} finally {
			uploading = false;
		}
	}
</script>

<svelte:head>
	<!-- set explicitly: navigating back from a paper would otherwise keep its title -->
	<title>papercli — paper improvement agent</title>
</svelte:head>

<main>
	<h1>Paper Improvement Agent</h1>
	<p>Upload a paper, see how it parses, review it against real academic search, improve it — citations intact.</p>

	<p>
		Your paper is first converted into a <strong>papercli repo</strong>: its LaTeX source, its references
		and its history in a git repository. Reviewing and editing only happen there — a sandbox where the
		agent gets familiar tools, and every output that matters is validated by code.
	</p>

	<details>
		<summary>Why the conversion is not optional</summary>
		<p>
			A PDF is a rendering, so for a language model, working on one is closer to working on an image
			than to working on text — and models are dramatically worse there. A model will happily draw a
			hand with six fingers, but it will not finish the sentence <em
				>“the number of fingers a person usually has on one hand is”</em
			> with <em>“six”</em>. Same model, same fact; only the representation differs. Editing a paper as
			a PDF is the six-finger case.
		</p>
		<p>
			A PDF reconstruction is a guess, so you rule on it once: your paper as rendered from our idea of
			what it is, beside the original, with every diverging word and every citation found. After that,
			every change reaches you as a git diff, and the references are pinned and verified against real
			academic search.
		</p>
	</details>

	<form onsubmit={upload}>
		<fieldset>
			<legend>Input format</legend>
			<label><input type="radio" name="kind" value="pdf" bind:group={kind} /> PDF</label>
			<label><input type="radio" name="kind" value="latex" bind:group={kind} /> LaTeX (.tex)</label>
		</fieldset>
		{#if kind === 'pdf'}
			<p class="reconstruct-opts">
				<AgentSelects />
				<span class="note">the agent reconstructing your paper's LaTeX from the PDF</span>
			</p>
		{/if}
		<input type="file" name="file" accept={kind === 'latex' ? '.tex' : '.pdf'} required />
		<button disabled={!ready || uploading}>{uploading ? 'Uploading…' : 'Upload'}</button>
	</form>

	<p class="note">
		One file per upload, and nothing in it is ever executed here — the server only runs tectonic. A
		multi-file project, with its assets and figure-generating code, is adopted locally instead:
		<code>papercli init ./my-paper</code>.
	</p>

	{#if error}
		<p class="error" role="alert">{error}</p>
	{/if}

	{#if papers.length}
		<section>
			<h2>Papers</h2>
			<ul>
				{#each papers as p (p.id)}
					<li>
						<a href="/papers/{p.id}">{p.title}</a>
						{#if !p.accepted}<span class="pending">awaiting acceptance</span>{/if}
						<button
							type="button"
							class="delete"
							onclick={() => remove(p)}
							disabled={deleting === p.id}
						>
							{deleting === p.id ? 'Deleting…' : 'Delete'}
						</button>
					</li>
				{/each}
			</ul>
		</section>
	{/if}
</main>

<style>
	main {
		max-width: 46rem;
		margin: 2rem auto;
		padding: 0 1rem;
		font-family: system-ui, sans-serif;
		line-height: 1.5;
	}
	fieldset {
		border: none;
		padding: 0;
		margin: 0 0 0.75rem;
	}
	.reconstruct-opts {
		margin: 0 0 0.75rem;
	}
	.reconstruct-opts .note {
		margin-left: 0.75rem;
	}
	label {
		margin-right: 1rem;
	}
	details {
		margin-bottom: 1.25rem;
	}
	summary {
		cursor: pointer;
	}
	.note {
		font-size: 0.9rem;
		color: #4b5563;
	}
	.error {
		color: #b91c1c;
	}
	.pending {
		font-size: 0.85rem;
		color: #b45309;
		margin-left: 0.5rem;
	}
	.delete {
		font-size: 0.8rem;
		margin-left: 0.75rem;
		color: #b91c1c;
		background: none;
		border: 1px solid #fca5a5;
		border-radius: 0.3rem;
		padding: 0.05rem 0.4rem;
		cursor: pointer;
	}
</style>
