<script lang="ts">
	let {
		model = $bindable('sonnet'),
		effort = $bindable('medium'),
		disabled = false
	}: { model?: string; effort?: string; disabled?: boolean } = $props();

	const models = [
		{ value: 'haiku', label: 'haiku — fastest' },
		{ value: 'sonnet', label: 'sonnet — fast, faithful (default)' },
		{ value: 'opus', label: 'opus — strongest, slow' }
	];
	const efforts = ['low', 'medium', 'high', 'xhigh'];
</script>

<span class="selects">
	<label>
		model
		<select name="model" bind:value={model} {disabled}>
			{#each models as m (m.value)}
				<option value={m.value}>{m.label}</option>
			{/each}
		</select>
	</label>
	<label>
		effort
		<select name="effort" bind:value={effort} {disabled}>
			{#each efforts as e (e)}
				<option value={e}>{e}</option>
			{/each}
		</select>
	</label>
</span>

<style>
	.selects {
		display: inline-flex;
		gap: 1rem;
		align-items: center;
	}
	label {
		font-size: 0.85rem;
		color: #4b5563;
	}
	select {
		margin-left: 0.3rem;
	}
</style>
