<script lang="ts">
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link';
	import ProductImage from '#lib/components/app/product-image.svelte';
	import VerdictBadge from '#lib/components/app/verdict-badge.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#lib/components/ui/card/index.js';
	import { reportHrefFor } from '#lib/nav.js';
	import { counts, listingLabel, money, safeImage, safeLink, sentimentPercentages } from '#lib/product.js';
	import type { Product } from '#lib/types.js';

	let { recommendations, guest = false }: { recommendations: Product[]; guest?: boolean } = $props();

	const shown = $derived(recommendations.slice(0, 3));
</script>

<Card class="min-w-0 [overflow-wrap:anywhere] [&_a]:h-auto [&_a]:min-h-11 [&_a]:whitespace-normal [&_a]:py-2">
	<CardHeader>
		<p class="text-muted-foreground text-xs font-medium tracking-wide uppercase">Other options</p>
		<CardTitle><h2 class="text-xl font-semibold">Similar products with no warnings</h2></CardTitle>
		<CardDescription>Enough reviews, and not a single safety report.</CardDescription>
	</CardHeader>
	<CardContent>
		{#if shown.length}
			<div class="grid grid-cols-1 gap-4 md:grid-cols-3">
				{#each shown as item, index (item.link)}
					{@const image = safeImage(item)}
					{@const link = safeLink(item.link)}
					{@const found = counts(item)}
					{@const positive = sentimentPercentages(item).find((entry) => entry.label === 'Positive')?.percent ?? 0}
					<article class="reveal grid min-w-0 content-start gap-3 rounded-lg border p-4" style="--i:{index}">
						<header class="flex gap-3">
							<ProductImage src={image} name={item.name} compact class="size-20 shrink-0 rounded-lg" />
							<h3 class="min-w-0 text-sm leading-snug font-medium">{item.name || 'Unnamed product'}</h3>
						</header>
						<b>{money(item.price)}</b>
						<dl class="grid grid-cols-3 gap-2 text-xs">
							<div><dt class="text-muted-foreground">Positive</dt><dd class="font-medium">{positive.toFixed(0)}%</dd></div>
							<div><dt class="text-muted-foreground">Safety reports</dt><dd class="font-medium">{found.safety}</dd></div>
							<div><dt class="text-muted-foreground">Fake or faulty</dt><dd class="font-medium">{found.counterfeit + found.defect}</dd></div>
						</dl>
						<VerdictBadge product={item} class="w-fit" />
						<div class="flex flex-wrap gap-2">
							<Button size="sm" variant="outline" href={reportHrefFor(link, guest)} disabled={!link}>Open report</Button>
							{#if link}
								<Button size="sm" variant="ghost" href={link} target="_blank" rel="noreferrer">{listingLabel(item)} <ExternalLinkIcon /></Button>
							{/if}
						</div>
					</article>
				{/each}
			</div>
		{:else}
			<p class="text-muted-foreground text-sm">No similar product with enough reviews and no warnings is available in this report. Check another listing to compare its reviews and warnings.</p>
			<Button variant="outline" class="mt-3" href={guest ? '/scan' : '/app/analyze'}>Check another product</Button>
		{/if}
	</CardContent>
</Card>
