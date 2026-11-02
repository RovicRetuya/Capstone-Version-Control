<script lang="ts">
	import { replaceState } from '$app/navigation';
	import { page } from '$app/state';
	import { untrack } from 'svelte';
	import EmptyState from '#lib/components/app/empty-state.svelte';
	import ProductCardSkeleton from '#lib/components/app/product-card-skeleton.svelte';
	import ProductGrid from '#lib/components/app/product-grid.svelte';
	import SearchIcon from '@lucide/svelte/icons/search';
	import SlidersHorizontalIcon from '@lucide/svelte/icons/sliders-horizontal';
	import XIcon from '@lucide/svelte/icons/x';
	import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from '#lib/components/ui/input-group/index.js';
	import type { Product } from '#lib/types.js';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from '#lib/components/ui/sheet/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import * as Select from '#lib/components/ui/select/index.js';
	import { byConcern, GROUP_NAMES, matchesConcern, reviewCount, type ConcernFilter } from '#lib/product.js';
	import { catalog } from '#lib/stores/catalog.svelte.js';

	let concern = $state<ConcernFilter>('all');
	let sort = $state<'fewest' | 'most' | 'reviews'>('fewest');
	// Search by name, as you type. Check a product sends a typed name here (?q=), and the address keeps the
	// search so that Back from a report finds it again.
	let search = $state(page.url.searchParams.get('q') ?? '');
	const terms = $derived(search.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []);
	const named = (product: Product) => {
		const name = String(product.name ?? '').toLowerCase();
		return terms.every((term) => name.includes(term));
	};
	// Runs only when the search changes. It compares with the browser's own address: a shallow replaceState leaves
	// page.url as it was, so comparing with page.url (or reading page.state here) kept this running for ever and
	// froze the page.
	$effect(() => {
		const wanted = search.trim();
		untrack(() => {
			const url = new URL(location.href);
			if ((url.searchParams.get('q') ?? '') === wanted) return;
			if (wanted) url.searchParams.set('q', wanted);
			else url.searchParams.delete('q');
			replaceState(url, page.state);
		});
	});

	// The same four group names as everywhere else, plus both warning groups together.
	const concerns: [ConcernFilter, string][] = [
		['all', 'All products'],
		['attention', `${GROUP_NAMES.caution} or ${GROUP_NAMES.safety.toLowerCase()}`],
		['safety', GROUP_NAMES.safety],
		['caution', GROUP_NAMES.caution],
		['clear', GROUP_NAMES.clear],
		['unknown', GROUP_NAMES.unknown]
	];
	const sorts: [typeof sort, string][] = [
		['fewest', 'Fewest reported problems'],
		['most', 'Most reported problems'],
		['reviews', 'Most reviews analyzed']
	];

	// A search shows its own matches; otherwise this is the whole catalog.
	const searching = $derived(catalog.results.length > 0);
	const source = $derived(searching ? catalog.results : catalog.browse);
	const filtered = $derived(
		source
			.filter((p) => matchesConcern(p, concern) && named(p))
			.sort((a, b) =>
				sort === 'reviews' ? reviewCount(b) - reviewCount(a) : sort === 'most' ? byConcern(a, b) : byConcern(b, a)
			)
	);
	const filtering = $derived(concern !== 'all' || terms.length > 0);
	const activeFilters = $derived((concern !== 'all' ? 1 : 0) + (sort !== 'fewest' ? 1 : 0));
	let filtersOpen = $state(false);
	const label = (list: string[][] | [string, string][], value: string) => list.find(([v]) => v === value)?.[1] ?? '';

	function clearFilters() {
		concern = 'all';
		search = '';
	}
</script>

<svelte:head><title>Products · DeFaketive</title></svelte:head>

<header class="space-y-1">
	<h1 class="text-3xl font-semibold tracking-tight">Products</h1>
	<p class="text-muted-foreground">
		Every product anyone has checked with DeFaketive. Products with the fewest reported problems appear first.
	</p>
</header>

