<script lang="ts">
	import './layout.css';
	import favicon from '#lib/assets/favicon.svg';
	import { goto, onNavigate } from '$app/navigation';
	import { ModeWatcher } from 'mode-watcher';
	import { onMount } from 'svelte';
	import { boot } from '#lib/boot.js';
	import CommandPalette from '#lib/components/app/command-palette.svelte';
	import ProblemReportDialog from '#lib/components/app/problem-report-dialog.svelte';
	import AuthDialog from '#lib/components/app/auth-dialog.svelte';
	import OfflineBanner from '#lib/components/app/offline-banner.svelte';
	import TermsDialog from '#lib/components/app/terms-dialog.svelte';
	import Splash from '#lib/components/app/splash.svelte';
	import WelcomeTour from '#lib/components/app/welcome-tour.svelte';
	import { Toaster } from '#lib/components/ui/sonner/index.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { library } from '#lib/stores/library.svelte.js';
	import { prefs } from '#lib/stores/prefs.svelte.js';
	import { scan } from '#lib/stores/scan.svelte.js';
	import { ui } from '#lib/stores/ui.svelte.js';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	// Page changes cross-fade (where the browser supports it). Only the part named `page-view` moves.
	onNavigate((navigation) => {
		if (!document.startViewTransition || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
		return new Promise((resolve) => {
			document.startViewTransition(async () => {
				resolve();
				await navigation.complete;
			});
		});
	});

	// Keyboard shortcuts. Ctrl+K (or Cmd+K) opens search. "/" jumps to the link box, like many sites do.
	function typing(target: EventTarget | null) {
		const el = target as HTMLElement | null;
		return Boolean(el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)));
	}
	function onkeydown(event: KeyboardEvent) {
		if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
			event.preventDefault();
			ui.commandOpen = !ui.commandOpen;
			return;
		}
		if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey || event.defaultPrevented) return;
		if (typing(event.target) || ui.commandOpen || ui.authOpen || ui.termsOpen || ui.tourOpen) return;
		event.preventDefault();
		const bar = document.querySelector<HTMLInputElement>('[data-scan-input]');
		if (bar) {
			bar.focus();
			bar.select();
		} else {
			// No scan bar on this page: open Analyze (the guest screen for a guest) and focus its bar there.
			ui.focusScan = true;
			goto(auth.user ? '/app/analyze' : '/scan');
		}
	}

	// Everything the app needs on every page is loaded once, here (see boot.ts; "Try again" runs it again).
	onMount(async () => {
		library.start();
		prefs.start();
		await boot();
		scan.restore();
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>DeFaketive</title>
</svelte:head>

<svelte:window {onkeydown} />

<ModeWatcher />
<Toaster position="bottom-right" />

<Splash />
<OfflineBanner />
<a class="skip-link" href="#main-content" onclick={(event) => {
	const main = document.querySelector<HTMLElement>('main');
	if (main) {
		event.preventDefault();
		if (!main.id) main.id = 'main-content';
		main.tabIndex = -1;
		main.focus();
		main.scrollIntoView({ block: 'start' });
	}
}}>Skip to main content</a>
{@render children()}

<AuthDialog />
<TermsDialog />
<CommandPalette />
{#if auth.user}<WelcomeTour /><ProblemReportDialog />{/if}
