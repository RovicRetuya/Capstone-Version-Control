<script lang="ts">
	import CircleAlertIcon from '@lucide/svelte/icons/circle-alert';
	import CircleCheckIcon from '@lucide/svelte/icons/circle-check';
	import CircleHelpIcon from '@lucide/svelte/icons/circle-help';
	import TriangleAlertIcon from '@lucide/svelte/icons/triangle-alert';
	import { chipFor, view } from '#lib/product.js';
	import type { Product } from '#lib/types.js';
	import { cn } from '#lib/utils.js';

	// The verdict is the biggest thing on a report. It says what reviewers REPORT, never that a product is safe or unsafe.
	// It arrives in steps: the box settles in and takes its colour, then the icon, the headline and the detail follow.
	let { product }: { product: Product } = $props();

	const verdict = $derived(view(product));
	const chip = $derived(chipFor(product));
</script>

<!-- Keyed on the product, so opening another report plays the reveal again. -->
{#key product.link}
	<div class={cn('verdict-box tone-' + chip.kind, 'text-foreground grid min-w-0 gap-3 rounded-xl border-2 border-(--tone)/60 bg-(--tone-soft) p-4 [overflow-wrap:anywhere] sm:p-5 md:p-6')} role="group" aria-label="Result">
		<div class="verdict-step flex flex-wrap items-center gap-2 text-sm font-medium" style="--d: 0.2s">
			<span class="relative grid size-5 place-items-center">
				{#if chip.kind === 'safety'}
					<span class="verdict-ring absolute inset-0 rounded-full bg-(--tone)/30" aria-hidden="true"></span>
				{/if}
				<span class="pop relative text-(--tone)" style="animation-delay: 0.2s">
					{#if chip.kind === 'safety'}<TriangleAlertIcon class="size-5" />
					{:else if chip.kind === 'caution'}<CircleAlertIcon class="size-5" />
					{:else if chip.kind === 'clear'}<CircleCheckIcon class="size-5" />
					{:else}<CircleHelpIcon class="size-5" />{/if}
				</span>
			</span>
			<span>{chip.label}</span>
			<!-- On a phone this would drop onto a line of its own; there the headline and the "guide, not proof" line say it. -->
			<span class="text-muted-foreground font-normal max-sm:sr-only">· What reviewers report</span>
		</div>
		<h2 class="verdict-step text-foreground text-2xl leading-tight font-semibold tracking-tight md:text-3xl" style="--d: 0.32s">{verdict.headline}</h2>
		{#if verdict.detail}<p class="verdict-step text-foreground/80 text-base" style="--d: 0.44s">{verdict.detail}</p>{/if}
		<p class="verdict-step text-muted-foreground text-sm" style="--d: 0.56s">Review signals are a guide, not proof.</p>
	</div>
{/key}
