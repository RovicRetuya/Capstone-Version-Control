<script lang="ts">
	import ProductCardSkeleton from '#lib/components/app/product-card-skeleton.svelte';
	import ProductGrid from '#lib/components/app/product-grid.svelte';
	import EmptyState from '#lib/components/app/empty-state.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { library } from '#lib/stores/library.svelte.js';

	const saved = $derived(library.saved);
</script>

<svelte:head><title>Wishlist · DeFaketive</title></svelte:head>

<header class="space-y-1">
	<h1 class="text-3xl font-semibold tracking-tight">Wishlist</h1>
	<p class="text-muted-foreground">Your saved products.</p>
</header>

<section class="space-y-3" aria-labelledby="saved-title">
	<div>
		<h2 id="saved-title" class="text-lg font-semibold tracking-tight">Your saved items</h2>
		{#if library.ready && !library.error}
			<p class="text-muted-foreground text-sm" aria-live="polite">{saved.length} product{saved.length === 1 ? '' : 's'} saved</p>
		{/if}
	</div>
	{#if !library.ready}
		<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4" role="status" aria-label="Loading your wishlist">
			{#each [1, 2, 3] as n (n)}<ProductCardSkeleton />{/each}
		</div>
	{:else if library.error}
		<!-- A failed load must not look like an empty wishlist. -->
		<EmptyState art="error" title="Your wishlist couldn't be loaded" description="Nothing was lost. It is still saved in your account.">
			{#snippet actions()}<Button onclick={() => library.retry()}>Try again</Button>{/snippet}
		</EmptyState>
	{:else if saved.length}
		<ProductGrid products={saved} />
	{:else}
		<EmptyState art="heart" title="Start building your shortlist" description="Tap the heart on any product to save it here.">
			{#snippet actions()}<Button href="/app/products">Browse products</Button>{/snippet}
		</EmptyState>
	{/if}
</section>
