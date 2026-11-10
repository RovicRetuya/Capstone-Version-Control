<script lang="ts">
	import MenuIcon from '@lucide/svelte/icons/menu';
	import * as Sheet from '#lib/components/ui/sheet/index.js';
	import ShieldCheckIcon from '@lucide/svelte/icons/shield-check';
	import { Button } from '#lib/components/ui/button/index.js';
	import { firstName } from '#lib/product.js';
	import { session as adminSession } from '#lib/stores/admin.svelte.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { signOut } from '#lib/session.js';
	import { ui } from '#lib/stores/ui.svelte.js';
	import Logo from './logo.svelte';
	import ThemeToggle from './theme-toggle.svelte';

	let menuOpen = $state(false);

	// The admin signs in apart from shoppers, so ask whether they are here: if so, the header offers the admin page.
	if (!adminSession.ready) void adminSession.load();
	async function adminSignOut() {
		await adminSession.signOut();
	}

</script>

<header class="bg-background/80 sticky top-0 z-40 border-b backdrop-blur">
	<div class="mx-auto flex h-14 w-full max-w-6xl items-center gap-2 px-3 sm:gap-4 sm:px-4 md:px-6">
		<Logo href="/" class="shrink-0 max-[380px]:[&>span]:hidden" />
		<nav class="ml-4 hidden items-center gap-1 text-sm md:flex" aria-label="Main navigation">
			<!-- Every link stays on the public site, in the order the landing page shows the sections. -->
			<Button variant="ghost" size="sm" href="/#how">How it works</Button>
			<Button variant="ghost" size="sm" href="/#faq">FAQ</Button>
			<Button variant="ghost" size="sm" href="/#about">About</Button>
		</nav>
		<div class="ml-auto hidden min-w-0 items-center gap-1 md:flex">
			<span class="max-[360px]:hidden"><ThemeToggle /></span>
			{#if adminSession.me}
				<span class="text-muted-foreground mx-2 hidden text-sm sm:inline">Hi, {firstName(adminSession.me.name)}</span>
				<Button variant="ghost" size="sm" class="max-[420px]:hidden" onclick={adminSignOut}>Sign out</Button>
				<Button size="sm" href="/admin"><ShieldCheckIcon /> Admin</Button>
			{:else if auth.user}
				<span class="text-muted-foreground mx-2 hidden text-sm sm:inline">Hi, {firstName(auth.user.name)}</span>
				<Button variant="ghost" size="sm" class="max-[420px]:hidden" onclick={signOut}>Sign out</Button>
				<Button size="sm" href="/app/home">Open app</Button>
			{:else}
				<Button variant="ghost" size="sm" onclick={() => ui.openAuth('signin')}>Sign in</Button>
				<Button size="sm" onclick={() => ui.openAuth('signup')}>Create account</Button>
			{/if}
		</div>
		<div class="ml-auto md:hidden">
			<Sheet.Root bind:open={menuOpen}>
				<Sheet.Trigger>
					{#snippet child({ props })}
						<Button {...props} variant="ghost" size="icon" aria-label="Open navigation menu">
							<MenuIcon aria-hidden="true" />
						</Button>
					{/snippet}
				</Sheet.Trigger>
				<Sheet.Content side="right" class="overflow-y-auto">
					<Sheet.Header class="pr-14">
						<Sheet.Title>Menu</Sheet.Title>
						<Sheet.Description>Explore Defaketive and manage your account.</Sheet.Description>
					</Sheet.Header>
					<nav class="flex flex-col gap-1 px-4" aria-label="Mobile navigation">
						{#each [{ href: '/#how', label: 'How it works' }, { href: '/#faq', label: 'FAQ' }, { href: '/#about', label: 'About' }] as link}
							<Button variant="ghost" class="min-h-11 justify-start" href={link.href} onclick={() => (menuOpen = false)}>{link.label}</Button>
						{/each}
					</nav>
					<div class="mx-4 flex items-center justify-between border-t pt-4">
						<span>Theme</span>
						<ThemeToggle />
					</div>
					<div class="mx-4 mb-4 flex flex-col gap-2 border-t pt-4">
						{#if adminSession.me}
							<p class="text-muted-foreground mb-2 text-sm">Hi, {firstName(adminSession.me.name)}</p>
							<Button class="min-h-11" href="/admin" onclick={() => (menuOpen = false)}><ShieldCheckIcon /> Admin</Button>
							<Button variant="ghost" class="min-h-11" onclick={() => { menuOpen = false; void adminSignOut(); }}>Sign out</Button>
						{:else if auth.user}
							<p class="text-muted-foreground mb-2 text-sm">Hi, {firstName(auth.user.name)}</p>
							<Button class="min-h-11" href="/app/home" onclick={() => (menuOpen = false)}>Open app</Button>
							<Button variant="ghost" class="min-h-11" onclick={() => { menuOpen = false; void signOut(); }}>Sign out</Button>
						{:else}
							<Button variant="ghost" class="min-h-11" onclick={() => { menuOpen = false; ui.openAuth('signin'); }}>Sign in</Button>
							<Button class="min-h-11" onclick={() => { menuOpen = false; ui.openAuth('signup'); }}>Create account</Button>
						{/if}
					</div>
				</Sheet.Content>
			</Sheet.Root>
		</div>
	</div>
</header>
