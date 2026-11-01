<script lang="ts">
	import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '#lib/components/ui/accordion/index.js';
	import { accuracyCopy } from '#lib/product.js';
	import { catalog } from '#lib/stores/catalog.svelte.js';

	let { value = $bindable('') }: { value?: string } = $props();

	// The accuracy answer quotes the server's own test figures, so it can't go stale.
	const accuracy = $derived(catalog.browse.find((p) => p.badge_view?.safety_check_accuracy)?.badge_view?.safety_check_accuracy);

	const questions = $derived([
		{
			q: 'Is DeFaketive free to use?',
			a: 'Yes. Guests get 3 new scans a day, and a free account gives unlimited scans.'
		},
		{
			q: 'How does DeFaketive decide on a warning?',
			a: 'It checks reviews for safety, fake and defect reports separately. A warning appears when enough reviewers report the same problem, and a single safety report is always shown. Every warning quotes the reviews behind it.'
		},
		{ q: 'Which platforms are supported?', a: 'Lazada PH and Shopee PH. Paste the link of a Lazada PH product page. For Shopee PH, open the product on Shopee and press Check with DeFaketive, the button the DeFaketive extension adds.' },
		{
			q: 'Can it detect Taglish reviews?',
			a: 'Yes. The sentiment model was trained on Filipino and English reviews, and the warning word lists include Taglish terms like peke, sira and umusok.'
		},
		{
			q: 'What happens if reviewers report a problem?',
			a: "You'll see a warning with the reviewers' own words highlighted. Read them, then compare similar products with no warnings before you buy."
		},
		{
			q: 'How accurate is the check?',
			a: `${accuracyCopy(accuracy)} That is why every report quotes the reviews themselves. Use it as decision support, not proof.`
		}
	]);
</script>

<Accordion type="single" bind:value class="w-full">
	{#each questions as item, index (item.q)}
		<AccordionItem value="q{index}">
			<AccordionTrigger>{item.q}</AccordionTrigger>
			<AccordionContent class="text-muted-foreground">{item.a}</AccordionContent>
		</AccordionItem>
	{/each}
</Accordion>
