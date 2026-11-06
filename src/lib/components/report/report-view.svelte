<script lang="ts">
	import { afterNavigate, goto } from '$app/navigation';
	import ArrowLeftIcon from '@lucide/svelte/icons/arrow-left';
	import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link';
	import HeartIcon from '@lucide/svelte/icons/heart';
	import { tick } from 'svelte';
	import { api, ApiError } from '#lib/api.js';
	import { reportHref } from '#lib/nav.js';
	import ProductImage from '#lib/components/app/product-image.svelte';
	import { Dialog, DialogContent, DialogHeader, DialogTitle } from '#lib/components/ui/dialog/index.js';
	import MaximizeIcon from '@lucide/svelte/icons/maximize-2';
	import Stars from '#lib/components/app/stars.svelte';
	import Alternatives from '#lib/components/report/alternatives.svelte';
	import ChecksCard from '#lib/components/report/checks-card.svelte';
	import Evidence from '#lib/components/report/evidence.svelte';
	import SentimentCard from '#lib/components/report/sentiment-card.svelte';
	import VerdictBlock from '#lib/components/report/verdict-block.svelte';
	import VerdictGuide from '#lib/components/report/verdict-guide.svelte';
	import WordsCard from '#lib/components/report/words-card.svelte';
	import { Alert, AlertDescription, AlertTitle } from '#lib/components/ui/alert/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card } from '#lib/components/ui/card/index.js';
	import EmptyState from '#lib/components/app/empty-state.svelte';
	import ReportSkeleton from '#lib/components/app/report-skeleton.svelte';
	import { Tabs, TabsContent, TabsList, TabsTrigger } from '#lib/components/ui/tabs/index.js';
	import {
		behindChecker,
		chipFor,
		counts,
		GROUP_NAMES,
		LAZADA_EXTENSION_REVIEWS_PER_STAR,
		LAZADA_REVIEWS_PER_STAR,
		liftedBySafety,
		listingLabel,
		money,
		platformName,
		queryContext,
		reportDate,
		reviewTags,
		safeImage,
		safeLink,
		scannable,
		sentimentLabel,
		sentimentPercentages,
		view,
		viaExtension,
		warningWords,
		type EvidenceFilter
	} from '#lib/product.js';
	import { page } from '$app/state';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { library } from '#lib/stores/library.svelte.js';
	import { scan } from '#lib/stores/scan.svelte.js';
	import { ui } from '#lib/stores/ui.svelte.js';
	import type { Product } from '#lib/types.js';
	import CircleAlertIcon from '@lucide/svelte/icons/circle-alert';
	import { onMount } from 'svelte';

	let product = $state<Product | null>(null);
	let recommendations = $state<Product[]>([]);
	let loading = $state(true);
	// Why there is no report to show: the link is no good, we have no report for it yet, or the load failed.
	// Each gets its own message and its own thing to do next.
	let failure = $state<'' | 'invalid' | 'missing' | 'failed'>('');
	// "Try again" adds one, which runs the load again.
	let attempt = $state(0);
	let requestId = 0;

	// `guest` is the stand-alone guest screen: same report, but no account features and its own way back.
	let { link, guest = false }: { link: string; guest?: boolean } = $props();

	type Detail = { product: Product; recommendations?: Product[] };
	const notFound = (error: unknown) => error instanceof ApiError && error.status === 404;
	// The whole database first: its "similar products" are picked from everything anyone has analyzed.
	// The original app's own route is the fallback (it only knows this browser's session).
	async function fetchDetail(target: string): Promise<Detail> {
		const query = new URLSearchParams({ link: target });
		try {
			return await api<Detail>(`/api/saved/detail?${query}`);
		} catch (first) {
			try {
				return await api<Detail>(`/api/products/detail?${query}`);
			} catch (second) {
				// "Not found" only when both said so. Anything else is a failed load, which is worth trying again.
				throw notFound(second) && !notFound(first) ? first : second;
			}
		}
	}

	// Load the report for the link in the address. A late answer for an older link is ignored.
	$effect(() => {
		const target = link;
		void attempt;
		const id = ++requestId;
		product = null;
		failure = '';
		if (!safeLink(target)) {
			loading = false;
			failure = 'invalid';
			return;
		}
		loading = true;
		fetchDetail(target)
			.then((data) => {
				if (id !== requestId) return;
				product = data.product;
				recommendations = data.recommendations ?? [];
				loading = false;
				library.remember(data.product);
				// The report of the scan just finished is open: the header stops pointing at it.
				scan.markSeen(data.product.link);
			})
			.catch((error: unknown) => {
				if (id !== requestId) return;
				failure = notFound(error) ? 'missing' : 'failed';
				loading = false;
			});
	});

	// A product we have no report for can be checked right away, with its link carried over. Only a Lazada PH
	// product can be checked: a report saved from Shopee or Temu still opens, but is never checked again.
	const checkable = $derived(scannable(queryContext(link).platform));
	const checkHref = $derived(`${guest ? '/scan' : '/app/analyze'}?q=${encodeURIComponent(link)}`);

	// --- What the report shows ------------------------------------------------
	const verdict = $derived(view(product));
	const summary = $derived(product?.sentiment_summary ?? {});
	const allReviews = $derived(
		Array.isArray(product?.comments) ? product.comments.filter((item) => item && typeof item === 'object') : []
	);
	const reviews = $derived(allReviews.filter((item) => !item.is_duplicate && item.included_in_analysis !== false));
	const coverage = $derived(summary.coverage ?? {});
	const uniqueCount = $derived(Number(verdict.reviews_analyzed || reviews.length) || reviews.length);
	const availableCount = $derived(
		Math.max(uniqueCount, Number(coverage.reviews_listed || coverage.reviews_available || uniqueCount) || uniqueCount)
	);
	// How many reviews were read, in plain words. The listing's own total is only quoted when the server sent one.
	const listedCount = $derived(Number(coverage.reviews_listed || coverage.reviews_available || 0) || 0);
	const sampleNote = $derived(
		coverage.sampling === 'stratified_by_star'
			? `We read ${uniqueCount.toLocaleString()} reviews, ${Number(coverage.star_quota || 0) > LAZADA_EXTENSION_REVIEWS_PER_STAR && !String(product?.platform ?? '').toLowerCase().includes('lazada') ? 'every written review the listing shows' : `up to ${Number(coverage.star_quota || LAZADA_REVIEWS_PER_STAR)} from each star level`}.${coverage.weighted ? ` The percentages are adjusted to reflect the listing's ${availableCount.toLocaleString()} ratings.` : ''}`
			: listedCount > uniqueCount
				? `We read ${uniqueCount.toLocaleString()} of this listing's ${listedCount.toLocaleString()} reviews.`
				: listedCount
					? `We read all ${uniqueCount.toLocaleString()} of this listing's reviews.`
					: `We read ${uniqueCount.toLocaleString()} review${uniqueCount === 1 ? '' : 's'}.`
	);
	const flagged = $derived(reviews.filter((item) => reviewTags(item).length));
	const sentiment = $derived(product ? sentimentPercentages(product) : []);
	const share = (label: string) => sentiment.find((item) => item.label === label) ?? { value: 0, percent: 0 };
	const positive = $derived(share('Positive'));
	const negative = $derived(share('Negative'));
	const weighted = $derived(Boolean(summary.sentiment_shares));
	const labelNames = $derived(Object.fromEntries((verdict.labels ?? []).map((item) => [item.category, item.label])));
	const words = $derived(warningWords(reviews));
	const name = $derived(product?.name || 'Unnamed product');
	const image = $derived(product ? safeImage(product) : '');
	const listing = $derived(safeLink(product?.link));
	const rating = $derived(Math.max(0, Math.min(5, Number(product?.rating || 0))));
	const saved = $derived(library.isSaved(listing));
	const date = $derived(product ? reportDate(product) : null);

	// Beside the name and the stars: what a shopper recognises the listing by.
	const identity = $derived([platformName(product), product?.price ? money(product.price) : ''].filter(Boolean).join(' · '));
	// Under the verdict: the numbers behind the report. (No "Category": saved products carry none, so it only
	// ever said "Not specified".)
	const details = $derived([
		['Positive reviews', weighted ? `${positive.percent.toFixed(0)}% (adjusted)` : `${positive.value} / ${uniqueCount}`],
		['Negative reviews', weighted ? `${negative.percent.toFixed(0)}% (adjusted)` : `${negative.value} / ${uniqueCount}`],
		['Flagged reviews', `${flagged.length} / ${uniqueCount}`],
		['Report date', date ?? 'Unavailable']
	]);

	// --- The evidence list, narrowed by the cards above it ----------------------
	let filter = $state<EvidenceFilter>('all');
	let tag = $state('');
	let word = $state('');
	let query = $state('');
	let limit = $state(6);
	let evidenceEl = $state<HTMLElement | null>(null);
	let tab = $state('overview');

	// Each new report starts on the flagged reviews, or on all of them when nothing was flagged.
	$effect(() => {
		if (!product) return;
		tab = 'overview';
		filter = flagged.length ? 'reported' : 'all';
		tag = '';
		word = '';
		query = '';
		limit = 6;
	});

	async function showEvidence() {
		tab = 'evidence';
		await tick();
		evidenceEl?.scrollIntoView({ behavior: 'smooth', block: 'start' });
		evidenceEl?.focus({ preventScroll: true });
	}
	function readAll(category: string) {
		tag = category;
		filter = 'reported';
		word = '';
		limit = 6;
		showEvidence();
	}
	function pickWord(next: string) {
		word = word === next ? '' : next;
		filter = 'all';
		tag = '';
		limit = 6;
		if (word) showEvidence();
	}

	// --- The next step, right under the verdict ----------------------------------
	const group = $derived(chipFor(product).kind);
	const lifted = $derived(liftedBySafety(product));
	const safetyMentions = $derived(counts(product).safety);
	const negativeCount = $derived(reviews.filter((item) => sentimentLabel(item) === 'negative').length);

	/** Open the list of reviews on one kind of review, with nothing else narrowing it. */
	function showReviews(kind: EvidenceFilter) {
		filter = kind;
		tag = '';
		word = '';
		query = '';
		limit = 6;
		showEvidence();
	}
	async function showSimilar() {
		tab = 'similar';
		await tick();
		document.getElementById('report-tabs')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
	}
	/** The explanation of the four labels sits at the bottom of the first tab. */
	async function showGuide() {
		tab = 'overview';
		await tick();
		const guide = document.getElementById('report-guide');
		guide?.scrollIntoView({ behavior: 'smooth', block: 'start' });
		guide?.focus({ preventScroll: true });
	}

	// Saving needs somewhere to keep it. On the guest screen that means an account.
	function save() {
		if (!product) return;
		if (guest && !auth.user) {
			ui.openAuth('signup', 'Create a free account to save products and keep your history.', reportHref(link));
			return;
		}
		library.toggleWishlist(product);
	}

	let photoOpen = $state(false);

	// A guest who is out of free scans is told so on a report, and can dismiss it for this visit.
	const LIMIT_KEY = 'defaketive-limit-dismissed';
	let limitDismissed = $state(false);
	onMount(() => {
		try {
			limitDismissed = sessionStorage.getItem(LIMIT_KEY) === '1';
		} catch {
			/* show the notice */
		}
	});
	// The button above the report goes back to the page it was opened from (Products, History...).
	// Opened with no page before it in the app (a shared link, a new tab), it offers to check another product.
	const CAME_FROM: Record<string, string> = {
		'/app/home': 'Back to Home',
		'/app/products': 'Back to Products',
		'/app/history': 'Back to History',
		'/app/wishlist': 'Back to Wishlist',
		'/app/report': 'Back to the previous report',
		'/scan/report': 'Back to the previous report'
	};
	let backLabel = $state<string | null>(null);
	afterNavigate(({ from }) => {
		// `from` can be there with no address (a first load, or a redirect from an /app page for a guest).
		const path = from?.url?.pathname;
		// Only from another report or one of these pages; the Check page keeps "Check another product".
		backLabel = path && (path !== page.url.pathname || from?.url?.search !== page.url.search) ? (CAME_FROM[path] ?? null) : null;
	});
	function goBack() {
		if (backLabel) history.back();
		else goto(guest ? '/scan' : '/app/analyze');
	}

	function dismissLimit() {
		limitDismissed = true;
		try {
			sessionStorage.setItem(LIMIT_KEY, '1');
		} catch {
			/* it stays hidden for this page */
		}
	}
