<script lang="ts">
	import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
	import CheckIcon from '@lucide/svelte/icons/check';
	import CopyIcon from '@lucide/svelte/icons/copy';
	import DownloadIcon from '@lucide/svelte/icons/download';
	import PuzzleIcon from '@lucide/svelte/icons/puzzle';
	import SmartphoneIcon from '@lucide/svelte/icons/smartphone';
	import XIcon from '@lucide/svelte/icons/x';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { Alert, AlertDescription, AlertTitle } from '#lib/components/ui/alert/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card, CardContent, CardHeader, CardTitle } from '#lib/components/ui/card/index.js';
	import { LAZADA_REVIEWS_PER_STAR } from '#lib/product.js';
	import { auth } from '#lib/stores/auth.svelte.js';

	// What the browser extension is and how to put it in Chrome or Edge. The same page sits on the public site
	// (/extension) and in the app (/app/extension). Until the extension is in the Chrome Web Store it is installed
	// from a .zip, which is offered only when the site has one (scripts/build-extension.mjs --download).
	const DOWNLOAD = '/downloads/defaketive-extension.zip';
	const CONTACT = 'mailto:bmacalino_20ur2047@psu.edu.ph?subject=DeFaketive%20extension';

	// null while we look; a missing file comes back as the app's own page (text/html), not as a .zip.
	let download = $state<boolean | null>(null);
	onMount(async () => {
		try {
			const response = await fetch(DOWNLOAD, { method: 'HEAD', cache: 'no-store' });
			download = response.ok && !(response.headers.get('content-type') ?? '').includes('text/html');
		} catch {
			download = false;
		}
	});

	const pasteHref = $derived(auth.user ? '/app/analyze' : '/scan');

	async function copy(text: string) {
		try {
			await navigator.clipboard.writeText(text);
			toast(`Copied ${text}. Paste it into the address bar.`);
		} catch {
			toast(`Type ${text} into the address bar.`);
		}
	}

	const reads = [
		"The product's name, price, seller and photo",
		'How many ratings it has at each star level',
		`Up to ${LAZADA_REVIEWS_PER_STAR} written reviews from each star level`
	];
	const never = [
		"Reviewers' names, or sellers' replies",
		'Your Lazada login, cart or orders',
		'Any other website, or your browsing history'
	];
</script>

<header class="space-y-3">
	<p class="text-muted-foreground flex items-center gap-2 text-sm font-medium">
		<PuzzleIcon class="size-4" aria-hidden="true" /> For Chrome and Edge on a computer
	</p>
	<h1 class="text-3xl font-semibold tracking-tight text-balance md:text-4xl">Check right on Lazada and Shopee</h1>
	<p class="text-muted-foreground max-w-2xl text-lg">
		The DeFaketive extension adds a <b class="text-foreground font-medium">Check with DeFaketive</b> button to Lazada PH
		and Shopee PH product pages. Press it and your report opens here. No copying links.
	</p>
</header>

<!-- A phone cannot add extensions: say so before the steps, which are no use there. -->
<Alert class="sm:hidden">
	<SmartphoneIcon />
	<AlertTitle>On a phone?</AlertTitle>
	<AlertDescription>Phone browsers can't add extensions. Paste a product link instead.</AlertDescription>
	<div class="col-start-2 mt-2"><Button size="sm" href={pasteHref}>Paste a link</Button></div>
</Alert>