{#snippet filterControls(suffix: string)}
	<div class="grid gap-1.5">
		<Label for="filter-risk{suffix}">Show</Label>
		<Select.Root type="single" bind:value={concern}>
			<Select.Trigger id="filter-risk{suffix}" class="w-full sm:w-60">{label(concerns, concern)}</Select.Trigger>
			<Select.Content>
				{#each concerns as [value, text] (value)}<Select.Item {value} label={text}>{text}</Select.Item>{/each}
			</Select.Content>
		</Select.Root>
	</div>
	<div class="grid gap-1.5">
		<Label for="filter-sort{suffix}">Sort by</Label>
		<Select.Root type="single" bind:value={sort}>
			<Select.Trigger id="filter-sort{suffix}" class="w-full sm:w-56">{label(sorts, sort)}</Select.Trigger>
			<Select.Content>
				{#each sorts as [value, text] (value)}<Select.Item {value} label={text}>{text}</Select.Item>{/each}
			</Select.Content>
		</Select.Root>
	</div>
{/snippet}

<div class="grid max-w-xl gap-1.5">
	<Label for="product-search">Search by name</Label>
	<InputGroup class="h-11">
		<InputGroupAddon><SearchIcon /></InputGroupAddon>
		<InputGroupInput id="product-search" enterkeyhint="search" placeholder="For example: power bank, earbuds, charger" autocomplete="off" bind:value={search} />
		{#if search}
			<InputGroupAddon align="inline-end">
				<InputGroupButton size="icon-xs" aria-label="Clear the search" onclick={() => (search = '')}><XIcon /></InputGroupButton>
			</InputGroupAddon>
		{/if}
	</InputGroup>
</div>

<!-- Wide screens: the filters sit in a row. Phones: one Filters button opens them from the bottom. -->
<div class="hidden flex-wrap items-end gap-4 sm:flex" aria-label="Filter products" role="group">
	{@render filterControls('')}
	{#if searching}
		<Button variant="outline" onclick={() => (catalog.results = [])}>Show all products</Button>
	{/if}
</div>
<div class="flex flex-wrap items-center gap-2 sm:hidden">
	<Button variant="outline" onclick={() => (filtersOpen = true)}>
		<SlidersHorizontalIcon /> Filters
		{#if activeFilters}<Badge variant="secondary">{activeFilters}</Badge>{/if}
	</Button>
	{#if searching}
		<Button variant="outline" onclick={() => (catalog.results = [])}>Show all</Button>
	{/if}
</div>
<Sheet bind:open={filtersOpen}>
	<SheetContent side="bottom" class="max-h-[85svh] rounded-t-xl">
		<SheetHeader>
			<SheetTitle>Filter products</SheetTitle>
			<SheetDescription>Choose what to show and how to sort it.</SheetDescription>
		</SheetHeader>
		<div class="grid gap-4 px-4">{@render filterControls('-sheet')}</div>
		<SheetFooter>
			<Button onclick={() => (filtersOpen = false)}>Show {filtered.length} product{filtered.length === 1 ? '' : 's'}</Button>
			{#if filtering || sort !== 'fewest'}
				<Button variant="ghost" onclick={() => { clearFilters(); sort = 'fewest'; }}>Reset</Button>
			{/if}
		</SheetFooter>
	</SheetContent>
</Sheet>

<p class="text-muted-foreground text-sm" aria-live="polite">
	{#if filtered.length}
		{filtered.length} product{filtered.length === 1 ? '' : 's'} shown{searching || terms.length ? ' for your search' : ''}.
	{/if}
</p>

{#if catalog.browseLoading && !source.length}
	<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4" role="status" aria-label="Loading products">
		{#each [1, 2, 3, 4] as n (n)}<ProductCardSkeleton />{/each}
	</div>
{:else if filtered.length}
	<ProductGrid products={filtered} />
{:else}
	{#if filtering && source.length}
		<EmptyState art="search" title="No products match these filters" description="Try another result.">
			{#snippet actions()}<Button variant="outline" onclick={clearFilters}>Clear filters</Button>{/snippet}
		</EmptyState>
	{:else if catalog.error && !catalog.modelUnavailable}
		<!-- A failed load must not look like an empty list. -->
		<EmptyState art="error" title="Products couldn't be loaded" description="The server did not answer. Nothing was lost.">
			{#snippet actions()}<Button onclick={() => catalog.reload()}>Try again</Button>{/snippet}
		</EmptyState>
	{:else}
		<EmptyState art="search" title="No products checked yet" description={catalog.modelUnavailable || 'Check a product and its report will be listed here.'}>
			{#snippet actions()}<Button href="/app/analyze">Check a product</Button>{/snippet}
		</EmptyState>
	{/if}
{/if}
