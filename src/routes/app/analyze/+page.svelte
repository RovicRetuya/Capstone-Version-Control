<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import ClearLinkButton from '#lib/components/app/clear-link-button.svelte';
	import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
	import CheckIcon from '@lucide/svelte/icons/check';
	import CircleAlertIcon from '@lucide/svelte/icons/circle-alert';
	import LinkIcon from '@lucide/svelte/icons/link';
	import SearchIcon from '@lucide/svelte/icons/search';
	import { onMount } from 'svelte';
	import { Alert, AlertDescription, AlertTitle } from '#lib/components/ui/alert/index.js';
	import { Kbd } from '#lib/components/ui/kbd/index.js';
	import ExtensionCard from '#lib/components/app/extension-card.svelte';
	import ShopeeSteps from '#lib/components/app/shopee-steps.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#lib/components/ui/card/index.js';
	import { InputGroup, InputGroupAddon, InputGroupInput } from '#lib/components/ui/input-group/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import ScanProgress from '#lib/components/app/scan-progress.svelte';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import {
		LAZADA_REVIEWS_PER_STAR,
		linkIdentity,
		MARKETPLACES,
		queryContext,
		refusalFor,
		safeLink,
		scannable,
		typicalScanTime,
		viaExtension
	} from '#lib/product.js';
	import { catalog } from '#lib/stores/catalog.svelte.js';
	import { library } from '#lib/stores/library.svelte.js';
	import { needsYouTitle, scan } from '#lib/stores/scan.svelte.js';
	import { ui } from '#lib/stores/ui.svelte.js';
	import type { Marketplace } from '#lib/types.js';

	let query = $state('');
	// One product per check. Lazada reads up to 60 reviews from each star level; 100 is the server's general limit.
	const reviewCount = 100;

	// A link pasted on Home or the landing page arrives in the address.
	onMount(() => {
		const incoming = page.url.searchParams.get('q');
		if (incoming && !scan.busy) query = incoming;
		// "/" pressed on another page lands here with the bar ready to type in.
		if (ui.focusScan) {
			ui.focusScan = false;
			document.getElementById('search-query')?.focus();
		}
	});

	// This page takes a product link. Words instead of a link are a search for a product already checked: that
	// lives on Products, and the page points there.
	const context = $derived(queryContext(query));
	const hasQuery = $derived(query.trim() !== '');
	const isName = $derived(hasQuery && !context.isUrl);
	const productsSearch = $derived(`/app/products?q=${encodeURIComponent(query.trim())}`);
	const unsupported = $derived(context.isUrl && !context.platform);
	// A Shopee or Temu link: a report saved from it still opens, but it is never scanned here (Shopee has the extension).
	const otherMarket = $derived(Boolean(context.platform) && !scannable(context.platform));
	const chosen = $derived<Marketplace>(context.platform ?? 'lazada');
	const match = $derived(
		context.platform
			? (catalog.lookup(query) ?? library.mine.find((product) => linkIdentity(product.link) === linkIdentity(query)))
			: null
	);
	const disabled = $derived(scan.busy || !context.platform || (otherMarket && !match));

	// One main button. A product we already have a report for opens it; checking it again is the second button.
	const primary = $derived(
		match
			? { intent: 'saved', label: 'Open report' }
			: context.platform && !otherMarket
				? { intent: 'live', label: `Check this ${MARKETPLACES[context.platform]} product` }
				: { intent: 'live', label: 'Check this product' }
	);
	const again = $derived(Boolean(match) && !otherMarket);

	// Enter on a product name goes where the hint under the box points. (The button is off for a name, and a form
	// whose button is off does not submit on Enter.)
	function nameEnter(event: KeyboardEvent) {
		if (event.key !== 'Enter' || !isName || scan.busy) return;
		event.preventDefault();
		goto(productsSearch);
	}

	function submit(event: SubmitEvent) {
		event.preventDefault();
		if (disabled) return;
		const intent = (event.submitter as HTMLElement | null)?.dataset.intent ?? primary.intent;
		scan.search({ query, marketplace: chosen, live: intent === 'live', productCount: 1, reviewCount });
	}

	const running = $derived(scan.summary?.state === 'running' && scan.busy);
	const stage = $derived(Math.min(3, Math.max(1, Number(scan.summary?.stage) || 1)));
	const progress = $derived(
		Number.isFinite(Number(scan.summary?.progress))
			? Math.min(100, Math.max(0, Number(scan.summary?.progress)))
			: ({ 1: 18, 2: 68, 3: 92 } as Record<number, number>)[stage]
	);
	// One product from a link takes a known time. A search by name scans several products, so nothing is promised there.
	const oneProduct = $derived(queryContext(scan.summary?.query ?? '').isUrl);
</script>

<svelte:head><title>Check a product · DeFaketive</title></svelte:head>

<header class="space-y-1">
	<p class="text-muted-foreground text-xs font-medium tracking-wide uppercase">Before you buy</p>
	<h1 class="text-3xl font-semibold tracking-tight">Check a product</h1>
	<p class="text-muted-foreground">One product link. The review evidence you need to make a decision.</p>
</header>

