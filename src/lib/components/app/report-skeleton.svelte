<script lang="ts">
	import { Card } from '#lib/components/ui/card/index.js';
	import { Skeleton } from '#lib/components/ui/skeleton/index.js';

	// A report-shaped placeholder: a small photo and the name, the big verdict box, the numbers, tabs, then two cards.
</script>

<div class="grid gap-6" role="status" aria-label="Loading product report">
	<Card class="gap-0 overflow-hidden py-0">
		<div class="grid gap-4 p-5 md:p-6">
			<div class="grid grid-cols-[4.5rem_1fr] items-start gap-x-4 sm:grid-cols-[7rem_1fr] sm:gap-x-5">
				<Skeleton class="aspect-square w-full rounded-xl" />
				<div class="grid content-start gap-3">
					<Skeleton class="h-6 w-full max-w-lg" />
					<Skeleton class="h-6 w-2/3 max-w-sm" />
					<Skeleton class="h-4 w-48 max-w-full" />
				</div>
			</div>
			<div class="grid gap-3 rounded-xl border-2 border-dashed p-5 md:p-6">
				<Skeleton class="h-4 w-40" />
				<Skeleton class="h-8 w-3/4 max-w-md" />
				<Skeleton class="h-4 w-full max-w-xl" />
			</div>
			<Skeleton class="h-9 w-56 max-w-full" />
		</div>
		<div class="border-t p-5 md:p-6">
			<div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
				{#each [1, 2, 3, 4] as n (n)}<div class="space-y-1.5"><Skeleton class="h-3 w-16" /><Skeleton class="h-4 w-24" /></div>{/each}
			</div>
		</div>
	</Card>
	<div class="flex gap-2"><Skeleton class="h-9 w-24" /><Skeleton class="h-9 w-36" /><Skeleton class="h-9 w-40" /></div>
	<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
		<Card class="gap-4 p-6">
			<Skeleton class="h-5 w-40" />
			<div class="flex items-center gap-6"><Skeleton class="size-36 rounded-full" /><div class="flex-1 space-y-3"><Skeleton class="h-4 w-full" /><Skeleton class="h-4 w-full" /><Skeleton class="h-4 w-full" /></div></div>
		</Card>
		<Card class="gap-4 p-6"><Skeleton class="h-5 w-52" /><Skeleton class="h-3 w-full" /><Skeleton class="h-3 w-4/5" /><Skeleton class="h-14 w-full" /></Card>
	</div>
</div>
