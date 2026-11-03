<script lang="ts">
	import SearchIcon from '@lucide/svelte/icons/search';
	import ShieldCheckIcon from '@lucide/svelte/icons/shield-check';
	import UserPlusIcon from '@lucide/svelte/icons/user-plus';
	import EmptyState from '#lib/components/app/empty-state.svelte';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card } from '#lib/components/ui/card/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import { Skeleton } from '#lib/components/ui/skeleton/index.js';
	import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '#lib/components/ui/table/index.js';
	import { adminApi } from '#lib/stores/admin.svelte.js';
	import AddAccountDialog from './add-account-dialog.svelte';
	import type { AdminAccount, AdminAccounts } from '#lib/admin-types.js';

	// Every account on the site, with what an admin may do to it (admin_api.py says what is refused, and why).
	let found = $state<AdminAccounts | null>(null);
	let failed = $state('');
	let query = $state('');
	let searched = $state('');
	let adding = $state(false);

	let requestId = 0;
	async function load(q = query.trim()) {
		const id = ++requestId;
		failed = '';
		try {
			const answer = await adminApi<AdminAccounts>(`/api/admin/accounts?q=${encodeURIComponent(q)}`);
			if (id !== requestId) return;
			found = answer;
			searched = q;
		} catch (error) {
			if (id === requestId) failed = (error as Error).message;
		}
	}
	load();

	// Search as the admin types, a moment after they stop.
	let timer: ReturnType<typeof setTimeout> | undefined;
	function onSearch() {
		clearTimeout(timer);
		timer = setTimeout(() => load(), 250);
	}

	const joined = (iso: string) =>
		iso ? new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '—';
</script>

{#snippet role(account: AdminAccount)}
	{#if account.admin}<Badge><ShieldCheckIcon /> Admin</Badge>{:else}<Badge variant="outline">Shopper</Badge>{/if}
{/snippet}

{#snippet actions(account: AdminAccount)}
	{#if account.you || account.main}
		<span class="text-muted-foreground text-sm">{account.you ? 'This is you' : 'Main admin'}</span>
	{/if}
{/snippet}

<div class="flex flex-col gap-4">
	<div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
		<div class="grid w-full gap-2 sm:max-w-sm">
			<Label for="admin-search">Search accounts</Label>
			<div class="relative">
				<SearchIcon class="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
				<Input id="admin-search" type="search" class="pl-9" placeholder="Name or email" bind:value={query} oninput={onSearch} />
			</div>
		</div>
		<div class="flex flex-wrap items-center gap-3">
			{#if found}
				<p class="text-muted-foreground text-sm" aria-live="polite">
					{found.total} {found.total === 1 ? 'account' : 'accounts'} · {found.admins} {found.admins === 1 ? 'admin' : 'admins'}
					{#if searched}· {found.accounts.length} {found.accounts.length === 1 ? 'matches' : 'match'}{/if}
				</p>
			{/if}
			<Button onclick={() => (adding = true)}><UserPlusIcon /> Add account</Button>
		</div>
	</div>

	{#if failed && !found}
		<EmptyState art="error" title="The accounts couldn't be loaded" description={failed}>
			{#snippet actions()}<Button onclick={() => load()}>Try again</Button>{/snippet}
		</EmptyState>
	{:else if !found}
		<div class="grid gap-2" role="status" aria-label="Loading accounts">
			{#each [0, 1, 2, 3] as row (row)}<Skeleton class="h-12 w-full" />{/each}
		</div>
	{:else if !found.accounts.length}
		<EmptyState art="search" title="No accounts match" description="Try part of a name or an email address.">
			{#snippet actions()}<Button variant="outline" onclick={() => ((query = ''), load(''))}>Clear the search</Button>{/snippet}
		</EmptyState>
	{:else}
		<!-- Wide screens: one table. Phones: a card per account. -->
		<Card class="hidden py-0 md:block">
			<Table>
				<TableHeader>
					<TableRow>
						<TableHead class="pl-4">Name</TableHead>
						<TableHead>Email</TableHead>
						<TableHead>Joined</TableHead>
						<TableHead class="text-right">History</TableHead>
						<TableHead class="text-right">Wishlist</TableHead>
						<TableHead class="text-right">Checks today</TableHead>
						<TableHead>Role</TableHead>
						<TableHead class="pr-4"><span class="sr-only">Actions</span></TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{#each found.accounts as account (account.id)}
						<TableRow data-account={account.email}>
							<TableCell class="max-w-48 truncate pl-4 font-medium" title={account.name}>{account.name}</TableCell>
							<TableCell class="text-muted-foreground max-w-64 truncate" title={account.email}>{account.email}</TableCell>
							<TableCell class="text-muted-foreground whitespace-nowrap">{joined(account.joined)}</TableCell>
							<TableCell class="text-right tabular-nums">{account.history}</TableCell>
							<TableCell class="text-right tabular-nums">{account.wishlist}</TableCell>
							<TableCell class="text-right tabular-nums">{account.checks_today}</TableCell>
							<TableCell>{@render role(account)}</TableCell>
							<TableCell class="pr-4">{@render actions(account)}</TableCell>
						</TableRow>
					{/each}
				</TableBody>
			</Table>
		</Card>

		<ul class="grid grid-cols-1 gap-3 md:hidden" aria-label="Accounts">
			{#each found.accounts as account (account.id)}
				<li class="min-w-0" data-account={account.email}>
					<Card class="gap-3 p-4">
						<div class="flex items-start justify-between gap-3">
							<div class="min-w-0">
								<p class="truncate font-medium">{account.name}</p>
								<p class="text-muted-foreground truncate text-sm">{account.email}</p>
							</div>
							{@render role(account)}
						</div>
						<p class="text-muted-foreground text-sm">
							Joined {joined(account.joined)} · History {account.history} · Wishlist {account.wishlist} · {account.checks_today} today
						</p>
						{@render actions(account)}
					</Card>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<AddAccountDialog bind:open={adding} onadded={() => load(searched)} />
