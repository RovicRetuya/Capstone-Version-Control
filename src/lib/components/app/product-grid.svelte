<script lang="ts">
	import type { Product } from '#lib/types.js';
	import ProductCard from './product-card.svelte';

	let { products }: { products: Product[] } = $props();
</script>

<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
	{#each products as product, index (product.link)}
		<div class="reveal" style="--i:{index}"><ProductCard {product} class="h-full" /></div>
	{/each}
</div>
