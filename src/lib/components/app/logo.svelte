<script lang="ts">
	import { cn } from '#lib/utils.js';
	import logo from '#lib/assets/logo.png';

	let {
		href = '/',
		showName = true,
		class: className
	}: { href?: string; showName?: boolean; class?: string } = $props();
</script>

<!-- The mark: the D-shaped loupe with a mustard checkmark. -->
<a {href} class={cn('tap inline-flex items-center gap-2 font-semibold tracking-tight', className)} aria-label="DeFaketive home">
	<img src={logo} alt="" class="size-7 shrink-0" />
	{#if showName}<span>DeFaketive</span>{/if}
</a>
