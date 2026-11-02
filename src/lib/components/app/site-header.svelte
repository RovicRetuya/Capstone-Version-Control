<script lang="ts">
	import ShieldCheckIcon from '@lucide/svelte/icons/shield-check';
	import { Button } from '#lib/components/ui/button/index.js';
	import { firstName } from '#lib/product.js';
	import { session as adminSession } from '#lib/stores/admin.svelte.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { signOut } from '#lib/session.js';
	import { ui } from '#lib/stores/ui.svelte.js';
	import Logo from './logo.svelte';
	import ThemeToggle from './theme-toggle.svelte';

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
		<div class="ml-auto flex min-w-0 items-center gap-1">
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
	</div>
</header>
