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
	import { Tabs, TabsContent, TabsList, TabsTrigger } from '#lib/components/ui/tabs/index.js';
	import { EXTENSION_CONTACT, EXTENSION_DOWNLOAD, extensionFileAvailable } from '#lib/extension-download.js';
	import { LAZADA_REVIEWS_PER_STAR } from '#lib/product.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { ui } from '#lib/stores/ui.svelte.js';

	// What the browser extension is, how to put it in Chrome or Edge, and how to check a Lazada or a Shopee product with
	// it, written for someone who has never added an extension. The same page sits on the public site (/extension) and
	// in the app (/app/extension). Until the extension is in the Chrome Web Store it is installed from a .zip, which
	// is offered only when the site has one (scripts/build-extension.mjs --download; deploy/setup-server.sh does it).
	const DOWNLOAD = EXTENSION_DOWNLOAD;
	const CONTACT = EXTENSION_CONTACT;

	// null while we look; shared with every page that offers the download.
	let download = $state<boolean | null>(null);
	onMount(async () => {
		download = await extensionFileAvailable();
	});

	const pasteHref = $derived(auth.user ? '/app/analyze' : '/scan');
	const accountHref = $derived(auth.user ? '/app/home' : '/enter');

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
		`Lazada: up to ${LAZADA_REVIEWS_PER_STAR} written reviews from each star level`,
		'Shopee: every written review, so a popular product takes a few minutes'
	];
	const never = [
		"Reviewers' names, or sellers' replies",
		'Your Lazada or Shopee login, cart or orders',
		'Any other website, or your browsing history'
	];

	// Things that go wrong, and what to do. Written as the person would say it.
	const problems: [string, string][] = [
		[
			"I don't see the Check with DeFaketive button",
			'Reload the product page. The button sits at the bottom left, and it only appears on a product page (the address has /products/ on Lazada, or a number at the end on Shopee), not on a search or home page. If it still is not there, open the extensions page, find DeFaketive and make sure its switch is on.'
		],
		[
			'It says the reviews "didn\'t add up", or nothing was checked',
			'Reload the product page and press Check again. This happens when the page changed while the reviews were being read, so keep the product tab open and do not scroll away or close it until your report opens.'
		],
		[
			'Lazada or Shopee shows "slide to verify" or asks me to log in',
			'That is the shop asking you, not DeFaketive. Do the check as you normally would, then press Check with DeFaketive again.'
		],
		[
			'It is taking a long time on Shopee',
			'A popular Shopee product can have thousands of written reviews and the extension reads all of them. The small box on the product page counts them as it goes. Leave the tab open.'
		],
		[
			'My report says it was already checked',
			'A product checked in the last 30 days opens its saved report instead of reading the reviews again. That keeps every report trustworthy, and the page tells you how old the report is.'
		],
		[
			'The extension does not open DeFaketive, or says I need to sign in',
			'Checking with the extension needs a free DeFaketive account. Sign in on this site in the same browser, then press the button again.'
		],
		[
			'A newer version came out',
			'Download the new .zip, unzip it over the old folder (replace the files), then open the extensions page and press the refresh arrow on the DeFaketive card.'
		]
	];
</script>

<header class="space-y-3">
	<p class="text-muted-foreground flex items-center gap-2 text-sm font-medium">
		<PuzzleIcon class="size-4" aria-hidden="true" /> For Chrome, Edge or Brave on a computer
	</p>
	<h1 class="text-3xl font-semibold tracking-tight text-balance md:text-4xl">How to check a Lazada or Shopee product</h1>
	<p class="text-muted-foreground max-w-2xl text-lg">
		The DeFaketive extension adds a <b class="text-foreground font-medium">Check with DeFaketive</b> button to Lazada PH
		and Shopee PH product pages. Press it and your report opens here. No copying links.
	</p>
</header>

<!-- A phone cannot add extensions: say so before the steps, which are no use there. -->
<Alert>
	<SmartphoneIcon />
	<AlertTitle>On a phone?</AlertTitle>
	<AlertDescription>
		Phone browsers can't add extensions, so the steps below need a computer. On a phone you can still open any
		product that has already been checked: paste its link, or the text you get from the Lazada app's Share button, into
		Check a product.
	</AlertDescription>
	<div class="col-start-2 mt-2"><Button size="sm" href={pasteHref}>Open Check a product</Button></div>
