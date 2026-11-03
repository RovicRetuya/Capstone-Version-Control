<script lang="ts">
	import ExtensionCard from '#lib/components/app/extension-card.svelte';
	import FaqList from '#lib/components/app/faq-list.svelte';
	import VerdictBadge from '#lib/components/app/verdict-badge.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#lib/components/ui/card/index.js';
	import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '#lib/components/ui/table/index.js';
	import { groupOfTone, SAFETY_LIFT_NOTE, VERDICT_GUIDE } from '#lib/product.js';
	import { ui } from '#lib/stores/ui.svelte.js';
</script>

<svelte:head><title>FAQ · DeFaketive</title></svelte:head>

<header class="space-y-1">
	<h1 class="text-3xl font-semibold tracking-tight">FAQ &amp; support</h1>
	<p class="text-muted-foreground">Common questions, and how to read a result.</p>
</header>

<Card>
	<CardHeader><CardTitle>Common questions</CardTitle></CardHeader>
	<CardContent><FaqList value="q4" /></CardContent>
</Card>

<ExtensionCard guideHref="/app/extension" />

<Card>
	<CardHeader>
		<CardTitle>How results work</CardTitle>
		<CardDescription>
			Each product gets a plain result from what its reviewers reported. There is no score, and no result says a
			product is safe or unsafe.
		</CardDescription>
	</CardHeader>
	<CardContent>
		<Table>
			<TableHeader>
				<TableRow><TableHead>Result</TableHead><TableHead>Shown as</TableHead><TableHead>What it means</TableHead></TableRow>
			</TableHeader>
			<TableBody>
				{#each VERDICT_GUIDE as row (row.state)}
					<TableRow>
						<TableCell class="font-medium whitespace-normal">{row.label}</TableCell>
						<TableCell><VerdictBadge kind={groupOfTone(row.tone)} /></TableCell>
						<TableCell class="text-muted-foreground whitespace-normal">{row.meaning}</TableCell>
					</TableRow>
				{/each}
			</TableBody>
		</Table>
		<p class="text-muted-foreground mt-3 text-sm">{SAFETY_LIFT_NOTE}</p>
	</CardContent>
</Card>

<div class="flex flex-wrap items-center gap-3">
	<Button variant="outline" onclick={() => ui.openReport()}>Report a problem</Button>
	<p class="text-muted-foreground text-sm">
		Still stuck? Send the team a report, or email
		<a class="text-primary underline underline-offset-4" href="mailto:bmacalino_20ur2047@psu.edu.ph">bmacalino_20ur2047@psu.edu.ph</a>.
	</p>
</div>
