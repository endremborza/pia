<script lang="ts">
	import type { Snippet } from 'svelte';

	let { summary, open = false, children }: { summary: Snippet; open?: boolean; children: Snippet } =
		$props();
</script>

<details {open}>
	<summary>{@render summary()}</summary>
	<div class="body">{@render children()}</div>
</details>

<style>
	details {
		border: 1px solid #e5e7eb;
		border-radius: 0.5rem;
		margin-bottom: 1rem;
	}
	summary {
		cursor: pointer;
		list-style: none;
		padding: 0.75rem 1rem;
		font-size: 1.1rem;
		font-weight: 600;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	summary::-webkit-details-marker {
		display: none;
	}
	summary::before {
		content: '▸';
		font-size: 0.8em;
		color: #6b7280;
	}
	details[open] > summary::before {
		content: '▾';
	}
	.body {
		padding: 0 1rem 1rem;
	}
</style>
