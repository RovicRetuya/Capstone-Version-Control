<script lang="ts">
	import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
	import CircleCheckIcon from '@lucide/svelte/icons/circle-check';
	import OctagonXIcon from '@lucide/svelte/icons/octagon-x';
	import ScanSearchIcon from '@lucide/svelte/icons/scan-search';
	import TriangleAlertIcon from '@lucide/svelte/icons/triangle-alert';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card } from '#lib/components/ui/card/index.js';
	import ScanProgress from './scan-progress.svelte';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { MARKETPLACES } from '#lib/product.js';
	import { catalog } from '#lib/stores/catalog.svelte.js';
	import { needsYouTitle, plainScanMessage, scan } from '#lib/stores/scan.svelte.js';
	import type { Marketplace } from '#lib/types.js';

	// The latest scan, on Home. It stays after a scan finishes so a shopper who wandered off can find the report.
	const summary = $derived(scan.summary);
	const stage = $derived(Math.min(3, Math.max(1, Number(summary?.stage) || 1)));
	const complete = $derived(summary?.state === 'complete');
	const stopped = $derived(summary?.state === 'error');
	const attention = $derived(summary?.state === 'attention');
	const running = $derived(summary?.state === 'running');
	// The scraper opened a Chrome window for a login or a check; the message says what to do in it.
	const needsYou = $derived(running && Boolean(summary?.needs_you));
	const progress = $derived(
		Number.isFinite(Number(summary?.progress))
			? Math.min(100, Math.max(0, Number(summary?.progress)))
			: ({ 1: 18, 2: 68, 3: 92 } as Record<number, number>)[stage]
	);
	const title = $derived(
		complete
			? 'Your report is ready'
			: stopped
				? "This scan couldn't finish"
				: attention
					? 'Scan progress needs checking'
					: needsYou
						? needsYouTitle(summary)
						: ['Collecting product reviews', 'Reading the reviews', 'Preparing your report'][stage - 1]
	);
	const product = $derived(summary?.productLink ? catalog.lookup(summary.productLink) : undefined);
	const action = $derived(
		complete
			? summary?.productLink
				? 'Open report'
				: 'View results'
			: stopped
				? 'View scan details'
				: attention
					? 'Check progress'
					: 'View progress'
	);
</script>

{#if summary}
	<Card class="flex-row items-center gap-4 p-4" aria-labelledby="home-scan-title">
		<div class="bg-muted text-foreground grid size-10 shrink-0 place-items-center rounded-full" aria-hidden="true">
			{#if complete}<CircleCheckIcon class="pop size-5" />
			{:else if stopped}<OctagonXIcon class="text-destructive size-5" />
			{:else if attention || needsYou}<TriangleAlertIcon class="size-5" />
			{:else if running}<Spinner class="size-5" />
			{:else}<ScanSearchIcon class="size-5" />{/if}
		</div>
		<div class="min-w-0 flex-1 space-y-1">
			<p class="text-muted-foreground text-xs">
				{MARKETPLACES[summary.platform as Marketplace] ?? 'Product scan'}
				{#if running}· {scan.elapsed} elapsed{/if}
			</p>
			<h2 id="home-scan-title" class="font-semibold" aria-live="polite">{title}</h2>
			<p class="text-muted-foreground truncate text-sm">{product?.name || summary.query || 'Your product'}</p>
			<p class="text-sm {needsYou ? 'text-foreground' : 'text-muted-foreground'}">
				{complete
					? "Your report is saved. Open it whenever you're ready."
					: plainScanMessage(summary.message, 'You can keep browsing while we work.')}
			</p>
			{#if running}
				<ScanProgress {stage} {progress} compact class="mt-2" />
			{/if}
		</div>
		<Button variant={complete ? 'default' : 'outline'} onclick={() => scan.open()}>
			{action} <ArrowRightIcon />
		</Button>
	</Card>
{/if}
