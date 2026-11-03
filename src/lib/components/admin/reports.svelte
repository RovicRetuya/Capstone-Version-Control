<script lang="ts">
	import MailIcon from '@lucide/svelte/icons/mail';
	import SearchIcon from '@lucide/svelte/icons/search';
	import { toast } from 'svelte-sonner';
	import EmptyState from '#lib/components/app/empty-state.svelte';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card } from '#lib/components/ui/card/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import * as Select from '#lib/components/ui/select/index.js';
	import { Skeleton } from '#lib/components/ui/skeleton/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { REPORT_CATEGORIES, reportTime } from '#lib/problem-report.js';
	import { reports } from '#lib/stores/admin-reports.svelte.js';

	// The problem reports people send from the site's "Report a problem" form (problem_reports.py). The admin reads
	// them here, writes back to the sender when they left an email, and marks each handled when it has been dealt with.
	const STATUSES: [typeof reports.status, string][] = [
		['new', 'Needs a look'],
		['done', 'Handled'],
		['all', 'All reports']
	];
	const KINDS: [string, string][] = [['', 'Any kind'], ...REPORT_CATEGORIES];
	const nameOf = (list: [string, string][], value: string) => list.find(([key]) => key === value)?.[1] ?? '';

	reports.load();

	let timer: ReturnType<typeof setTimeout> | undefined;
	function onSearch() {
		clearTimeout(timer);
		timer = setTimeout(() => reports.load(), 250);
	}

	async function mark(id: number, status: 'new' | 'done') {
		try {
			await reports.mark(id, status);
			toast.success(status === 'done' ? 'Marked as handled.' : 'Opened again.');
		} catch (error) {
			toast.error((error as Error).message);
		}
	}
	const narrowed = $derived(reports.status !== 'all' || reports.category !== '' || reports.query.trim() !== '');
	function showAll() {
		reports.status = 'all';
		reports.category = '';
		reports.query = '';
		reports.load();
	}
</script>

<div class="flex flex-col gap-4">
	<div class="flex flex-col gap-3 lg:flex-row lg:items-end">
		<div class="grid w-full gap-2 lg:max-w-sm">
			<Label for="report-search">Search reports</Label>
			<div class="relative">
				<SearchIcon class="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
				<Input id="report-search" type="search" class="pl-9" placeholder="Words, a name, an email or a page" bind:value={reports.query} oninput={onSearch} />
			</div>
		</div>
		<div class="grid gap-2">
			<Label for="report-status">Show</Label>
			<Select.Root type="single" value={reports.status} onValueChange={(value) => ((reports.status = value as typeof reports.status), reports.load())}>
				<Select.Trigger id="report-status" class="w-full sm:w-48">{nameOf(STATUSES, reports.status)}</Select.Trigger>
				<Select.Content>
					{#each STATUSES as [key, text] (key)}<Select.Item value={key} label={text}>{text}</Select.Item>{/each}
				</Select.Content>
			</Select.Root>
		</div>
		<div class="grid gap-2">
			<Label for="report-kind-filter">Kind</Label>
			<Select.Root type="single" value={reports.category} onValueChange={(value) => ((reports.category = value), reports.load())}>
				<Select.Trigger id="report-kind-filter" class="w-full sm:w-64">{nameOf(KINDS, reports.category)}</Select.Trigger>
				<Select.Content>
					{#each KINDS as [key, text] (key)}<Select.Item value={key} label={text}>{text}</Select.Item>{/each}
				</Select.Content>
			</Select.Root>
		</div>
		{#if reports.data}
			<p class="text-muted-foreground text-sm lg:ml-auto" aria-live="polite">
				{reports.data.counts.new} {reports.data.counts.new === 1 ? 'needs' : 'need'} a look · {reports.data.counts.done} handled
			</p>
		{/if}
	</div>

	{#if reports.failed && !reports.data}
		<EmptyState art="error" title="The reports couldn't be loaded" description={reports.failed}>
			{#snippet actions()}<Button onclick={() => reports.load()}>Try again</Button>{/snippet}
		</EmptyState>
	{:else if !reports.data}
		<div class="grid gap-3" role="status" aria-label="Loading reports">
			{#each [0, 1, 2] as row (row)}<Skeleton class="h-28 w-full" />{/each}
		</div>
	{:else if !reports.data.reports.length}
		{#if reports.data.counts.total === 0}
			<EmptyState art="reviews" title="No reports yet" description="When someone uses Report a problem on the site, it shows up here." />
		{:else if reports.status === 'new' && reports.category === '' && !reports.query.trim()}
			<EmptyState art="reviews" title="Nothing needs a look" description="Every report has been handled." >
				{#snippet actions()}<Button variant="outline" onclick={showAll}>Show all reports</Button>{/snippet}
			</EmptyState>
		{:else}
			<EmptyState art="search" title="No reports match" description="Try other words, or another kind or status.">
				{#snippet actions()}<Button variant="outline" onclick={showAll}>Show all reports</Button>{/snippet}
			</EmptyState>
		{/if}
	{:else}
		<ul class="grid gap-3" aria-label="Problem reports">
			{#each reports.data.reports as report (report.id)}
				<li data-report={report.id}>
					<Card class="gap-3 p-4">
						<div class="flex flex-wrap items-center gap-2">
							<Badge variant="secondary">{report.label}</Badge>
							{#if report.status === 'new'}<Badge>New</Badge>{:else}<Badge variant="outline">Handled</Badge>{/if}
							<span class="text-muted-foreground text-sm">#{report.id} · {reportTime(report.created_at)}</span>
						</div>
						<p class="text-sm whitespace-pre-wrap break-words">{report.message}</p>
						<dl class="text-muted-foreground grid gap-1 text-sm sm:grid-cols-[auto_1fr] sm:gap-x-4">
							<dt class="font-medium">From</dt>
							<dd class="min-w-0 break-words">
								{#if report.user}{report.user.name} <span class="text-muted-foreground">({report.user.email})</span>{:else}A guest, not signed in{/if}
							</dd>
							{#if report.email}
								<dt class="font-medium">Write back to</dt>
								<dd class="min-w-0 break-all">
									<a class="text-primary inline-flex items-center gap-1 underline underline-offset-4" href="mailto:{report.email}?subject={encodeURIComponent(`Your DeFaketive report #${report.id}`)}">
										<MailIcon class="size-3.5" aria-hidden="true" />{report.email}
									</a>
								</dd>
							{/if}
							{#if report.page}
								<dt class="font-medium">Page</dt>
								<dd class="min-w-0 font-mono text-xs break-all">{report.page}</dd>
							{/if}
						</dl>
						<div>
							{#if report.status === 'new'}
								<Button size="sm" disabled={reports.busy === report.id} onclick={() => mark(report.id, 'done')}>
									{#if reports.busy === report.id}<Spinner />{/if} Mark as handled
								</Button>
							{:else}
								<Button size="sm" variant="outline" disabled={reports.busy === report.id} onclick={() => mark(report.id, 'new')}>
									{#if reports.busy === report.id}<Spinner />{/if} Open again
								</Button>
							{/if}
						</div>
					</Card>
				</li>
			{/each}
		</ul>
		{#if narrowed && reports.data.reports.length < reports.data.counts.total}
			<p class="text-muted-foreground text-sm">Showing {reports.data.reports.length} of {reports.data.counts.total}. <button type="button" class="text-primary underline underline-offset-4" onclick={showAll}>Show all</button></p>
		{/if}
	{/if}
</div>
