<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import EllipsisIcon from '@lucide/svelte/icons/ellipsis';
	import ChevronDownIcon from '@lucide/svelte/icons/chevron-down';
	import CircleHelpIcon from '@lucide/svelte/icons/circle-help';
	import FlagIcon from '@lucide/svelte/icons/flag';
	import HeartIcon from '@lucide/svelte/icons/heart';
	import HistoryIcon from '@lucide/svelte/icons/history';
	import HouseIcon from '@lucide/svelte/icons/house';
	import InfoIcon from '@lucide/svelte/icons/info';
	import LogOutIcon from '@lucide/svelte/icons/log-out';
	import PackageSearchIcon from '@lucide/svelte/icons/package-search';
	import PuzzleIcon from '@lucide/svelte/icons/puzzle';
	import ScanSearchIcon from '@lucide/svelte/icons/scan-search';
	import SearchIcon from '@lucide/svelte/icons/search';
	import SettingsIcon from '@lucide/svelte/icons/settings';
	import type { Component } from 'svelte';
	import logo from '#lib/assets/logo.png';
	import texture from '#lib/assets/page-texture.jpg';
	import ScanPill from '#lib/components/app/scan-pill.svelte';
	import SiteFooter from '#lib/components/app/site-footer.svelte';
	import ThemeToggle from '#lib/components/app/theme-toggle.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import {
		DropdownMenu,
		DropdownMenuContent,
		DropdownMenuItem,
		DropdownMenuLabel,
		DropdownMenuSeparator,
		DropdownMenuTrigger
	} from '#lib/components/ui/dropdown-menu/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { guestDestination } from '#lib/nav.js';
	import { initials } from '#lib/product.js';
	import { signOut } from '#lib/session.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { ui } from '#lib/stores/ui.svelte.js';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	// The round icons down the left (along the bottom on a phone), in the order people use them.
	type Item = { href: string; label: string; icon: Component };
	const items: Item[] = [
		{ href: '/app/home', label: 'Home', icon: HouseIcon },
		{ href: '/app/analyze', label: 'Check', icon: ScanSearchIcon },
		{ href: '/app/products', label: 'Products', icon: PackageSearchIcon },
		{ href: '/app/history', label: 'History', icon: HistoryIcon },
		{ href: '/app/wishlist', label: 'Wishlist', icon: HeartIcon },
		{ href: '/app/about', label: 'About', icon: InfoIcon },
		{ href: '/app/faq', label: 'FAQ', icon: CircleHelpIcon }
	];
	const active = (href: string) => page.url.pathname === href;
	const mobileItems = items.filter(item => ['Home', 'Check', 'Products', 'Wishlist'].includes(item.label));
	const moreItems = items.filter(item => ['History', 'About', 'FAQ'].includes(item.label));

	// The app is for signed-in people. A guest who lands on one of its pages (a typed address, an old bookmark,
	// a shared link) is sent to the public screen that does the same job, or asked to sign in when there is none.
	// Nothing of the app is drawn until we know who is here.
	// When the server cannot be reached we do not know who is here, so nobody is sent anywhere: the banner at
	// the top of the page says what is wrong and offers "Try again".
	$effect(() => {
		if (!auth.ready || auth.user || ui.leaving || auth.unreachable) return;
		const wanted = page.url.pathname + page.url.search;
		const target = guestDestination(page.url);
		goto(target.href, { replaceState: true }).then(() => {
			if (target.signIn) ui.openAuth('signin', 'Sign in or create a free account to open that page.', wanted);
		});
	});
</script>

