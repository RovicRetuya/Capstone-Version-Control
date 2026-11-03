<script lang="ts">
	import ExtensionCard from '#lib/components/app/extension-card.svelte';
	import TeamGrid from '#lib/components/app/team-grid.svelte';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#lib/components/ui/card/index.js';

	const features = [
		['Taglish-aware sentiment', 'A language model trained on Filipino and English reviews sorts each review as positive, negative, or mixed or unclear.'],
		['Separate warnings', 'Safety, fake and defect reports are checked one by one, so good reviews never average away a fire report.'],
		['Lazada PH and Shopee PH', 'Reads public reviews from Lazada PH product pages (up to 60 from each star level) and, with the extension, from Shopee PH product pages (every written review).'],
		['Similar products', 'When reviewers report problems, see similar products whose reviews raised no warnings.']
	];
</script>

<svelte:head><title>About · DeFaketive</title></svelte:head>

<header class="space-y-1">
	<h1 class="text-3xl font-semibold tracking-tight">About DeFaketive</h1>
	<p class="text-muted-foreground max-w-2xl">
		DeFaketive reads customer reviews from Lazada PH and Shopee PH, in English, Filipino or Taglish, and shows you
		what buyers report about fakes, defects and safety problems, in their own words.
	</p>
</header>

<section class="grid grid-cols-1 gap-4 sm:grid-cols-2" aria-label="What it does">
	{#each features as [title, text], index (title)}
		<Card class="reveal gap-1 p-5" style="--i:{index}">
			<h2 class="font-semibold">{title}</h2>
			<p class="text-muted-foreground text-sm">{text}</p>
		</Card>
	{/each}
</section>

<ExtensionCard guideHref="/app/extension" />

<Card>
	<CardHeader>
		<CardTitle>The minds behind a safer shopping experience</CardTitle>
		<CardDescription>Pangasinan State University – Urdaneta City Campus · BS Information Technology · May 2026</CardDescription>
	</CardHeader>
	<CardContent><TeamGrid /></CardContent>
</Card>

<p class="text-muted-foreground max-w-2xl text-sm">
	DeFaketive is a student research project for academic use. Its reports summarize what reviewers wrote; they are not
	proof that a listing or product is authentic, counterfeit or safe.
</p>
