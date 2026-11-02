<script lang="ts">
	import { goto } from '$app/navigation';
	import KeyRoundIcon from '@lucide/svelte/icons/key-round';
	import LogOutIcon from '@lucide/svelte/icons/log-out';
	import { toast } from 'svelte-sonner';
	import Accounts from '#lib/components/admin/accounts.svelte';
	import Limits from '#lib/components/admin/limits.svelte';
	import PasswordDialog from '#lib/components/admin/password-dialog.svelte';
	import EmptyState from '#lib/components/app/empty-state.svelte';
	import Logo from '#lib/components/app/logo.svelte';
	import ThemeToggle from '#lib/components/app/theme-toggle.svelte';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { Tabs, TabsContent, TabsList, TabsTrigger } from '#lib/components/ui/tabs/index.js';
	import { session } from '#lib/stores/admin.svelte.js';

	// The admin side of the app (admin_api.py). Only the one admin account gets in: anyone else goes to the sign-in page.
	session.load();
	$effect(() => {
		if (session.ready && !session.me && !session.unreachable) void goto('/enter', { replaceState: true });
	});

	// The open tab is in the address (?tab=limits), so a reload opens the same one.
	let tab = $state(new URL(location.href).searchParams.get('tab') === 'limits' ? 'limits' : 'accounts');
	$effect(() => {
		const url = new URL(location.href);
		if (tab === 'limits') url.searchParams.set('tab', 'limits');
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
				<p class="text-muted-foreground">Manage the accounts on DeFaketive and how many new checks can start each day.</p>
			</header>

			<Tabs bind:value={tab} onValueChange={recheck} class="gap-6">
				<TabsList>
					<TabsTrigger value="accounts">Manage accounts</TabsTrigger>
					<TabsTrigger value="limits">Daily limits</TabsTrigger>
				</TabsList>
				<TabsContent value="accounts"><Accounts /></TabsContent>
				<TabsContent value="limits"><Limits /></TabsContent>
			</Tabs>
		{/if}
	</main>
</div>

<PasswordDialog bind:open={passwordOpen} />
