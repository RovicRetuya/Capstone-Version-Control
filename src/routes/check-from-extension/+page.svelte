<script lang="ts">
	import { goto } from '$app/navigation';
	import { toast } from 'svelte-sonner';
	import { reportHref } from '#lib/nav.js';
	import { page } from '$app/state';
	import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
	import CircleAlertIcon from '@lucide/svelte/icons/circle-alert';
	import PuzzleIcon from '@lucide/svelte/icons/puzzle';
	import { onMount } from 'svelte';
	import SiteFooter from '#lib/components/app/site-footer.svelte';
	import SiteHeader from '#lib/components/app/site-header.svelte';
	import { Alert, AlertDescription, AlertTitle } from '#lib/components/ui/alert/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#lib/components/ui/card/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { scan } from '#lib/stores/scan.svelte.js';
	import { ui } from '#lib/stores/ui.svelte.js';

	// The DeFaketive browser extension opens this page after it collected a Lazada or Shopee product's reviews in the
	// shopper's own browser. The reviews wait in the extension under the id in the address (?handoff=); this page
	// asks the extension's site script for them, and sends them to the server once the person is signed in.
	// The extension and this page only talk through window.postMessage, on this site's own origin.
	interface Collected {
		name?: string;
		link?: string;
		reviews?: unknown[];
	}

	type Phase = 'asking' | 'no-extension' | 'missing' | 'sign-in' | 'sending' | 'failed';
	const ANSWER_WAIT_MS = 3000;

	const id = page.url.searchParams.get('handoff') ?? '';
	let phase = $state<Phase>('asking');
	let collected = $state<Collected | null>(null);
	let problem = $state('');

	const count = $derived(Array.isArray(collected?.reviews) ? collected.reviews.length : 0);

	function askExtension(): Promise<{ product: Collected | null } | null> {
		return new Promise((resolve) => {
			const timer = setTimeout(() => finish(null), ANSWER_WAIT_MS);
			function finish(answer: { product: Collected | null } | null) {
				clearTimeout(timer);
				window.removeEventListener('message', listen);
				resolve(answer);
			}
			function listen(event: MessageEvent) {
				if (event.source !== window || event.origin !== location.origin) return;
				const data = event.data;
				if (!data || data.source !== 'defaketive-extension' || data.type !== 'handoff' || data.id !== id) return;
				finish({ product: data.product && typeof data.product === 'object' ? data.product : null });
			}
			window.addEventListener('message', listen);
			window.postMessage({ source: 'defaketive-site', type: 'take-handoff', id }, location.origin);
		});
	}

	onMount(async () => {
		if (!/^[0-9a-f-]{36}$/.test(id)) {
			phase = 'missing';
			return;
		}
		const answer = await askExtension();
		if (!answer) phase = 'no-extension';
		else if (!answer.product) phase = 'missing';
		else collected = answer.product;
	});

	// Once the reviews are here and we know who is visiting: send them, or ask a guest to sign in first.
	$effect(() => {
		if (!collected || !auth.ready || phase === 'sending' || phase === 'failed') return;
		if (!auth.user) {
			phase = 'sign-in';
			return;
		}
		send(collected);
	});

	async function send(product: Collected) {
		phase = 'sending';
		const outcome = await scan.submitCollected(product as Record<string, unknown>);
		if (outcome && 'failure' in outcome) {
			problem = outcome.failure;
			phase = 'failed';
			return;
		}
		window.postMessage({ source: 'defaketive-site', type: 'handoff-used', id }, location.origin);
		if (outcome) {
			// This product's report is recent, so the server kept it: open that one and say why.
			const { link, days_ago, keeps_for } = outcome.saved;
			const when = days_ago === 0 ? 'today' : days_ago === 1 ? 'yesterday' : `${days_ago} days ago`;
			toast.info(`This product was checked ${when}, so we opened that report.`, {
				description: `A new check can replace it after ${keeps_for} days. Checking again now would not change it.`
			});
			await goto(reportHref(link), { replaceState: true });
			return;
		}
		// The check page follows the job and opens the report by itself when it is ready.
		await goto('/app/analyze', { replaceState: true });
	}

	const here = () => `${page.url.pathname}${page.url.search}`;
	const signIn = () => ui.openAuth('signin', 'Sign in to see the report for the product you just checked.', here());
	const signUp = () => ui.openAuth('signup', 'Create a free account to see the report for the product you just checked.', here());
</script>

<svelte:head><title>Checking a product · DeFaketive</title></svelte:head>

<div class="flex min-h-svh flex-col">
	<SiteHeader />
	<main class="page-view mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 py-10 md:px-6">
		<Card>
			<CardHeader>
				<CardTitle class="text-xl">
					{#if phase === 'sign-in'}
						Sign in to see your report
					{:else if phase === 'failed'}
						This check couldn't start
					{:else if phase === 'no-extension' || phase === 'missing'}
						Nothing to check here
					{:else}
						Starting your check…
					{/if}
				</CardTitle>
				{#if collected?.name}
					<CardDescription>{collected.name}</CardDescription>
				{/if}
			</CardHeader>
			<CardContent class="grid gap-4">
				{#if phase === 'asking' || phase === 'sending'}
					<p class="flex items-center gap-3 text-sm" role="status">
						<Spinner class="size-5" />
						{phase === 'sending' ? `Sending ${count} reviews to DeFaketive…` : 'Getting the reviews from the extension…'}
					</p>
				{:else if phase === 'sign-in'}
					<p class="text-sm">
						The DeFaketive extension collected {count} reviews of this product. Checking a product with the extension needs a
						free account. Your reviews wait here while you sign in.
					</p>
					<div class="flex flex-wrap gap-2">
						<Button onclick={signIn}>Sign in <ArrowRightIcon /></Button>
						<Button variant="outline" onclick={signUp}>Create a free account</Button>
					</div>
				{:else if phase === 'no-extension'}
					<Alert>
						<PuzzleIcon />
						<AlertTitle>The DeFaketive extension didn't answer</AlertTitle>
						<AlertDescription>
							Make sure the extension is installed and switched on in this browser, then go back to the product page and
							press Check with DeFaketive again.
							<a class="tap text-primary font-medium underline underline-offset-4" href="/extension">How to install the extension</a>
						</AlertDescription>
					</Alert>
				{:else if phase === 'missing'}
					<Alert>
						<CircleAlertIcon />
						<AlertTitle>These reviews are no longer here</AlertTitle>
						<AlertDescription>
							They were already sent, or they expired after an hour. Go back to the product page and press Check with
							DeFaketive again.
						</AlertDescription>
					</Alert>
				{:else if phase === 'failed'}
					<Alert variant="destructive">
						<CircleAlertIcon />
						<AlertTitle>Nothing was checked</AlertTitle>
						<AlertDescription>{problem}</AlertDescription>
					</Alert>
				{/if}
				{#if phase === 'no-extension' || phase === 'missing' || phase === 'failed'}
					<div class="flex flex-wrap gap-2">
						<Button href={auth.user ? '/app' : '/'} variant="outline">Go to DeFaketive</Button>
					</div>
				{/if}
			</CardContent>
		</Card>
	</main>
	<SiteFooter />
</div>
