<script lang="ts">
	import { goto } from '$app/navigation';
	import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
	import ClearLinkButton from '#lib/components/app/clear-link-button.svelte';
	import LinkIcon from '@lucide/svelte/icons/link';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { Kbd } from '#lib/components/ui/kbd/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { InputGroup, InputGroupAddon, InputGroupInput } from '#lib/components/ui/input-group/index.js';
	import { guestReportHref } from '#lib/nav.js';
	import { queryContext, scannable } from '#lib/product.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { catalog } from '#lib/stores/catalog.svelte.js';
	import { prefs } from '#lib/stores/prefs.svelte.js';
	import { scan } from '#lib/stores/scan.svelte.js';

	let {
		autofill = false,
		size = 'lg',
		placeholder = 'Paste a Lazada PH link...',
		target = '/app/analyze'
	}: { autofill?: boolean; size?: 'default' | 'lg'; placeholder?: string; target?: string } = $props();

	let value = $state('');
	const instanceId = $props.id();
	const helpId = `${instanceId}-help`;
	let lastClipboard = '';

	const note = $derived(
		auth.user
			? 'Press Enter to check · unlimited scans with your account'
			: `Press Enter to check · ${auth.left > 0 ? `${auth.left} free scan${auth.left === 1 ? '' : 's'} left today as a guest` : 'no free scans left today'} · sign in for unlimited`
	);

	// A copied product link is put in the bar. It never starts a scan by itself.
	onMount(async () => {
		if (!autofill || !prefs.clipboard || scan.busy || value.trim()) return;
		let text = '';
		try {
			text = String(await navigator.clipboard.readText()).trim();
		} catch {
			return;
		}
		// Only a link DeFaketive can check (Lazada PH) is put in the bar.
		if (!text || text.length > 2000 || text === lastClipboard || !scannable(queryContext(text).platform) || value.trim()) return;
		lastClipboard = text;
		value = text;
		toast('The product link you copied is in the box. Press Check to continue.');
	});

	function submit(event: SubmitEvent) {
		event.preventDefault();
		const query = value.trim();
		// A guest who pastes a product that was already checked gets its report at once: no second screen and
		// no free scan used. (Signed in, the next page also offers to check it again, so it is not skipped.)
		if (!auth.user && queryContext(query).platform) {
			const known = catalog.lookup(query);
			if (known) return goto(guestReportHref(known.link));
		}
		goto(query ? `${target}?q=${encodeURIComponent(query)}` : target);
	}
</script>

<form onsubmit={submit} class="w-full min-w-0">
	<div class="flex flex-col gap-3 sm:flex-row sm:items-center">
		<InputGroup class="h-12 min-w-0 [&_button]:min-h-11 [&_button]:min-w-11">
			<InputGroupAddon><LinkIcon /></InputGroupAddon>
			<InputGroupInput
				bind:value
				name="product-query"
				data-scan-input
				{placeholder}
				autocomplete="off"
				aria-label="Product link"
				aria-describedby={helpId}
				class="min-w-0 text-base md:text-sm"
			/>
			<ClearLinkButton bind:value />
			<InputGroupAddon align="inline-end" class="max-md:hidden"><Kbd title="Press / to jump here">/</Kbd></InputGroupAddon>
		</InputGroup>
		<Button type="submit" {size} class="min-h-12 w-full shrink-0 sm:w-auto">Check <ArrowRightIcon aria-hidden="true" /></Button>
	</div>
	<p id={helpId} class="text-muted-foreground mt-3 text-sm leading-relaxed wrap-anywhere">{note}</p>
</form>
