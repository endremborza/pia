<script lang="ts">
	import type { ParsedPaper } from './types';

	let { paper }: { paper: ParsedPaper } = $props();
</script>

<article>
	{#if paper.unresolved.length}
		<p class="warn" role="alert">
			{paper.unresolved.length} citation{paper.unresolved.length > 1 ? 's' : ''} without a reference
			entry: {paper.unresolved.join(', ')}
		</p>
	{/if}
	{#if paper.uncited.length}
		<p class="warn">
			{paper.uncited.length} reference{paper.uncited.length > 1 ? 's' : ''} never cited: {paper.uncited.join(
				', '
			)}
		</p>
	{/if}

	{#if paper.abstract}
		<section>
			<h3>Abstract</h3>
			<p>{paper.abstract}</p>
		</section>
	{/if}

	<section>
		<h3>Structure</h3>
		<ul class="sections">
			<!-- keyed by position: papers repeat headings (an appendix "Results", say) -->
			{#each paper.sections as s, i (i)}
				<li style:margin-left="{(s.level - 1) * 1.5}em">{s.title}</li>
			{/each}
		</ul>
	</section>

	<section>
		<h3>In-text citations</h3>
		<ul>
			{#each Object.entries(paper.citations) as [key, count] (key)}
				<li class:missing={paper.unresolved.includes(key)}>
					<code>{key}</code> ×{count}
					{#if paper.unresolved.includes(key)}— no reference entry{/if}
				</li>
			{/each}
		</ul>
	</section>

	{#if paper.references.length}
		<section>
			<h3>References ({paper.references.length})</h3>
			<ol>
				{#each paper.references as ref (ref.key)}
					<li><code>{ref.key}</code> — {ref.text}</li>
				{/each}
			</ol>
		</section>
	{/if}
</article>

<style>
	.warn {
		color: #b45309;
	}
	.missing {
		color: #b91c1c;
	}
	.sections {
		list-style: none;
		padding-left: 0;
	}
</style>
