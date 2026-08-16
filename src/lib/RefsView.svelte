<script lang="ts">
	import Foldable from './Foldable.svelte';
	import type { RefSummary } from './types';

	let { refs }: { refs: RefSummary[] } = $props();

	const order = ['Unknown', 'Needs attention', 'URL reference', 'Auto-correctable', 'Verified'];
	let sorted = $derived(
		[...refs].sort((a, b) => order.indexOf(a.status) - order.indexOf(b.status))
	);
	const statusClass: Record<string, string> = {
		Verified: 'ok',
		'Auto-correctable': 'fixable',
		'Needs attention': 'warn',
		'URL reference': 'url',
		Unknown: 'bad'
	};
</script>

<Foldable>
	{#snippet summary()}
		References
		<span class="chip">{refs.length}</span>
	{/snippet}

	<p class="note">
		Verified online, most problematic first — hallubib's confidence taxonomy, shown as-is. Every id
		links to the source's own record.
	</p>
	<ul class="refs">
		{#each sorted as ref (ref.key)}
			<li>
				<span class="status {statusClass[ref.status] ?? 'bad'}">{ref.status}</span>
				<code>{ref.key}</code>
				<span class="title">{ref.title || '(no title parsed)'}</span>
				{#if ref.author}<span class="meta">{ref.author}{ref.year ? `, ${ref.year}` : ''}</span>{/if}
				<span class="ids">
					{#each ref.ids as link (link.api)}
						<a href={link.url} target="_blank" rel="noreferrer">{link.api}</a>
					{/each}
					{#if ref.url && !ref.ids.length}
						<a href={ref.url} target="_blank" rel="noreferrer">link</a>
					{/if}
				</span>
				{#each ref.notes as note, i (i)}
					<span class="meta warn-text">{note}</span>
				{/each}
			</li>
		{/each}
	</ul>
</Foldable>

<style>
	.chip {
		font-size: 0.8rem;
		background: #f3f4f6;
		color: #374151;
		border-radius: 0.6rem;
		padding: 0.15rem 0.5rem;
	}
	.refs {
		list-style: none;
		padding: 0;
	}
	.refs li {
		padding: 0.4rem 0;
		border-bottom: 1px solid #e5e7eb;
	}
	.status {
		font-size: 0.75rem;
		padding: 0.1rem 0.45rem;
		border-radius: 0.6rem;
		margin-right: 0.4rem;
		white-space: nowrap;
	}
	.ok {
		background: #dcfce7;
		color: #15803d;
	}
	.fixable {
		background: #cffafe;
		color: #0e7490;
	}
	.warn {
		background: #fef3c7;
		color: #b45309;
	}
	.url {
		background: #e5e7eb;
		color: #374151;
	}
	.bad {
		background: #fee2e2;
		color: #b91c1c;
	}
	.title {
		margin-left: 0.35rem;
	}
	.meta {
		display: block;
		font-size: 0.85rem;
		color: #6b7280;
		margin-left: 0.25rem;
	}
	.warn-text {
		color: #b45309;
	}
	.ids a {
		margin-left: 0.5rem;
		font-size: 0.85rem;
	}
	.note {
		font-size: 0.9rem;
		color: #4b5563;
	}
</style>
