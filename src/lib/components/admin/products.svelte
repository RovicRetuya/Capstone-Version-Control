<script lang="ts">
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link';
	import SearchIcon from '@lucide/svelte/icons/search';
	import EmptyState from '#lib/components/app/empty-state.svelte';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card } from '#lib/components/ui/card/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import * as Select from '#lib/components/ui/select/index.js';
	import { Skeleton } from '#lib/components/ui/skeleton/index.js';
	import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '#lib/components/ui/table/index.js';
	import { adminApi } from '#lib/stores/admin.svelte.js';
	import { safeLink } from '#lib/product.js';
	import type { AdminProduct, AdminProducts } from '#lib/admin-types.js';

	// Every product the site has saved: scanned by the site, sent by the extension, or in the starter set. A list to read
	// (admin_api.py: GET /api/admin/products), newest first. The site never shows other people's accounts here.
	let found = $state<AdminProducts | null>(null);
	let failed = $state('');
	let query = $state('');
	let platform = $state('');

	const RESULTS: Record<string, string> = {
		no_warning_signs: 'No warning signs',
		possible_safety_issue: 'Safety mentions',
		safety_warning: 'Safety reports',
		possible_counterfeit_or_defect: 'Fakes or defects',
		insufficient_evidence: 'Not enough reviews'
	};
	const result = (product: AdminProduct) => RESULTS[product.result] ?? (product.result || '—');
	const price = (product: AdminProduct) => (product.price === null || product.price === '' ? '—' : String(product.price));
	const rating = (product: AdminProduct) => (product.rating ? product.rating.toFixed(1) : '—');
	const reviews = (product: AdminProduct) =>
		product.reviews_read === null ? '—' : product.reviews_listed ? `${product.reviews_read} of ${product.reviews_listed}` : String(product.reviews_read);

	let requestId = 0;
	async function load() {
		const id = ++requestId;
		failed = '';
		const params = new URLSearchParams({ q: query.trim(), platform });
		try {
			const answer = await adminApi<AdminProducts>(`/api/admin/products?${params}`);
			if (id === requestId) found = answer;
		} catch (error) {
			if (id === requestId) failed = (error as Error).message;
		}
	}
	load();

	let timer: ReturnType<typeof setTimeout> | undefined;
	function onSearch() {
		clearTimeout(timer);
		timer = setTimeout(load, 250);
	}
	const kinds = $derived([['', 'All marketplaces'], ...Object.keys(found?.platforms ?? {}).map((name) => [name, name] as [string, string])] as [string, string][]);
	const kindName = $derived(kinds.find(([key]) => key === platform)?.[1] ?? 'All marketplaces');
	function clear() {
		query = '';
		platform = '';
		load();
	}
</script>

<div class="flex flex-col gap-4">
	<div class="flex flex-col gap-3 lg:flex-row lg:items-end">
		<div class="grid w-full gap-2 lg:max-w-sm">
			<Label for="product-search">Search products</Label>
			<div class="relative">
				<SearchIcon class="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
				<Input id="product-search" type="search" class="pl-9" placeholder="A name or part of a link" bind:value={query} oninput={onSearch} />
			</div>
		</div>
		<div class="grid gap-2">
			<Label for="product-platform">Marketplace</Label>
			<Select.Root type="single" value={platform} onValueChange={(value) => ((platform = value), load())}>
				<Select.Trigger id="product-platform" class="w-full sm:w-56">{kindName}</Select.Trigger>
				<Select.Content>
					{#each kinds as [key, text] (key)}<Select.Item value={key} label={text}>{text}{key && found ? ` (${found.platforms[key]})` : ''}</Select.Item>{/each}
				</Select.Content>
			</Select.Root>
		</div>
		{#if found}
			<p class="text-muted-foreground text-sm lg:ml-auto" aria-live="polite">
				{found.total} saved {found.total === 1 ? 'product' : 'products'}{#if query.trim() || platform} · {found.shown} {found.shown === 1 ? 'match' : 'match'}{/if}
			</p>
		{/if}
	</div>

	{#if failed && !found}
		<EmptyState art="error" title="The products couldn't be loaded" description={failed}>
			{#snippet actions()}<Button onclick={load}>Try again</Button>{/snippet}
		</EmptyState>
	{:else if !found}
		<div class="grid gap-2" role="status" aria-label="Loading products">
			{#each [0, 1, 2, 3] as row (row)}<Skeleton class="h-12 w-full" />{/each}
		</div>
	{:else if !found.products.length}
		{#if found.total === 0}
			<EmptyState art="reviews" title="No products saved yet" description="Products appear here after someone checks one." />
		{:else}
			<EmptyState art="search" title="No products match" description="Try part of a name, or another marketplace.">
				{#snippet actions()}<Button variant="outline" onclick={clear}>Clear the search</Button>{/snippet}
			</EmptyState>
		{/if}
	{:else}
		<Card class="hidden py-0 md:block">
			<Table>
				<TableHeader>
					<TableRow>
						<TableHead class="pl-4">Product</TableHead>
						<TableHead>Marketplace</TableHead>
						<TableHead>Price</TableHead>
						<TableHead class="text-right">Rating</TableHead>
						<TableHead class="text-right">Reviews read</TableHead>
						<TableHead class="pr-4">Result</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{#each found.products as product (product.link)}
						<TableRow data-product={product.link}>
							<TableCell class="max-w-72 pl-4 font-medium">
								{#if safeLink(product.link)}
									<a class="inline-flex max-w-full items-center gap-1 underline-offset-4 hover:underline" href={safeLink(product.link)} target="_blank" rel="noreferrer noopener">
										<span class="truncate" title={product.name}>{product.name || product.link}</span>
										<ExternalLinkIcon class="text-muted-foreground size-3.5 shrink-0" aria-hidden="true" /><span class="sr-only"> (opens the listing)</span>
									</a>
								{:else}<span class="truncate">{product.name}</span>{/if}
							</TableCell>
							<TableCell class="whitespace-nowrap">{product.platform || '—'}</TableCell>
							<TableCell class="whitespace-nowrap tabular-nums">{price(product)}</TableCell>
							<TableCell class="text-right tabular-nums">{rating(product)}</TableCell>
							<TableCell class="text-right whitespace-nowrap tabular-nums">{reviews(product)}</TableCell>
							<TableCell class="pr-4 whitespace-nowrap">{result(product)}</TableCell>
						</TableRow>
					{/each}
				</TableBody>
			</Table>
		</Card>

		<ul class="grid grid-cols-1 gap-3 md:hidden" aria-label="Saved products">
			{#each found.products as product (product.link)}
				<li class="min-w-0" data-product={product.link}>
					<Card class="gap-2 p-4">
						<p class="font-medium break-words">{product.name || product.link}</p>
						<p class="text-muted-foreground text-sm">
							{product.platform || '—'} · {price(product)} · {rating(product)} stars · {reviews(product)} reviews read
						</p>
						<div class="flex flex-wrap items-center gap-2 text-sm">
							<Badge variant="secondary">{result(product)}</Badge>
						</div>
						{#if safeLink(product.link)}
							<a class="text-primary inline-flex items-center gap-1 text-sm underline underline-offset-4" href={safeLink(product.link)} target="_blank" rel="noreferrer noopener">Open the listing <ExternalLinkIcon class="size-3.5" aria-hidden="true" /></a>
						{/if}
					</Card>
				</li>
			{/each}
		</ul>
		{#if found.shown < found.total && !query.trim() && !platform}
			<p class="text-muted-foreground text-sm">Showing the newest {found.shown} of {found.total}. Search to find the others.</p>
		{/if}
	{/if}
</div>
