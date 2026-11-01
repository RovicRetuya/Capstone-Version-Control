<script lang="ts">
	import { page } from '$app/state';
	import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
	import CheckIcon from '@lucide/svelte/icons/check';
	import CircleAlertIcon from '@lucide/svelte/icons/circle-alert';
	import LinkIcon from '@lucide/svelte/icons/link';
	import { onMount } from 'svelte';
	import ScanProgress from '#lib/components/app/scan-progress.svelte';
	import ScanStatus from '#lib/components/app/scan-status.svelte';
	import { Alert, AlertDescription, AlertTitle } from '#lib/components/ui/alert/index.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#lib/components/ui/card/index.js';
	import { InputGroup, InputGroupAddon, InputGroupInput } from '#lib/components/ui/input-group/index.js';
	import { Kbd } from '#lib/components/ui/kbd/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import {
		LAZADA_REVIEWS_PER_STAR,
		linkIdentity,
		MARKETPLACES,
		queryContext,
		refusalFor,
		scannable,
		typicalScanTime,
		viaExtension
	} from '#lib/product.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { catalog } from '#lib/stores/catalog.svelte.js';
	import { library } from '#lib/stores/library.svelte.js';
	import { needsYouTitle, scan } from '#lib/stores/scan.svelte.js';
	import { ui } from '#lib/stores/ui.svelte.js';
	import type { Marketplace } from '#lib/types.js';

	// The guest screen: one job, check a product link. No menu, no history, nothing to learn first.
	let query = $state('');

	// A link pasted on the landing page arrives in the address.
	onMount(() => {
		const incoming = page.url.searchParams.get('q');
		if (incoming && !scan.busy) query = incoming;
		// "/" pressed on the guest report lands here with the bar ready to type in.
		if (ui.focusScan) {
			ui.focusScan = false;
			document.getElementById('guest-query')?.focus();
		}
	});

	const context = $derived(queryContext(query));
	const hasQuery = $derived(query.trim() !== '');
	const notALink = $derived(hasQuery && !context.isUrl);
	const unsupported = $derived(context.isUrl && !context.platform);
	// A product somebody already checked opens at once and does not use a free scan.
	const match = $derived(
		context.platform
			? (catalog.lookup(query) ?? library.mine.find((product) => linkIdentity(product.link) === linkIdentity(query)))
			: null
	);
	// A Shopee or Temu link: its saved report still opens, but it is never scanned here (Shopee has the extension).
	const refused = $derived(Boolean(context.platform) && !scannable(context.platform) && !match);
	const outOfScans = $derived(auth.ready && auth.left === 0);
	const blocked = $derived(scannable(context.platform) && !match && outOfScans);

	function submit(event: SubmitEvent) {
		event.preventDefault();
		if (!context.platform || blocked || refused) return;
		scan.search({ query, marketplace: context.platform, live: !match, productCount: 1, reviewCount: 100 });
	}

	const running = $derived(scan.summary?.state === 'running' && scan.busy);
	const stage = $derived(Math.min(3, Math.max(1, Number(scan.summary?.stage) || 1)));
	const progress = $derived(
		Number.isFinite(Number(scan.summary?.progress))
			? Math.min(100, Math.max(0, Number(scan.summary?.progress)))
			: ({ 1: 18, 2: 68, 3: 92 } as Record<number, number>)[stage]
	);

	const steps = [
		['Paste a link', 'From a Lazada PH product page.'],
		['We read the reviews', 'In English, Filipino and Taglish, looking for reports of fakes, defects and safety problems.'],
		['Read the result', 'A plain result with the reviewers\' own words behind it. No score.']
	];
	const perks = ['Unlimited scans', 'Your scan history, on any device', 'Save products to a wishlist', 'Search every product already checked'];
</script>

<svelte:head><title>Check a product · DeFaketive</title></svelte:head>

