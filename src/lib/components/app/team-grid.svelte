<script lang="ts">
	import { Avatar, AvatarFallback } from '#lib/components/ui/avatar/index.js';
	import { initials } from '#lib/product.js';

	const team = [
		{ name: 'Kathleen D. De Guzman, MIT', role: 'Faculty Adviser' },
		{ name: 'Mark Rhean E. Caballero', role: 'Capstone Leader' },
		{ name: 'Ryan Rovic Retuya', role: 'UI / UX' },
		{ name: 'Princethom A. Guyo', role: 'Quality Assurance' },
		{ name: 'Brian P. Macalino', role: 'Programmer' }
	];
</script>

<ul class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
	{#each team as person (person.name)}
		<li class="flex items-center gap-3 rounded-xl border p-4">
			<Avatar class="size-10"><AvatarFallback>{initials(person.name.replace(/,.*/, ''))}</AvatarFallback></Avatar>
			<div class="min-w-0">
				<p class="truncate font-medium">{person.name}</p>
				<p class="text-muted-foreground text-sm">{person.role}</p>
			</div>
		</li>
	{/each}
</ul>