{#if !auth.user}
	<div class="text-muted-foreground grid min-h-[70svh] place-items-center px-4 text-center" role="status">
		{#if auth.unreachable}
			<span class="text-sm">Nothing can be shown until the server answers.</span>
		{:else}
			<span class="flex items-center gap-2 text-sm"><Spinner /> Opening DeFaketive…</span>
		{/if}
	</div>
{:else}
	<div class="tex-page tex-warm flex min-h-svh flex-col" style:--tex="url({texture})">
		<header data-print="hide" class="bg-background/85 sticky top-0 z-30 flex h-[70px] [@media(max-height:480px)]:static shrink-0 items-center gap-2 border-b px-3 backdrop-blur sm:gap-3 sm:px-4 md:px-6">
			<a href="/app/home" class="flex shrink-0 items-center gap-3" aria-label="DeFaketive V0.9 BETA, home">
				<img src={logo} alt="" class="size-10 shrink-0" />
				<span class="hidden leading-none min-[420px]:block">
					<span class="block text-lg font-extrabold tracking-tight">DeFaketive</span>
					<span class="text-muted-foreground block font-mono text-[10px] tracking-widest">V0.9 BETA</span>
				</span>
			</a>
			<span class="bg-border mx-2 hidden h-9 w-px lg:block" aria-hidden="true"></span>
			<p class="text-muted-foreground hidden font-mono text-[11px] leading-[1.45] tracking-[0.18em] uppercase lg:block">
				Real products.<br />Real reviews.<br />A safer you.
			</p>
			<div class="ml-auto flex min-w-0 items-center gap-1 sm:gap-2">
				<ul class="text-muted-foreground mr-3 hidden items-center gap-4 font-mono text-xs xl:flex" aria-label="Marketplaces checked">
					<li class="flex items-center gap-1.5"><span class="size-1.5 rounded-full bg-[#ee4d2d]" aria-hidden="true"></span> Shopee</li>
					<li class="flex items-center gap-1.5"><span class="size-1.5 rounded-full bg-[#0f146d]" aria-hidden="true"></span> Lazada</li>
				</ul>
				<ScanPill />
				<Button variant="ghost" size="icon" aria-label="Search pages and products" onclick={() => (ui.commandOpen = true)}><SearchIcon /></Button>
				<Button variant="ghost" size="sm" aria-label="Report a problem" class="max-sm:size-9 max-sm:px-0" onclick={() => ui.openReport()}>
					<FlagIcon /> <span class="max-lg:sr-only">Report</span>
				</Button>
				<Button variant="ghost" size="icon" href="/app/settings" aria-label="Settings" class="max-sm:hidden"><SettingsIcon /></Button>
				<ThemeToggle />
				<DropdownMenu>
					<DropdownMenuTrigger>
						{#snippet child({ props })}
							<button type="button" {...props} class="hover:bg-accent focus-visible:ring-ring flex shrink-0 items-center gap-2 rounded-full py-1 pr-1 pl-1 sm:ml-1 sm:pr-2 text-sm font-medium outline-none focus-visible:ring-2">
								<span class="bg-foreground text-background grid size-9 place-items-center rounded-full text-xs font-bold" aria-hidden="true">{initials(auth.user?.name)}</span>
								<span class="max-w-40 truncate max-sm:sr-only">{auth.user?.name}</span>
								<ChevronDownIcon class="size-4 opacity-60 max-sm:hidden" />
							</button>
						{/snippet}
					</DropdownMenuTrigger>
					<DropdownMenuContent align="end" class="min-w-56">
						<DropdownMenuLabel class="text-muted-foreground text-xs font-normal">
							{auth.user?.email}<br />Your history and wishlist are saved to your account.
						</DropdownMenuLabel>
						<DropdownMenuSeparator />
						<DropdownMenuItem onclick={() => goto('/app/settings')}><SettingsIcon /> Settings</DropdownMenuItem>
						<DropdownMenuItem onclick={() => goto('/app/extension')}><PuzzleIcon /> Get the extension</DropdownMenuItem>
						<DropdownMenuItem onclick={() => ui.openReport()}><FlagIcon /> Report a problem</DropdownMenuItem>
						<DropdownMenuItem onclick={signOut}><LogOutIcon /> Sign out</DropdownMenuItem>
					</DropdownMenuContent>
				</DropdownMenu>
			</div>
		</header>

		<div class="flex min-w-0 flex-1">
			<!-- The round icons down the left of the page (data-sidebar names them for the tests). -->
			<nav data-print="hide" data-sidebar="sidebar" aria-label="Main" class="sticky top-[70px] hidden h-[calc(100svh-70px)] w-24 shrink-0 flex-col items-center gap-3 overflow-y-auto pt-7 md:flex">
				{#each items as item (item.href)}
					<a href={item.href} data-sidebar="menu-button" aria-current={active(item.href) ? 'page' : undefined} class="group flex w-full flex-col items-center gap-1.5 outline-none">
						<span class="group-focus-visible:ring-ring grid size-12 place-items-center rounded-full border shadow-sm transition group-hover:-translate-y-0.5 group-focus-visible:ring-2 {active(item.href) ? 'bg-foreground text-background border-foreground shadow-md' : 'bg-background text-foreground/80'}">
							<item.icon class="size-5" />
						</span>
						<span class="px-1 text-center text-xs leading-snug {active(item.href) ? 'font-semibold text-foreground' : 'text-muted-foreground'}">{item.label}</span>
					</a>
				{/each}
			</nav>

			<div class="flex min-w-0 flex-1 flex-col">
				<main id="main-content" tabindex="-1" class="page-view flex min-w-0 flex-1 flex-col gap-6 px-4 pt-6 pb-[calc(6rem+env(safe-area-inset-bottom))] md:px-6 md:pb-8 lg:px-8">
					<div class="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6">
						{@render children()}
					</div>
				</main>
				<div data-print="hide"><SiteFooter compact /></div>
			</div>
		</div>

		<!-- On a phone the icons run along the bottom. -->
		<nav data-print="hide" aria-label="Main" class="bg-background/95 fixed inset-x-0 bottom-0 z-30 flex justify-start gap-0.5 overflow-x-auto border-t px-1 pt-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))] backdrop-blur min-[380px]:gap-1 min-[380px]:px-2 md:hidden">
			{#each mobileItems as item (item.href)}
				<a href={item.href} aria-current={active(item.href) ? 'page' : undefined} class="focus-visible:ring-ring flex min-w-fit flex-1 flex-col items-center gap-1 rounded-lg px-1 py-1 outline-none focus-visible:ring-2">
					<span class="grid size-9 place-items-center rounded-full border {active(item.href) ? 'bg-foreground text-background border-foreground' : 'bg-background'}"><item.icon class="size-4" /></span>
					<span class="text-center text-xs leading-snug {active(item.href) ? 'font-semibold text-foreground' : 'text-muted-foreground'}">{item.label === 'Wishlist' ? 'Saved' : item.label}</span>
				</a>
			{/each}
			<DropdownMenu>
				<DropdownMenuTrigger>
					{#snippet child({ props })}
						<button {...props} type="button" aria-label="More navigation" class="focus-visible:ring-ring flex min-w-0 flex-1 flex-col items-center gap-1 rounded-lg px-1 py-1 outline-none focus-visible:ring-2">
							<span class="grid size-9 place-items-center rounded-full border {moreItems.some(item => active(item.href)) ? 'bg-foreground text-background border-foreground' : 'bg-background'}"><EllipsisIcon class="size-4" /></span>
							<span class="text-center text-xs leading-snug {moreItems.some(item => active(item.href)) ? 'font-semibold text-foreground' : 'text-muted-foreground'}">More</span>
						</button>
					{/snippet}
				</DropdownMenuTrigger>
				<DropdownMenuContent side="top" align="end" class="min-w-44">
					<DropdownMenuLabel>More pages</DropdownMenuLabel>
					{#each moreItems as item (item.href)}
						<DropdownMenuItem class="min-h-11">
							{#snippet child({ props })}
								<a {...props} href={item.href} aria-current={active(item.href) ? 'page' : undefined}><item.icon /> {item.label}</a>
							{/snippet}
						</DropdownMenuItem>
					{/each}
				</DropdownMenuContent>
			</DropdownMenu>
		</nav>
	</div>
{/if}
