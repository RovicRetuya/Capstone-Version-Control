<script lang="ts">
	import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
	import Highlighted from '#lib/components/app/highlighted.svelte';
	import CountUp from '#lib/components/app/count-up.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#lib/components/ui/card/index.js';
	import { Progress } from '#lib/components/ui/progress/index.js';
	import { categoryPlace, chipFor, segments, view } from '#lib/product.js';
	import type { Badge, Product } from '#lib/types.js';

	// One block per label the check ran, worded by the server, with the strongest quote.
	let {
		product,
		uniqueCount,
		onread
	}: { product: Product; uniqueCount: number; onread: (category: string) => void } = $props();

	// Most serious first, in two groups: the kinds of problem that can change the verdict, then the ones that can't.
	const badges = $derived(
		[...(view(product).badges ?? [])].sort((a, b) => categoryPlace(a.category) - categoryPlace(b.category))
	);
	const deciding = $derived(badges.filter((badge) => !badge.informs_only));
	const informing = $derived(badges.filter((badge) => badge.informs_only));
	// The safety bar takes the product's own colour: red only when the reports are serious or repeated.
	// Every other bar is plain: a count of reviews is never shown in the brand colour.
	const safetyBar = $derived(chipFor(product).kind === 'safety' ? '[&>div]:bg-destructive' : '[&>div]:bg-warning');
	const plainBar = '[&>div]:bg-foreground';
	const width = (mentions: number) =>
		uniqueCount ? Math.min(100, Math.max(mentions ? 3 : 0, (mentions / uniqueCount) * 100)) : 0;
</script>

{#snippet block(badge: Badge, index: number)}
	{@const quote = badge.evidence?.[0]}
	<div class="reveal grid content-start gap-2" style="--i:{index}">
		<div class="flex items-baseline justify-between gap-3">
			<span class="font-medium">{badge.label}</span>
			<b class="text-sm tabular-nums"><CountUp value={badge.mentions} /> review{badge.mentions === 1 ? '' : 's'}</b>
		</div>
		<!-- What this label covers, in the server's own words. -->
		{#if badge.helper}<p class="text-muted-foreground -mt-1 text-xs">{badge.helper}</p>{/if}
		<Progress
			value={width(badge.mentions)}
			aria-label="{badge.mentions} of {uniqueCount} reviews"
			class={badge.category === 'safety' && badge.mentions ? safetyBar : plainBar}
		/>
		<p class="text-muted-foreground text-sm">{badge.summary}</p>
		{#if quote}
			<blockquote class="bg-muted/50 grid gap-1.5 rounded-lg border-s-0 p-3 text-sm">
				<p><Highlighted pieces={segments(quote.text, quote.highlights)} /></p>
				{#if quote.hazard || quote.rating}
					<small class="text-muted-foreground text-xs">
						{[quote.hazard ? `Reports ${quote.hazard}` : '', quote.rating ? `${Number(quote.rating).toFixed(0)}-star review` : ''].filter(Boolean).join(' · ')}
					</small>
				{/if}
			</blockquote>
			<Button variant="link" size="sm" class="w-fit px-0" onclick={() => onread(badge.category)}>
				Read all {badge.mentions} <ArrowRightIcon />
			</Button>
		{/if}
	</div>
{/snippet}

<Card id="report-findings" tabindex={-1}>
	<CardHeader>
		<p class="text-muted-foreground text-xs font-medium tracking-wide uppercase">What reviewers reported</p>
		<CardTitle class="text-xl">Each check, in their own words</CardTitle>
		<CardDescription>The sentences the check flagged, with the words it matched highlighted.</CardDescription>
	</CardHeader>
	<CardContent class="grid gap-6">
		{#if deciding.length}
			<section class="grid gap-4" aria-labelledby="checks-deciding">
				<h3 id="checks-deciding" class="text-sm font-semibold">Can change the result</h3>
				<!-- Side by side on a wide screen, so the card is not one long strip. -->
				<div class="grid grid-cols-1 content-start gap-x-10 gap-y-6 lg:grid-cols-2 xl:grid-cols-3">
					{#each deciding as badge, index (badge.category)}{@render block(badge, index)}{/each}
				</div>
			</section>
		{/if}
		{#if informing.length}
			<!-- Said once for the group, instead of a tag on each block. -->
			<section class={['grid gap-4', deciding.length && 'border-t pt-6']} aria-labelledby="checks-informing">
				<div class="grid gap-1">
					<h3 id="checks-informing" class="text-sm font-semibold">Doesn't change the result</h3>
					<p class="text-muted-foreground text-xs">Still worth knowing before you buy.</p>
				</div>
				<div class="grid grid-cols-1 content-start gap-x-10 gap-y-6 lg:grid-cols-2 xl:grid-cols-3">
					{#each informing as badge, index (badge.category)}{@render block(badge, deciding.length + index)}{/each}
				</div>
			</section>
		{/if}
		{#if !badges.length}
			<p class="text-muted-foreground text-sm">This product has not been checked with the current review model.</p>
		{/if}
	</CardContent>
</Card>
