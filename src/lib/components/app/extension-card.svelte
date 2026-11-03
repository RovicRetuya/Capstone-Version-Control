<script lang="ts">
	import BookOpenIcon from '@lucide/svelte/icons/book-open';
	import DownloadIcon from '@lucide/svelte/icons/download';
	import PuzzleIcon from '@lucide/svelte/icons/puzzle';
	import { onMount } from 'svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { EXTENSION_CONTACT, EXTENSION_DOWNLOAD, extensionFileAvailable } from '#lib/extension-download.js';

	// The short version of the extension guide, with the download, for the pages people land on (Check, Home, About, FAQ).
	// The whole guide is /app/extension (/extension for someone not signed in).
	let { guideHref = '/app/extension', class: className = '' }: { guideHref?: string; class?: string } = $props();

	// null while we look; the card shows the guide either way and offers the file when the site has it.
	let available = $state<boolean | null>(null);
	onMount(async () => {
		available = await extensionFileAvailable();
	});

	const steps = [
		['Download and add it', 'Once, in Chrome, Edge or Brave on a computer. About 2 minutes.'],
		['Open a product', 'On Lazada PH or Shopee PH, in your browser (not the app).'],
		['Press Check with DeFaketive', 'The purple button at the bottom left. Your report opens here.']
	];
</script>

<section class={['bg-card grid gap-4 rounded-xl border p-5', className]} aria-labelledby="extension-card-title">
	<div class="space-y-1">
		<h2 id="extension-card-title" class="flex items-center gap-2 text-lg font-semibold tracking-tight">
			<PuzzleIcon class="size-5" aria-hidden="true" /> Check Lazada and Shopee products with the extension
		</h2>
		<p class="text-muted-foreground text-sm">
			Shopee reviews can only be checked this way, and it is the quickest way to check Lazada too.
		</p>
	</div>
	<ol class="grid gap-3 sm:grid-cols-3">
		{#each steps as [title, text], index (title)}
			<li class="grid grid-cols-[1.5rem_1fr] gap-3">
				<span class="bg-primary text-primary-foreground grid size-6 place-items-center rounded-full text-xs font-medium" aria-hidden="true">{index + 1}</span>
				<div>
					<p class="text-sm font-medium"><span class="sr-only">Step {index + 1}: </span>{title}</p>
					<p class="text-muted-foreground text-sm">{text}</p>
				</div>
			</li>
		{/each}
	</ol>
	<div class="flex flex-wrap items-center gap-2" aria-live="polite">
		{#if available}
			<Button href={EXTENSION_DOWNLOAD} download="defaketive-extension.zip"><DownloadIcon /> Download the extension (.zip)</Button>
		{:else if available === false}
			<Button variant="outline" href={EXTENSION_CONTACT}><DownloadIcon /> Ask the team for the file</Button>
		{/if}
		<Button variant="outline" href={guideHref}><BookOpenIcon /> Read the step-by-step guide</Button>
	</div>
</section>