<header class="space-y-2 text-center">
	<Badge variant="secondary" class="mx-auto">
		{#if auth.ready}
			{auth.left > 0 ? `${auth.left} of ${auth.guest?.limit ?? 3} free scans left today` : 'No free scans left today'}
		{:else}
			Free guest scan
		{/if}
	</Badge>
	<h1 class="text-3xl font-semibold tracking-tight text-balance md:text-4xl">Check a product before you buy</h1>
	<p class="text-muted-foreground mx-auto max-w-xl">
		Paste a product link. No account needed. You get a plain result and the reviews behind it.
	</p>
</header>

<Card class="mx-auto w-full max-w-2xl">
	<CardHeader class="sr-only"><CardTitle>Check a product</CardTitle></CardHeader>
	<CardContent>
		<form onsubmit={submit} class="grid gap-4">
			<div class="grid gap-2">
				<Label for="guest-query">Product link</Label>
				<InputGroup class="h-12">
					<InputGroupAddon><LinkIcon /></InputGroupAddon>
					<InputGroupInput
						id="guest-query"
						name="query"
						data-scan-input
						placeholder="Paste a Lazada PH link..."
						autocomplete="off"
						bind:value={query}
						disabled={scan.busy}
						aria-invalid={notALink || unsupported || refused}
					/>
					<InputGroupAddon align="inline-end" class="max-md:hidden"><Kbd title="Press / to jump here">/</Kbd></InputGroupAddon>
				</InputGroup>
				{#if notALink}
					<p class="text-destructive flex items-center gap-1.5 text-sm" aria-live="polite">
						<CircleAlertIcon class="size-4" /> That is not a link. Paste the product page's address.
					</p>
				{:else if unsupported}
					<p class="text-destructive flex items-center gap-1.5 text-sm" aria-live="polite">
						<CircleAlertIcon class="size-4" /> This website is not supported. Paste a Lazada PH product link.
					</p>
				{:else if refused}
					<p class="text-destructive flex items-center gap-1.5 text-sm" aria-live="polite">
						<CircleAlertIcon class="size-4 shrink-0" /> {refusalFor(context.platform!)}
						{#if viaExtension(context.platform)}
							<a class="tap font-medium underline underline-offset-4" href="/extension">Get the extension</a>
						{/if}
					</p>
				{:else if context.platform}
					<p class="text-success flex items-center gap-1.5 text-sm" aria-live="polite">
						<CheckIcon class="size-4" /> {MARKETPLACES[context.platform]} product link detected.
					</p>
				{/if}
				{#if match}
					<p class="bg-muted rounded-lg px-3 py-2 text-sm" aria-live="polite">
						Already checked: <span class="font-medium">{match.name || 'this product'}</span>. Opening it does not use a free scan.
					</p>
				{:else if scannable(context.platform) && !blocked}
					<p class="text-muted-foreground text-xs">
						Uses 1 free scan. We read up to {LAZADA_REVIEWS_PER_STAR} reviews from each star level.
					</p>
				{/if}
			</div>

			{#if blocked}
				<Alert class="tone-caution border-(--tone)/50 bg-(--tone-soft) *:[svg]:text-(--tone)">
					<CircleAlertIcon />
					<AlertTitle>You've used today's free scans</AlertTitle>
					<AlertDescription>Create a free account for unlimited scans, or come back tomorrow.</AlertDescription>
					<div class="col-start-2 mt-2 flex flex-wrap gap-2">
						<Button size="sm" type="button" onclick={() => ui.openAuth('signup', '', `/app/analyze?q=${encodeURIComponent(query)}`)}>Create free account</Button>
						<Button size="sm" type="button" variant="ghost" onclick={() => ui.openAuth('signin', '', `/app/analyze?q=${encodeURIComponent(query)}`)}>Sign in</Button>
					</div>
				</Alert>
			{:else}
				<Button type="submit" size="lg" class="h-11" disabled={scan.busy || !context.platform || refused}>
					{#if scan.busy}<Spinner />{/if}
					{match ? 'Open report' : context.platform ? `Check this ${MARKETPLACES[context.platform]} product` : 'Check this product'}
					<ArrowRightIcon />
				</Button>
			{/if}

			{#if scan.feedback}
				<Alert
					variant={scan.feedback.kind === 'error' ? 'destructive' : 'default'}
					class={scan.feedback.kind === 'warning' ? 'tone-caution border-(--tone)/50 bg-(--tone-soft) *:[svg]:text-(--tone)' : ''}
				>
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
					<p class="text-muted-foreground text-xs">
						A scan usually takes {typicalScanTime(scan.summary?.platform)}. Keep this page open. The report opens by itself when it is ready.
					</p>
				</div>
			{/if}
		</form>
	</CardContent>
</Card>

{#if scan.summary && !running}
	<div class="mx-auto w-full max-w-2xl"><ScanStatus /></div>
{/if}

<section class="mx-auto grid w-full max-w-4xl gap-4 md:grid-cols-3" aria-label="How it works">
	{#each steps as [title, text], index (title)}
		<Card class="reveal gap-2 p-5" style="--i:{index}">
			<span class="text-muted-foreground text-xs font-medium">STEP 0{index + 1}</span>
			<h2 class="font-semibold">{title}</h2>
			<p class="text-muted-foreground text-sm">{text}</p>
		</Card>
	{/each}
</section>

<Card class="mx-auto w-full max-w-4xl">
	<CardHeader>
		<CardTitle>Want more than {auth.guest?.limit ?? 3} scans a day?</CardTitle>
		<CardDescription>A free account adds:</CardDescription>
	</CardHeader>
	<CardContent class="grid gap-4">
		<ul class="grid gap-2 text-sm sm:grid-cols-2">
			{#each perks as perk (perk)}
				<li class="flex items-center gap-2"><CheckIcon class="text-success size-4 shrink-0" /> {perk}</li>
			{/each}
		</ul>
		<div class="flex flex-wrap gap-2">
			<Button onclick={() => ui.openAuth('signup')}>Create free account</Button>
			<Button variant="outline" onclick={() => ui.openAuth('signin')}>Sign in</Button>
		</div>
	</CardContent>
</Card>