<Card>
	<CardHeader>
		<CardTitle>Paste a product link</CardTitle>
		<CardDescription>Copy the address of a Lazada PH product page and paste it here.</CardDescription>
	</CardHeader>
	<CardContent>
		<form onsubmit={submit} class="grid gap-4">
			<div class="grid gap-2">
				<Label for="search-query">Product link</Label>
				<InputGroup class="h-11">
					<InputGroupAddon><LinkIcon /></InputGroupAddon>
					<InputGroupInput
						id="search-query"
						data-scan-input
						name="query"
						placeholder="Paste a Lazada PH product link..."
						autocomplete="off"
						bind:value={query}
						onkeydown={nameEnter}
						disabled={scan.busy}
						aria-invalid={unsupported}
						aria-describedby="query-hint"
					/>
					<ClearLinkButton bind:value={query} disabled={scan.busy} />
					<InputGroupAddon align="inline-end" class="max-md:hidden"><Kbd title="Press / to jump here">/</Kbd></InputGroupAddon>
				</InputGroup>
				<div id="query-hint" class="contents">
				{#if isName}
					<p class="flex items-start gap-2 text-sm" aria-live="polite">
						<SearchIcon class="text-muted-foreground mt-0.5 size-4 shrink-0" aria-hidden="true" />
						<span>
							That's a name, not a link. Looking for a product someone already checked?
							<a class="tap text-primary inline-flex items-center gap-1 font-medium underline underline-offset-4" href={productsSearch}>Search Products for “{query.trim()}” <ArrowRightIcon class="size-4" /></a>
						</span>
					</p>
				{/if}
				{#if context.isUrl}
					<p
						class="flex items-center gap-1.5 text-sm {unsupported || (otherMarket && !match)
							? 'text-destructive'
							: otherMarket
								? 'text-muted-foreground'
								: 'text-success'}"
						aria-live="polite"
					>
						{#if unsupported}
							<CircleAlertIcon class="size-4" /> This website is not supported. Paste a Lazada PH product link.
						{:else if otherMarket}
							<CircleAlertIcon class="size-4 shrink-0" />
							{match ? 'Its saved report can still be opened.' : refusalFor(context.platform!)}
							{#if !match && viaExtension(context.platform)}
								<a class="tap text-primary font-medium underline underline-offset-4" href="/app/extension">Get the extension</a>
							{/if}
						{:else}
							<CheckIcon class="size-4" /> {MARKETPLACES[context.platform!]} product link detected.
						{/if}
					</p>
				{/if}
				{#if !match && viaExtension(context.platform)}
					<ShopeeSteps link={safeLink(query.trim())} extensionHref="/app/extension" />
				{/if}
				{#if match}
					<p class="bg-muted rounded-lg px-3 py-2 text-sm" aria-live="polite">
						Saved report found: <span class="font-medium">{match.name || `${MARKETPLACES[context.platform!]} product`}</span>
					</p>
				{:else if context.platform && !otherMarket}
					<p class="text-muted-foreground text-xs">We read up to {LAZADA_REVIEWS_PER_STAR} reviews from each star level.</p>
				{/if}
				</div>
			</div>

			<div class="flex flex-wrap gap-2">
				<Button type="submit" size="lg" {disabled} data-intent={primary.intent}>
					{primary.label} <ArrowRightIcon />
				</Button>
				{#if again}
					<Button type="submit" size="lg" variant="outline" {disabled} data-intent="live">Check again for new reviews</Button>
				{/if}
			</div>

			{#if scan.feedback}
				<Alert variant={scan.feedback.kind === 'error' ? 'destructive' : 'default'} class={scan.feedback.kind === 'warning' ? 'tone-caution border-(--tone)/50 bg-(--tone-soft) *:[svg]:text-(--tone)' : ''}>
					<CircleAlertIcon />
					<AlertTitle>{scan.feedback.title}</AlertTitle>
					<AlertDescription>{scan.feedback.message}</AlertDescription>
				</Alert>
			{/if}

			{#if running}
				<div class="bg-muted/50 grid gap-3 rounded-lg border p-4" role="status" aria-live="polite">
					<div class="flex items-center gap-3">
						<Spinner class="size-5" />
						<div class="flex flex-1 items-center justify-between gap-2">
							<b class="text-sm">
								{scan.summary?.platform
									? `${MARKETPLACES[scan.summary.platform as Marketplace] ?? scan.summary.platform} live scan`
									: 'Live scan running'}
							</b>
							<span class="text-muted-foreground text-xs tabular-nums">{scan.elapsed}</span>
						</div>
					</div>
					{#if scan.summary?.needs_you}
						<Alert class="tone-caution border-(--tone)/50 bg-(--tone-soft) *:[svg]:text-(--tone)">
							<CircleAlertIcon />
							<AlertTitle>{needsYouTitle(scan.summary)}</AlertTitle>
							<AlertDescription>{scan.summary.message}</AlertDescription>
						</Alert>
					{:else}
						<p class="text-muted-foreground text-sm">{scan.summary?.message || 'Preparing…'}</p>
					{/if}
					<ScanProgress {stage} {progress} />
					{#if oneProduct}<p class="text-muted-foreground text-xs">A scan of one product usually takes {typicalScanTime(scan.summary?.platform)}.</p>{/if}
				</div>
			{/if}

			<p class="text-muted-foreground text-xs">
				{scan.busy
					? 'You can browse your workspace while this scan runs. The top of the page shows how it is going.'
					: `Results are based on a sample of public reviews. A check usually takes ${typicalScanTime('lazada')}.`}
			</p>
		</form>
	</CardContent>
</Card>

<ExtensionCard guideHref="/app/extension" />