<div class="flex flex-wrap items-center gap-3" aria-live="polite">
	{#if download}
		<Button size="lg" href={DOWNLOAD} download="defaketive-extension.zip"><DownloadIcon /> Download the extension (.zip)</Button>
	{/if}
	<Button size="lg" variant="outline" href={pasteHref}>Paste a link instead</Button>
</div>
{#if download === false}
	<Alert>
		<PuzzleIcon />
		<AlertTitle>Not in the Chrome Web Store yet</AlertTitle>
		<AlertDescription>
			While the extension is being tested, the team shares the file directly.
			<a class="tap text-primary font-medium underline underline-offset-4" href={CONTACT}>Ask us for it</a>, then follow the steps below.
		</AlertDescription>
	</Alert>
{/if}

<Card>
	<CardHeader><CardTitle>Install it (2 minutes)</CardTitle></CardHeader>
	<CardContent>
		<ol class="grid gap-5">
			<li class="grid grid-cols-[1.75rem_1fr] gap-3">
				<span class="bg-primary text-primary-foreground grid size-7 place-items-center rounded-full text-sm font-medium" aria-hidden="true">1</span>
				<div class="space-y-1">
					<p class="font-medium">Unzip the file</p>
					<p class="text-muted-foreground text-sm">You get a folder with a file called <code class="bg-muted rounded px-1">manifest.json</code> inside.</p>
				</div>
			</li>
			<li class="grid grid-cols-[1.75rem_1fr] gap-3">
				<span class="bg-primary text-primary-foreground grid size-7 place-items-center rounded-full text-sm font-medium" aria-hidden="true">2</span>
				<div class="space-y-2">
					<p class="font-medium">Open your browser's extensions page and switch on Developer mode</p>
					<p class="text-muted-foreground text-sm">Type this into the address bar (links can't open it). Developer mode is a switch at the top right.</p>
					<div class="flex flex-wrap gap-2">
						<Button size="sm" variant="outline" class="font-mono" onclick={() => copy('chrome://extensions')}><CopyIcon /> chrome://extensions</Button>
						<Button size="sm" variant="outline" class="font-mono" onclick={() => copy('edge://extensions')}><CopyIcon /> edge://extensions</Button>
					</div>
				</div>
			</li>
			<li class="grid grid-cols-[1.75rem_1fr] gap-3">
				<span class="bg-primary text-primary-foreground grid size-7 place-items-center rounded-full text-sm font-medium" aria-hidden="true">3</span>
				<div class="space-y-1">
					<p class="font-medium">Press Load unpacked and choose the folder</p>
					<p class="text-muted-foreground text-sm">Pick the folder with <code class="bg-muted rounded px-1">manifest.json</code> in it. DeFaketive appears in your list of extensions.</p>
				</div>
			</li>
			<li class="grid grid-cols-[1.75rem_1fr] gap-3">
				<span class="bg-primary text-primary-foreground grid size-7 place-items-center rounded-full text-sm font-medium" aria-hidden="true">4</span>
				<div class="space-y-1">
					<p class="font-medium">Open a Lazada PH or Shopee PH product and press Check with DeFaketive</p>
					<p class="text-muted-foreground text-sm">
						The button is at the bottom left of the page. Your report opens in DeFaketive; checking with the extension
						needs a free account.
					</p>
				</div>
			</li>
		</ol>
	</CardContent>
</Card>

<div class="grid grid-cols-1 gap-4 md:grid-cols-2">
	<Card>
		<CardHeader><CardTitle>What it reads</CardTitle></CardHeader>
		<CardContent>
			<ul class="grid gap-2 text-sm">
				{#each reads as item (item)}
					<li class="flex items-start gap-2"><CheckIcon class="mt-0.5 size-4 shrink-0" aria-hidden="true" /> {item}</li>
				{/each}
			</ul>
		</CardContent>
	</Card>
	<Card>
		<CardHeader><CardTitle>What it never reads</CardTitle></CardHeader>
		<CardContent>
			<ul class="grid gap-2 text-sm">
				{#each never as item (item)}
					<li class="flex items-start gap-2"><XIcon class="text-muted-foreground mt-0.5 size-4 shrink-0" aria-hidden="true" /> {item}</li>
				{/each}
			</ul>
		</CardContent>
	</Card>
</div>

<section class="space-y-2" aria-labelledby="extension-notes">
	<h2 id="extension-notes" class="text-lg font-semibold tracking-tight">Good to know</h2>
	<ul class="text-muted-foreground grid max-w-3xl list-disc gap-1.5 pl-5 text-sm">
		<li>Keep the product tab open while the button collects the reviews. It tells you when your report is opening.</li>
		<li>If Lazada or Shopee shows a "slide to verify" or login check, that is the marketplace asking you. Do it as you normally would, then press the button again.</li>
		<li>Shopee reviews can only be checked with the extension: pasting a Shopee link into Check a product points you here.</li>
		<li>On a phone, or in another browser, paste a Lazada product link into <a class="tap text-primary font-medium underline underline-offset-4" href={pasteHref}>Check a product</a> instead.</li>
		<li>DeFaketive is a student research project, not part of Lazada or Shopee.</li>
	</ul>
</section>

<p class="text-muted-foreground text-sm">
	<a class="tap text-primary inline-flex items-center gap-1 font-medium underline underline-offset-4" href={pasteHref}>
		Or check a product by pasting its link <ArrowRightIcon class="size-4" />
	</a>
</p>
