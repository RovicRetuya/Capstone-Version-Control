<script lang="ts">
	import { goto } from '$app/navigation';
	import KeyRoundIcon from '@lucide/svelte/icons/key-round';
	import LogOutIcon from '@lucide/svelte/icons/log-out';
	import { untrack } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Accounts from '#lib/components/admin/accounts.svelte';
	import Filters from '#lib/components/admin/filters.svelte';
	import Limits from '#lib/components/admin/limits.svelte';
	import PasswordDialog from '#lib/components/admin/password-dialog.svelte';
	import PasswordRequests from '#lib/components/admin/password-requests.svelte';
	import Products from '#lib/components/admin/products.svelte';
	import Reports from '#lib/components/admin/reports.svelte';
	import EmptyState from '#lib/components/app/empty-state.svelte';
	import Logo from '#lib/components/app/logo.svelte';
	import ThemeToggle from '#lib/components/app/theme-toggle.svelte';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { Tabs, TabsContent, TabsList, TabsTrigger } from '#lib/components/ui/tabs/index.js';
	import { passwordRequests } from '#lib/stores/admin-requests.svelte.js';
	import { reports } from '#lib/stores/admin-reports.svelte.js';
	import { session } from '#lib/stores/admin.svelte.js';

	// The admin side of the app (admin_api.py). Only the one admin account gets in: anyone else goes to the sign-in page.
	session.load();
	$effect(() => {
		if (session.ready && !session.me && !session.unreachable) void goto('/enter', { replaceState: true });
	});

	// The tabs say how many reports and password requests are new, so they are loaded as soon as they are signed in.
	$effect(() => {
		if (session.me) untrack(() => {
			reports.load();
			passwordRequests.load();
		});
	});

	// The open tab is in the address (?tab=limits), so a reload opens the same one.
	const TABS = ['accounts', 'products', 'limits', 'filters', 'reports', 'passwords'];
	const asked = new URL(location.href).searchParams.get('tab') ?? '';
	let tab = $state(TABS.includes(asked) ? asked : 'accounts');
	$effect(() => {
		const url = new URL(location.href);
		if (tab !== 'accounts') url.searchParams.set('tab', tab);
		else url.searchParams.delete('tab');
		if (url.href !== location.href) history.replaceState(history.state, '', url);
	});

	// The session may have ended meanwhile: check again on a tab switch or a return to the window.
	function recheck() {
		if (session.me) session.load();
	}

	let passwordOpen = $state(false);

	async function signOut() {
		try {
			await session.signOut();
			toast("You're signed out.");
			await goto('/');
		} catch (error) {
			toast.error((error as Error).message);
		}
	}
</script>

<svelte:head><title>DeFaketive · Admin</title></svelte:head>
<svelte:window onfocus={recheck} />

<div class="flex min-h-svh flex-col">
	<header class="bg-background/80 sticky top-0 z-30 border-b backdrop-blur">
		<div class="mx-auto flex h-14 w-full max-w-6xl items-center gap-3 px-4 md:px-6">
			<Logo href="/" />
			<Badge variant="secondary">Admin</Badge>
			<div class="ml-auto flex items-center gap-1">
				{#if session.me}
					<span class="text-muted-foreground hidden max-w-56 truncate text-sm md:inline" title={session.me.email}>{session.me.name}</span>
					<Button variant="ghost" size="sm" onclick={() => (passwordOpen = true)}><KeyRoundIcon /> <span class="hidden sm:inline">Change password</span><span class="sr-only sm:hidden">Change password</span></Button>
					<Button variant="ghost" size="sm" onclick={signOut}><LogOutIcon /> <span class="hidden sm:inline">Sign out</span><span class="sr-only sm:hidden">Sign out</span></Button>
				{/if}
				<ThemeToggle />
			</div>
		</div>
	</header>

	<main class="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 p-4 md:p-6 lg:p-8">
		{#if !session.ready || (!session.me && !session.unreachable)}
			<div class="text-muted-foreground grid min-h-[50svh] place-items-center text-center" role="status">
				<span class="flex items-center gap-2 text-sm"><Spinner /> Opening the admin side…</span>
			</div>
		{:else if !session.me}
			<EmptyState art="error" title="The server didn't answer" description="Check that DeFaketive's server is running, then try again.">
				{#snippet actions()}<Button onclick={() => session.load()}>Try again</Button>{/snippet}
			</EmptyState>
		{:else}
			<header class="space-y-1">
				<h1 class="text-3xl font-semibold tracking-tight">Admin</h1>
				<p class="text-muted-foreground">Manage the accounts on DeFaketive, see the products it has saved, set how many new checks can start each day and what the Products page offers, and handle the problems and password requests people send.</p>
			</header>

			<Tabs bind:value={tab} onValueChange={recheck} class="gap-6">
				<!-- Six tabs are wider than a phone: let them wrap onto a second line there. -->
				<TabsList class="max-w-full flex-wrap justify-start group-data-horizontal/tabs:h-auto [&>[data-slot=tabs-trigger]]:flex-none">
					<TabsTrigger value="accounts">Manage accounts</TabsTrigger>
					<TabsTrigger value="products">Saved products</TabsTrigger>
					<TabsTrigger value="limits">Daily limits</TabsTrigger>
					<TabsTrigger value="filters">Products page</TabsTrigger>
					<TabsTrigger value="reports">
						Reports
						{#if reports.newCount}<Badge class="ml-1 px-1.5">{reports.newCount}<span class="sr-only"> new</span></Badge>{/if}
					</TabsTrigger>
					<TabsTrigger value="passwords">
						Password requests
						{#if passwordRequests.newCount}<Badge class="ml-1 px-1.5">{passwordRequests.newCount}<span class="sr-only"> new</span></Badge>{/if}
					</TabsTrigger>
				</TabsList>
				<TabsContent value="accounts"><Accounts /></TabsContent>
				<TabsContent value="products"><Products /></TabsContent>
				<TabsContent value="limits"><Limits /></TabsContent>
				<TabsContent value="filters"><Filters /></TabsContent>
				<TabsContent value="reports"><Reports /></TabsContent>
				<TabsContent value="passwords"><PasswordRequests /></TabsContent>
			</Tabs>
		{/if}
	</main>
</div>

<PasswordDialog bind:open={passwordOpen} />
