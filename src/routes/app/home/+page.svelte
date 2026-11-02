<script lang="ts">
	import CircleAlertIcon from '@lucide/svelte/icons/circle-alert';
	import CircleCheckIcon from '@lucide/svelte/icons/circle-check';
	import TriangleAlertIcon from '@lucide/svelte/icons/triangle-alert';
	import ChartSkeleton from '#lib/components/app/chart-skeleton.svelte';
	import CountUp from '#lib/components/app/count-up.svelte';
	import EmptyState from '#lib/components/app/empty-state.svelte';
	import OverviewChart from '#lib/components/app/overview-chart.svelte';
	import ProductCardSkeleton from '#lib/components/app/product-card-skeleton.svelte';
	import ProductRow from '#lib/components/app/product-row.svelte';
	import ProductRowItem from '#lib/components/app/product-row-item.svelte';
	import RowItemSkeleton from '#lib/components/app/row-item-skeleton.svelte';
	import ScanStartForm from '#lib/components/app/scan-start-form.svelte';
	import ScanStatus from '#lib/components/app/scan-status.svelte';
	import StatsSkeleton from '#lib/components/app/stats-skeleton.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card, CardContent, CardHeader, CardTitle } from '#lib/components/ui/card/index.js';
	import { Skeleton } from '#lib/components/ui/skeleton/index.js';
	import { byConcern, chipFor, firstName, GROUP_NAMES, reviewCount } from '#lib/product.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { catalog } from '#lib/stores/catalog.svelte.js';
	import { library } from '#lib/stores/library.svelte.js';

	// Home is a dashboard: start a check, then see what needs a look, before anything else.
	const products = $derived(library.history);
	const safety = $derived(products.filter((p) => chipFor(p).kind === 'safety').sort(byConcern));
	const caution = $derived(products.filter((p) => chipFor(p).kind === 'caution').sort(byConcern));
	// The most serious first: safety reports, then cautions.
	const attention = $derived([...safety, ...caution]);
	const SHOWN = 5;

	const stats = $derived([
		{ value: products.length, label: 'Products checked' },
		{ value: products.reduce((total, p) => total + reviewCount(p), 0), label: 'Reviews analyzed' },
		{ value: attention.length, label: 'With warnings' },
		{ value: library.wishlist.length, label: 'In your wishlist' }
	]);

	const groups = $derived(
		(['clear', 'caution', 'safety', 'unknown'] as const).map((kind) => {
			const count = products.filter((p) => chipFor(p).kind === kind).length;
			return { key: kind, label: GROUP_NAMES[kind], count, percent: products.length ? Math.round((count / products.length) * 100) : 0 };
		})
	);

	const where = $derived(auth.user ? 'in your account' : 'on this browser');
	const attentionNote = $derived(
		attention.length
			? `${attention.length} of the ${products.length} product${products.length === 1 ? '' : 's'} you checked ${attention.length === 1 ? 'has' : 'have'} a warning. Most serious first.`
			: products.length
				? 'None of the products you checked has a warning.'
				: 'Nothing checked yet.'
	);

	const emptyTitle = $derived(catalog.modelUnavailable ? 'Review analysis is unavailable' : 'Your first report starts here');
	const emptyCopy = $derived(catalog.modelUnavailable || 'Paste a product link above. Your completed report will appear here.');

	// The two explainers are for a first visit. Once something has been checked, the person's own results take their place.
	const firstVisit = $derived(library.ready && !library.error && products.length === 0);
	const steps = [
		['Paste a link', 'Copy any product link from Lazada PH and paste it into the bar above.'],
		['We read the reviews', 'A Filipino-aware language model reads each review and looks for reports of fakes, defects and safety problems.'],
		['Get your result', "No warnings, caution, or safety reports, with the reviewers' own words."]
	];
	const tips = [
		['Check seller ratings first', 'Prefer sellers with high ratings and many completed orders before buying electronics.'],
		['Verify product authenticity codes', 'Many brands print a serial or authenticity code you can check on their official website.'],
		['Read 1-star reviews carefully', "Counterfeit products often appear in low-rating reviews mentioning 'fake', 'not original', or unexpected materials."],
		['Check the return policy', 'Prefer sellers with a clear return policy for electronics, and keep the receipt and box.']
	];
