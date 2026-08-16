<script lang="ts">
	import type { Proposal } from './types';

	let {
		proposal,
		disabled,
		onsubmit,
		onapprove,
		onreject
	}: {
		proposal: Proposal | null;
		disabled: boolean;
		onsubmit: (command: string) => void;
		onapprove: () => void;
		onreject: () => void;
	} = $props();

	let command = $state('');

	function submit(e: SubmitEvent) {
		e.preventDefault();
		if (command.trim()) onsubmit(command.trim());
		command = '';
	}

	const lineClass = (line: string) =>
		line.startsWith('+') && !line.startsWith('+++')
			? 'add'
			: line.startsWith('-') && !line.startsWith('---')
				? 'del'
				: line.startsWith('@@')
					? 'hunk'
					: '';
</script>

<section>
	<h3>Edit by instruction</h3>
	{#if !proposal}
		<form onsubmit={submit}>
			<input
				type="text"
				bind:value={command}
				placeholder="e.g. make the introduction shorter"
				aria-label="edit instruction"
				{disabled}
			/>
			<button disabled={disabled || !command.trim()}>Run edit</button>
		</form>
		<p class="note">
			The agent edits the LaTeX on a proposal branch. The diff only reaches you if it survives the
			gates: allowed paths, a clean tectonic build, and the citation validator.
		</p>
	{:else}
		<h4>Proposal: <em>{proposal.command}</em></h4>
		<pre class="diff">{#each proposal.diff.split('\n') as line, i (i)}<span class={lineClass(line)}>{line}
</span>{/each}</pre>
		<div class="actions">
			<button onclick={onapprove} disabled={disabled}>Approve — merge to main</button>
			<button class="secondary" onclick={onreject} disabled={disabled}>Reject — delete branch</button>
		</div>
	{/if}
</section>

<style>
	form {
		display: flex;
		gap: 0.5rem;
	}
	input[type='text'] {
		flex: 1;
		padding: 0.4rem 0.6rem;
		border: 1px solid #d1d5db;
		border-radius: 0.375rem;
	}
	.diff {
		background: #f9fafb;
		border: 1px solid #e5e7eb;
		border-radius: 0.375rem;
		padding: 0.75rem;
		overflow-x: auto;
		font-size: 0.82rem;
		line-height: 1.4;
	}
	.add {
		color: #15803d;
	}
	.del {
		color: #b91c1c;
	}
	.hunk {
		color: #6d28d9;
	}
	.actions {
		display: flex;
		gap: 0.75rem;
	}
	.secondary {
		background: none;
	}
	.note {
		font-size: 0.9rem;
		color: #4b5563;
	}
</style>