</Alert>

<div class="flex flex-wrap items-center gap-3" aria-live="polite">
	{#if !auth.user}
		<Button size="lg" onclick={() => ui.openAuth('signin')}><DownloadIcon /> Sign in to download the extension</Button>
	{:else if download}
		<Button size="lg" href={DOWNLOAD} download="defaketive-extension.zip"><DownloadIcon /> Download the extension (.zip)</Button>
	{/if}
	<Button size="lg" variant="outline" href={pasteHref}>Paste a link instead</Button>
</div>
{#if !auth.user}
	<p class="text-muted-foreground max-w-2xl text-sm">
		The extension, including the Shopee scraper, is free with an account. Sign in or create one to download it.
		<button type="button" class="tap text-primary font-medium underline underline-offset-4" onclick={() => ui.openAuth('signup')}>Create a free account</button>
	</p>
{:else if download === false}
	<Alert>
		<PuzzleIcon />
		<AlertTitle>Not in the Chrome Web Store yet</AlertTitle>
		<AlertDescription>
			While the extension is being tested, the team shares the file directly.
			<a class="tap text-primary font-medium underline underline-offset-4" href={CONTACT}>Ask us for it</a>, then follow the steps below.
		</AlertDescription>
	</Alert>
{/if}

{#snippet step(n: number, title: string, text: string)}
	<li class="grid grid-cols-[1.75rem_1fr] gap-3">
		<span class="bg-primary text-primary-foreground grid size-7 place-items-center rounded-full text-sm font-medium" aria-hidden="true">{n}</span>
		<div class="space-y-1">
			<p class="font-medium"><span class="sr-only">Step {n}: </span>{title}</p>
			<p class="text-muted-foreground text-sm">{text}</p>
		</div>
	</li>
{/snippet}

<Card>
	<CardHeader><CardTitle>Before you start</CardTitle></CardHeader>
	<CardContent>
		<ul class="grid gap-2 text-sm">
			<li class="flex items-start gap-2"><CheckIcon class="mt-0.5 size-4 shrink-0" aria-hidden="true" /> A computer with Google Chrome, Microsoft Edge or Brave.</li>
			<li class="flex items-start gap-2">
				<CheckIcon class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
				<span>A free DeFaketive account, signed in on this site in the same browser. <a class="tap text-primary font-medium underline underline-offset-4" href={accountHref}>{auth.user ? 'Open DeFaketive' : 'Sign in or make one'}</a>.</span>
			</li>
			<li class="flex items-start gap-2"><CheckIcon class="mt-0.5 size-4 shrink-0" aria-hidden="true" /> You do not need to log in to Lazada or Shopee. Use them as you normally do.</li>
		</ul>
	</CardContent>
</Card>

<Card>
	<CardHeader><CardTitle>Part 1. Install it (2 minutes, once)</CardTitle></CardHeader>
	<CardContent>
		<ol class="grid gap-5">
			{@render step(1, 'Download the extension', 'Sign in, then press "Download the extension (.zip)" above. A file called defaketive-extension.zip lands in your Downloads folder.')}
			{@render step(2, 'Unzip it', 'Right-click the file and choose Extract All (on a Mac, double-click it). You get a folder with a file called manifest.json inside. Keep that folder somewhere you will not delete it: the browser reads the extension from it every time.')}
			<li class="grid grid-cols-[1.75rem_1fr] gap-3">
				<span class="bg-primary text-primary-foreground grid size-7 place-items-center rounded-full text-sm font-medium" aria-hidden="true">3</span>
				<div class="space-y-2">
					<p class="font-medium"><span class="sr-only">Step 3: </span>Open your browser's extensions page</p>
					<p class="text-muted-foreground text-sm">Press the button for your browser to copy the address, then paste it into the address bar at the top and press Enter. (A link can't open this page for you.)</p>
					<div class="flex flex-wrap gap-2">
						<Button size="sm" variant="outline" class="font-mono" onclick={() => copy('chrome://extensions')}><CopyIcon /> chrome://extensions</Button>
						<Button size="sm" variant="outline" class="font-mono" onclick={() => copy('edge://extensions')}><CopyIcon /> edge://extensions</Button>
						<Button size="sm" variant="outline" class="font-mono" onclick={() => copy('brave://extensions')}><CopyIcon /> brave://extensions</Button>
					</div>
				</div>
			</li>
			{@render step(4, 'Switch on Developer mode', 'It is a switch at the top right of that page (in Edge, at the bottom left). It only lets you add an extension from a folder.')}
			{@render step(5, 'Press Load unpacked and choose the folder', 'Pick the folder you unzipped, the one with manifest.json in it. DeFaketive appears in your list of extensions.')}
			{@render step(6, 'Pin it (optional)', 'Click the puzzle-piece icon next to the address bar and the pin beside DeFaketive, so its icon stays in view.')}
		</ol>
	</CardContent>
</Card>

<Card>
	<CardHeader><CardTitle>Part 2. Check a product</CardTitle></CardHeader>
	<CardContent>
		<Tabs value="lazada" class="gap-5">
			<TabsList>
				<TabsTrigger value="lazada">Lazada PH</TabsTrigger>
				<TabsTrigger value="shopee">Shopee PH</TabsTrigger>
			</TabsList>
			<TabsContent value="lazada">
				<ol class="grid gap-5">
					{@render step(1, 'Open the product on Lazada in your browser', 'Go to lazada.com.ph and open the product you are thinking of buying. Use the website, not the Lazada app.')}
					{@render step(2, 'Wait for the page to finish loading', 'Let the photos and the price show up first.')}
					{@render step(3, 'Press Check with DeFaketive', `It is a purple button at the bottom left of the page. The extension reads the product and up to ${LAZADA_REVIEWS_PER_STAR} written reviews from each star level. A small box tells you how far it is. This takes about a minute.`)}
					{@render step(4, 'Keep the Lazada tab open', 'Do not close it or scroll to a different product until the box says your report is opening.')}
					{@render step(5, 'Read your report', 'A new DeFaketive tab opens with the result, the checks behind it and the reviews that raised them. Use Save to keep it in your Wishlist.')}
				</ol>
			</TabsContent>
			<TabsContent value="shopee">
				<ol class="grid gap-5">
					{@render step(1, 'Open the product on Shopee in your browser', 'Go to shopee.ph and open the product. Use the website, not the Shopee app. (Shopee products can only be checked with the extension.)')}
					{@render step(2, 'Wait for the page to finish loading', 'Let the photos, the price and the ratings show up first.')}
					{@render step(3, 'Press Check with DeFaketive', 'It is a purple button at the bottom left of the page. Shopee has no limit per star level, so the extension reads every written review. A popular product can take several minutes, and a small box counts the reviews as it goes.')}
					{@render step(4, 'Keep the Shopee tab open', 'Do not close it until the box says your report is opening. If Shopee asks you to slide to verify or log in, do it, then press the button again.')}
					{@render step(5, 'Read your report', 'A new DeFaketive tab opens with the result and the reviews behind it. The box on the product page tells you how many reviews were read, and how many were skipped (for example reviews with no text).')}
				</ol>
			</TabsContent>
		</Tabs>
	</CardContent>
</Card>

<section class="space-y-3" aria-labelledby="extension-problems">
	<h2 id="extension-problems" class="text-lg font-semibold tracking-tight">If something goes wrong</h2>
	<div class="grid max-w-3xl gap-2">
		{#each problems as [question, answer] (question)}
			<details class="bg-card rounded-lg border px-4 py-3 text-sm">
				<summary class="cursor-pointer font-medium">{question}</summary>
				<p class="text-muted-foreground mt-2">{answer}</p>
			</details>
		{/each}
	</div>
</section>

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

<p class="text-muted-foreground max-w-3xl text-sm">
	DeFaketive is a student research project, not part of Lazada or Shopee. Results are based on a sample of public reviews.
</p>

<p class="text-muted-foreground text-sm">
	<a class="tap text-primary inline-flex items-center gap-1 font-medium underline underline-offset-4" href={pasteHref}>
		Or check a product by pasting its link <ArrowRightIcon class="size-4" />
	</a>
</p>