</script>

<svelte:head><title>Home · DeFaketive</title></svelte:head>

<header class="mx-auto w-full max-w-3xl min-w-0 space-y-2 pt-4 text-center md:pt-8">
	<p class="text-sm">{auth.user ? 'Welcome back,' : 'Welcome,'}</p>
	<h1 class="text-4xl leading-none tracking-tight [overflow-wrap:anywhere] min-[380px]:text-5xl sm:text-7xl" style="font-family: 'Archivo Black', 'Arial Black', Impact, sans-serif">
		{auth.user ? `${firstName(auth.user.name)}.` : 'shopper.'}
	</h1>
	<p class="text-muted-foreground mx-auto max-w-md pt-2">Check what reviewers report before you buy from Lazada PH or Shopee PH.</p>
</header>

<Card class="mx-auto w-full max-w-3xl p-4 md:p-6" aria-label="Check a product">
	<ScanStartForm autofill />
</Card>

<ScanStatus />

{#if library.error}
	<!-- A failed load must not look like "you have checked nothing". -->
	<EmptyState art="error" title="Your history couldn't be loaded" description="Nothing was lost. It is still saved in your account.">
		{#snippet actions()}<Button onclick={() => library.retry()}>Try again</Button>{/snippet}
	</EmptyState>
{:else}
	<!-- The numbers. -->
	{#if !library.ready}
		<StatsSkeleton />
	{:else}
		<Card class="mx-auto w-full max-w-3xl gap-0 p-0">
			<dl class="grid grid-cols-2 lg:grid-cols-4" aria-label="Your activity in numbers">
				{#each stats as stat, index (stat.label)}
					<div class="reveal flex flex-col gap-1 p-5 {index % 2 ? 'border-l' : ''} {index > 1 ? 'max-lg:border-t' : ''} {index > 0 ? 'lg:border-l' : ''}" style="--i:{index}">
						<dd class="text-3xl font-extrabold tabular-nums"><CountUp value={stat.value} /></dd>
						<dt class="text-muted-foreground font-mono text-[10px] tracking-widest uppercase">{stat.label}</dt>
					</div>
				{/each}
			</dl>
		</Card>
	{/if}

	{#if library.ready && (safety.length || caution.length)}
		<section class="mx-auto flex w-full max-w-4xl flex-wrap items-end justify-between gap-3 pt-2" aria-label="What needs a look">
			<div class="space-y-1">
				{#if safety.length}
					<h2 class="text-destructive text-sm font-bold">{safety.length} product{safety.length === 1 ? ' has' : 's have'} safety reports</h2>
					<p class="text-muted-foreground text-sm">Reviewers described fire, smoke, shocks or overheating.</p>
				{:else}
					<h2 class="text-sm font-bold">{caution.length} product{caution.length === 1 ? ' needs' : 's need'} caution</h2>
					<p class="text-muted-foreground text-sm">Reviewers reported problems worth a look before you buy.</p>
				{/if}
			</div>
			<a href="/app/history?filter={safety.length ? 'safety' : 'caution'}" class="text-destructive hover:underline text-sm font-semibold {safety.length ? '' : 'text-foreground'}">View them →</a>
		</section>
	{/if}

	<!-- Then everything recent. -->
	{#if !library.ready}
		<section class="space-y-3" aria-label="Loading recently checked products">
			<Skeleton class="h-6 w-48" />
			<div class="flex gap-4 overflow-hidden">{#each [1, 2, 3, 4] as n (n)}<ProductCardSkeleton class="w-64 shrink-0" />{/each}</div>
		</section>
	{:else}
		<ProductRow id="recent" title="Recently checked" href="/app/history" products={products.slice(0, 10)}>
			{#snippet empty()}
				<EmptyState art="search" title={emptyTitle} description={emptyCopy}>
					{#snippet actions()}
						<Button href="/app/analyze">Check a product</Button>
					{/snippet}
				</EmptyState>
			{/snippet}
		</ProductRow>
	{/if}

	<!-- What to look at first, beside the overall picture. On a phone they stack, this one on top. -->
	<div class="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
		<Card class="gap-0 pb-0" aria-labelledby="attention-title">
			<CardHeader class="pb-4">
				<h2 id="attention-title" class="flex items-center gap-2 text-base leading-snug font-semibold">
					{#if safety.length}
						<TriangleAlertIcon class="tone-safety size-4 shrink-0 text-(--tone)" aria-hidden="true" />
					{:else if caution.length}
						<CircleAlertIcon class="tone-caution size-4 shrink-0 text-(--tone)" aria-hidden="true" />
					{/if}
					Needs a look
				</h2>
				{#if library.ready}<p class="text-muted-foreground text-sm" aria-live="polite">{attentionNote}</p>{/if}
			</CardHeader>
			{#if !library.ready}
				<div class="divide-y border-t" role="status" aria-label="Loading what needs a look">
					{#each [1, 2, 3] as n (n)}<RowItemSkeleton />{/each}
				</div>
			{:else if attention.length}
				<div class="divide-y border-t">
					{#each attention.slice(0, SHOWN) as product (product.link)}
						<ProductRowItem {product} />
					{/each}
				</div>
				<div class="mt-auto flex flex-wrap items-center gap-2 border-t p-4">
					<span class="text-muted-foreground text-sm">See all:</span>
					{#if safety.length}
						<Button size="sm" variant="outline" href="/app/history?filter=safety">{GROUP_NAMES.safety} · {safety.length}</Button>
					{/if}
					{#if caution.length}
						<Button size="sm" variant="outline" href="/app/history?filter=caution">{GROUP_NAMES.caution} · {caution.length}</Button>
					{/if}
				</div>
			{:else if products.length}
				<p class="flex items-start gap-2 border-t p-4 text-sm">
					<CircleCheckIcon class="tone-clear mt-0.5 size-4 shrink-0 text-(--tone)" aria-hidden="true" />
					<span>Nothing needs a look right now. <span class="text-muted-foreground">No warning is not proof that a product is safe.</span></span>
				</p>
			{:else}
				<p class="text-muted-foreground border-t p-4 text-sm">
					Check a product and anything that needs a closer look will be listed here.
				</p>
			{/if}
		</Card>

		<Card aria-label="Overview of your checked products">
			<CardHeader><CardTitle>Overview</CardTitle></CardHeader>
			<CardContent class="flex flex-1 flex-col gap-4">
				<!-- Both cards are the same height: the chart sits in the middle, the note stays at the bottom. -->
				<div class="my-auto">
					{#if !library.ready}<ChartSkeleton />{:else}<OverviewChart {groups} total={products.length} />{/if}
				</div>
				<p class="text-muted-foreground text-xs">
					{products.length ? `Based on ${products.length} product${products.length === 1 ? '' : 's'} ${where}.` : 'Check a product to see your overview.'}
				</p>
			</CardContent>
		</Card>
	</div>
{/if}

{#if firstVisit}
	<section class="space-y-3" aria-labelledby="how-title">
		<h2 id="how-title" class="text-lg font-semibold tracking-tight">How it works</h2>
		<ol class="grid grid-cols-1 gap-4 md:grid-cols-3">
			{#each steps as [title, text], index (title)}
				<li class="reveal" style="--i:{index}">
					<Card class="h-full gap-2 p-5">
						<span class="text-muted-foreground text-xs font-medium">STEP 0{index + 1}</span>
						<h3 class="font-semibold">{title}</h3>
						<p class="text-muted-foreground text-sm">{text}</p>
					</Card>
				</li>
			{/each}
		</ol>
	</section>

	<section class="space-y-3" aria-labelledby="tips-title">
		<h2 id="tips-title" class="text-lg font-semibold tracking-tight">Shopping safety tips</h2>
		<dl class="grid grid-cols-1 gap-4 sm:grid-cols-2">
			{#each tips as [term, detail], index (term)}
				<Card class="reveal gap-1 p-5" style="--i:{index}">
					<dt class="font-medium">{term}</dt>
					<dd class="text-muted-foreground text-sm">{detail}</dd>
				</Card>
			{/each}
		</dl>
	</section>
{/if}
