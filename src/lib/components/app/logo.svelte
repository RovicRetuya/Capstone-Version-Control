<script lang="ts">
	import { cn } from '#lib/utils.js';

	let {
		href = '/',
		showName = true,
		class: className
	}: { href?: string; showName?: boolean; class?: string } = $props();
</script>

<!-- The mark: a loupe whose handle bends into a checkmark (branding/logo/final in the project root). -->
<a {href} class={cn('tap inline-flex items-center gap-2 font-semibold tracking-tight', className)} aria-label="DeFaketive home">
	<svg viewBox="0 0 256 256" class="text-primary size-5 shrink-0" fill="currentColor" aria-hidden="true">
		<path
			fill-rule="evenodd"
			d="M95,57 A58,58 0 0 1 95,173 A58,58 0 0 1 95,57 Z M95,79 A36,36 0 0 1 95,151 A36,36 0 0 1 95,79 Z"
		/>
		<path class="text-highlight" d="M118,162 L155,199 L222,132 L198,108 L155,151 L142,138 Z" />
	</svg>
	{#if showName}<span>DeFaketive</span>{/if}
</a>
