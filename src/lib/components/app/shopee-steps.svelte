<script lang="ts">
	import PuzzleIcon from '@lucide/svelte/icons/puzzle';
	import { Button } from '#lib/components/ui/button/index.js';
	import { LAZADA_REVIEWS_PER_STAR } from '#lib/product.js';

	// Shown when a Shopee PH link is pasted: Shopee is checked by the browser extension, in the shopper's own browser,
	// so the link alone can't be scanned here. These are the steps to do it. The full install guide is /extension.
	let { link = '', extensionHref = '/extension' }: { link?: string; extensionHref?: string } = $props();

	const steps = [
		['Add the extension', 'Chrome or Edge on a computer. It takes about 2 minutes and only needs to be done once.'],
		['Open the product on Shopee', 'Use the same link you pasted. Log in to Shopee if it asks.'],
		['Press Check with DeFaketive', 'The button is at the bottom left of the Shopee page. Keep that tab open while it reads the reviews.'],
		['Read your report', `It opens here once the reviews are read: up to ${LAZADA_REVIEWS_PER_STAR} from each star level, usually within a minute or two.`]
	];
</script>

<section class="bg-muted/50 grid gap-4 rounded-lg border p-4" aria-labelledby="shopee-steps-title">
	<div class="space-y-1">
		<h2 id="shopee-steps-title" class="flex items-center gap-2 text-sm font-semibold">
			<PuzzleIcon class="size-4" aria-hidden="true" /> How to check this Shopee PH product
		</h2>
		<p class="text-muted-foreground text-sm">Shopee reviews are read in your own browser, so they can't be checked from a pasted link.</p>
	</div>
	<ol class="grid gap-3">
		{#each steps as [title, text], index (title)}
			<li class="grid grid-cols-[1.5rem_1fr] gap-3">
				<span class="bg-primary text-primary-foreground grid size-6 place-items-center rounded-full text-xs font-medium" aria-hidden="true">{index + 1}</span>
				<div>
					<p class="text-sm font-medium">{title}</p>
					<p class="text-muted-foreground text-sm">{text}</p>
				</div>
			</li>
		{/each}
	</ol>
	<div class="flex flex-wrap gap-2">
		<Button size="sm" href={extensionHref}>Get the extension</Button>
		{#if link}
			<Button size="sm" variant="outline" href={link} target="_blank" rel="noopener noreferrer">Open this product on Shopee</Button>
		{/if}
	</div>
</section>
