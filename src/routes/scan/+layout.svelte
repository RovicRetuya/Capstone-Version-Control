<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import SiteFooter from '#lib/components/app/site-footer.svelte';
	import SiteHeader from '#lib/components/app/site-header.svelte';
	import { reportHref } from '#lib/nav.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	// The guest screen: checking a product without an account, and without the main app around it.
	// Someone who is signed in belongs in the app, so they are sent to the same thing there.
	$effect(() => {
		if (!auth.ready || !auth.user) return;
		const link = page.url.searchParams.get('link');
		const query = page.url.searchParams.get('q');
		if (page.url.pathname.startsWith('/scan/report') && link) goto(reportHref(link), { replaceState: true });
		else goto(query ? `/app/analyze?q=${encodeURIComponent(query)}` : '/app/analyze', { replaceState: true });
	});
</script>

<div class="flex min-h-svh flex-col">
	<SiteHeader />
	<main id="main-content" tabindex="-1" class="page-view mx-auto flex w-full min-w-0 max-w-5xl flex-1 flex-col gap-6 px-4 py-8 sm:gap-8 md:px-6 md:py-12">
		{@render children()}
	</main>
	<SiteFooter />
</div>