</script>

<svelte:head><title>{product ? `${name} · DeFaketive` : 'Product report · DeFaketive'}</title></svelte:head>

<div class="flex flex-wrap items-center justify-between gap-2">
	<Button variant="ghost" size="sm" class="-ml-2" onclick={goBack}>
		<ArrowLeftIcon /> {backLabel ?? 'Check another product'}
	</Button>
	<!-- Only while loading: once the report is here, the count of reviews read sits under the verdict. -->
	<p class="text-muted-foreground text-sm" aria-live="polite">{#if loading}Loading product report…{/if}</p>
</div>

<!-- What an account adds. It sits under the verdict: the answer comes first, the offer after. -->
{#snippet accountNote()}
{#if guest && !auth.user}
	<!-- The guest screen always says what an account adds. It never blocks the report. -->
	<Alert>
		<CircleAlertIcon />
		<AlertTitle>You're viewing this as a guest</AlertTitle>
		<AlertDescription>
			{auth.left > 0 ? `${auth.left} free scan${auth.left === 1 ? '' : 's'} left today.` : 'No free scans left today.'}
			A free account keeps your history, saves products and scans without a daily limit.
		</AlertDescription>
		<div class="col-start-2 mt-2 flex flex-wrap gap-2">
			<Button size="sm" onclick={() => ui.openAuth('signup', '', reportHref(link))}>Create free account</Button>
			<Button size="sm" variant="ghost" onclick={() => ui.openAuth('signin', '', reportHref(link))}>Sign in</Button>
		</div>
	</Alert>
{:else if !auth.user && auth.ready && auth.left === 0 && !limitDismissed}
	<Alert>
		<CircleAlertIcon />
		<AlertTitle>You've used today's free scans</AlertTitle>
		<AlertDescription>Sign in or create a free account for unlimited scans. Free scans come back tomorrow.</AlertDescription>
		<div class="col-start-2 mt-2 flex flex-wrap gap-2">
			<Button size="sm" onclick={() => ui.openAuth('signup')}>Sign up to use more</Button>
			<Button size="sm" variant="ghost" onclick={dismissLimit}>Not now</Button>
		</div>
	</Alert>
{/if}
{/snippet}

{#if loading}
	<ReportSkeleton />
{:else if failure === 'failed'}
	<!-- The load failed: say so and offer to try again. This must not read as "there is no such report". -->
	<EmptyState art="error" title="This report couldn't be loaded" description="The server did not answer. Your link is fine.">
		{#snippet actions()}<Button onclick={() => (attempt += 1)}>Try again</Button>{/snippet}
	</EmptyState>
{:else if failure === 'missing' && checkable}
	<EmptyState art="search" title="We don't have a report for this product yet" description="Check it now and its report will open here.">
		{#snippet actions()}
			<Button href={checkHref}>Check this product</Button>
			{#if !guest}<Button variant="outline" href="/app/history">Go to history</Button>{/if}
		{/snippet}
	</EmptyState>
{:else if failure || !product}
	<EmptyState
		art="error"
		title="This link can't be opened"
		description={failure === 'missing'
			? 'We have no report for it, and it is not a Lazada PH product link.'
			: 'This product has no valid listing link.'}
	>
		{#snippet actions()}
			{#if guest}
				<Button href="/scan">Check another product</Button>
			{:else}
				<Button variant="outline" href="/app/history">Go to history</Button>
				<Button href="/app/analyze">Check a product</Button>
			{/if}
		{/snippet}
	</EmptyState>
{:else}
	<Card class="gap-0 overflow-hidden py-0">
		<div class="grid gap-4 p-5 md:p-6">
			<!-- Which product this is, kept short: the verdict comes straight after, on the first screen of a phone too. -->
			<div class="grid grid-cols-[4.5rem_1fr] items-start gap-x-4 gap-y-3 sm:grid-cols-[7rem_1fr] sm:gap-x-5">
				{#if image}
					<button
						type="button"
						class="group focus-visible:ring-ring/50 relative block aspect-square w-full overflow-hidden rounded-xl outline-none focus-visible:ring-3 sm:row-span-2"
						aria-label="View a larger photo of {name}"
						onclick={() => (photoOpen = true)}
					>
						<ProductImage src={image} {name} class="size-full" />
						<span class="bg-background/90 absolute right-1 bottom-1 grid size-6 place-items-center rounded-md opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" aria-hidden="true"><MaximizeIcon class="size-3.5" /></span>
					</button>
				{:else}
					<ProductImage src="" {name} class="aspect-square w-full rounded-xl sm:row-span-2" />
				{/if}
				<div class="grid min-w-0 content-start gap-2">
					<p class="text-muted-foreground hidden text-xs font-medium tracking-wide uppercase sm:block">Product report</p>
					<h1 class="text-lg leading-snug font-semibold tracking-tight sm:text-xl">{name}</h1>
					<div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
						<Stars value={rating} />
						<span class="text-muted-foreground">{identity}</span>
					</div>
				</div>
				<!-- Under the photo on a phone, under the name on anything wider. -->
				<div class="col-span-2 flex flex-wrap gap-2 sm:col-span-1 sm:col-start-2">
					<Button variant="outline" size="sm" aria-pressed={saved} disabled={!listing} onclick={save}>
						<HeartIcon class={saved ? 'fill-current' : ''} /> {saved ? 'Saved' : 'Save'}
					</Button>
					{#if listing}
						<Button variant="outline" size="sm" href={listing} target="_blank" rel="noreferrer">
							{listingLabel(product)} <ExternalLinkIcon />
						</Button>
					{/if}
				</div>
			</div>
			<VerdictBlock {product} />
			{#if lifted}
				<!-- The verdict alone would not be orange: say why this product is. -->
				<p class="bg-muted rounded-lg px-3 py-2 text-sm">
					This product is shown as <b>{GROUP_NAMES.caution}</b> because {safetyMentions} review{safetyMentions === 1 ? ' mentions' : 's mention'} a
					safety concern. One mention is enough for a closer look, whatever the overall result says.
				</p>
			{/if}
			{#if behindChecker(product)}
				<!-- A saved report does not change when the checker does. Say so instead of showing it as today's. -->
				<p class="bg-muted text-muted-foreground rounded-lg px-3 py-2 text-sm" data-behind-checker>
					This report was made with an earlier version of the checker.
					{#if checkable}
						<a class="tap text-primary font-medium underline underline-offset-4" href={checkHref}>Check it again</a>
						to bring it up to date.
					{:else}
						{#if viaExtension(queryContext(link).platform)}
							It can't be checked again from here: open the product on Shopee and press Check with DeFaketive.
						{:else}
							It can't be checked again: DeFaketive now checks Lazada PH products only.
						{/if}
					{/if}
				</p>
			{/if}
			<!-- One thing to do next, chosen by the verdict. -->
			<div class="flex flex-wrap items-center gap-2" role="group" aria-label="What to do next">
				{#if group === 'safety' || group === 'caution'}
					<!-- Someone who has been warned mostly wants a safer choice: with some to show, those come first. -->
					{#if recommendations.length}
						<Button onclick={showSimilar}>
							See {recommendations.length} similar product{recommendations.length === 1 ? '' : 's'} with no warnings
							<ArrowRightIcon />
						</Button>
					{/if}
					<Button variant={recommendations.length ? 'outline' : 'default'} onclick={() => showReviews(flagged.length ? 'reported' : 'all')}>
						{flagged.length === 1 ? 'Read the flagged review' : flagged.length ? `Read the ${flagged.length} flagged reviews` : 'Read the reviews'}
						<ArrowRightIcon />
					</Button>
				{:else if group === 'clear'}
					<!-- No warning is not the same as no complaint: point at what there is to read. -->
					{#if flagged.length}
						<Button variant="outline" onclick={() => showReviews('reported')}>
							{flagged.length === 1 ? 'Read the flagged review' : `Read the ${flagged.length} flagged reviews`} <ArrowRightIcon />
						</Button>
					{:else if negativeCount}
						<Button variant="outline" onclick={() => showReviews('negative')}>
							{negativeCount === 1 ? 'Read the negative review' : `Read the ${negativeCount} negative reviews`} <ArrowRightIcon />
						</Button>
					{:else if reviews.length}
						<Button variant="outline" onclick={() => showReviews('all')}>Read all reviews <ArrowRightIcon /></Button>
					{/if}
				{:else if flagged.length}
					<!-- No result yet, but the few reviews there are still say something: lead to those. -->
					<Button variant="outline" onclick={() => showReviews('reported')}>
						{flagged.length === 1 ? 'Read the flagged review' : `Read the ${flagged.length} flagged reviews`} <ArrowRightIcon />
					</Button>
				{:else if reviews.length}
					<Button variant="outline" onclick={() => showReviews('all')}>Read the reviews we have <ArrowRightIcon /></Button>
				{/if}
				<Button variant="link" size="sm" class="text-muted-foreground" onclick={showGuide}>What do these labels mean?</Button>
			</div>
		</div>
		<!-- The numbers behind the report. Useful, but never ahead of the verdict. -->
		<div class="grid gap-3 border-t p-5 md:p-6">
			<dl class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-4">
				{#each details as [term, value] (term)}
					<div><dt class="text-muted-foreground text-xs">{term}</dt><dd class="font-medium">{value}</dd></div>
				{/each}
			</dl>
			<p class="text-muted-foreground text-xs">{sampleNote}</p>
		</div>
	</Card>

	{@render accountNote()}

	<Tabs bind:value={tab} id="report-tabs" class="scroll-mt-20 gap-6">
		<TabsList class="w-full sm:w-fit">
			<TabsTrigger value="overview">Summary</TabsTrigger>
			<!-- One span per label: the tab's own spacing would otherwise open a gap inside it. -->
			<TabsTrigger value="evidence"><span>Reviews<span class="hidden sm:inline">&nbsp;· {flagged.length} flagged</span></span></TabsTrigger>
			<TabsTrigger value="similar"><span>Similar<span class="hidden sm:inline">&nbsp;products{recommendations.length ? ` · ${recommendations.length}` : ''}</span></span></TabsTrigger>
		</TabsList>
		<TabsContent value="overview" class="animate-in fade-in-0 slide-in-from-bottom-1 grid gap-6 duration-200">
			<!-- The chart and what the four labels mean, side by side (stacked on a phone); the reviewers' own words follow. -->
			<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
				<SentimentCard {product} {uniqueCount} />
				<!-- The link under the result jumps here. -->
				<VerdictGuide {product} />
			</div>
			<ChecksCard {product} {uniqueCount} onread={readAll} />
		</TabsContent>

		<TabsContent value="evidence" class="animate-in fade-in-0 slide-in-from-bottom-1 grid gap-6 duration-200">
			<WordsCard {words} active={word} onpick={pickWord} />
			<Evidence
				{reviews}
				{labelNames}
				serious={chipFor(product).kind === 'safety'}
				bind:filter
				bind:tag
				bind:word
				bind:query
				bind:limit
				bind:el={evidenceEl}
			/>
		</TabsContent>

		<TabsContent value="similar" class="animate-in fade-in-0 slide-in-from-bottom-1 grid gap-6 duration-200">
			<Alternatives {recommendations} {guest} />
		</TabsContent>
	</Tabs>

	<Dialog bind:open={photoOpen}>
		<DialogContent class="sm:max-w-3xl">
			<DialogHeader><DialogTitle class="sr-only">Photo of {name}</DialogTitle></DialogHeader>
			<img src={image} alt="Photo of {name}" class="max-h-[75svh] w-full rounded-lg object-contain" />
		</DialogContent>
	</Dialog>

	<p class="text-muted-foreground text-xs">
		This report analyzes a sample of public reviews. It supports shopping decisions but does not prove that a listing or product
		is authentic or counterfeit.
	</p>
{/if}
