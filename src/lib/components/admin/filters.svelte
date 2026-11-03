<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { json } from '#lib/api.js';
	import EmptyState from '#lib/components/app/empty-state.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#lib/components/ui/card/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import { RadioGroup, RadioGroupItem } from '#lib/components/ui/radio-group/index.js';
	import { Skeleton } from '#lib/components/ui/skeleton/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { adminApi } from '#lib/stores/admin.svelte.js';
	import { SHOW_CHOICES, SHOW_LABEL, SORT_CHOICES, SORT_LABEL, type FilterChoices } from '#lib/product-filters.js';
	import type { AdminFilters } from '#lib/admin-types.js';

	// What the Products page offers visitors: which choices appear in its two lists, and which one is picked first.
	// The server keeps it (admin_api.py) and everybody reads it, so a change shows on the next visit to the page.
	type Group = 'show' | 'sort';
	const GROUPS: { id: Group; title: string; help: string; choices: [string, string][] }[] = [
		{ id: 'show', title: SHOW_LABEL, help: 'Which results visitors can narrow the list to.', choices: SHOW_CHOICES },
		{ id: 'sort', title: SORT_LABEL, help: 'Which orders visitors can sort the list by.', choices: SORT_CHOICES }
	];

	let answer = $state<AdminFilters | null>(null);
	let failed = $state('');
	let draft = $state<FilterChoices | null>(null);
	let saving = $state(false);

	const copy = (value: FilterChoices): FilterChoices => JSON.parse(JSON.stringify(value));
	async function load() {
		failed = '';
		try {
			show(await adminApi<AdminFilters>('/api/admin/filters'));
		} catch (error) {
			failed = (error as Error).message;
		}
	}
	function show(next: AdminFilters) {
		answer = next;
		draft = copy(next.filters);
	}
	load();

	const isOn = (group: Group, key: string) => (draft![group].enabled as string[]).includes(key);
	function toggle(group: Group, key: string, on: boolean) {
		if (!draft) return;
		const known = GROUPS.find((g) => g.id === group)!.choices.map(([k]) => k);
		const next = known.filter((k) => (k === key ? on : isOn(group, k)));
		(draft[group].enabled as string[]) = next;
		// The choice that is picked first must stay on: if it was just turned off, start on the first one left.
		if (!next.includes(draft[group].default as string)) (draft[group].default as string) = next[0] ?? '';
	}
	const problem = (group: Group) => (draft && !draft[group].enabled.length ? 'Keep at least one choice on.' : '');
	const valid = $derived(draft !== null && !problem('show') && !problem('sort'));
	const changed = $derived(answer !== null && draft !== null && JSON.stringify(draft) !== JSON.stringify(answer.filters));
	const atDefaults = $derived(answer !== null && draft !== null && JSON.stringify(draft) === JSON.stringify(answer.defaults));

	async function save(event: SubmitEvent) {
		event.preventDefault();
		if (!valid || !changed || !draft) return;
		saving = true;
		try {
			show(await adminApi<AdminFilters>('/api/admin/filters', json('PUT', draft)));
			toast.success('Saved. The Products page shows these choices from now on.');
		} catch (error) {
			toast.error((error as Error).message);
		} finally {
			saving = false;
		}
	}
	function useAll() {
		if (answer) draft = copy(answer.defaults);
	}
</script>

{#if failed && !answer}
	<EmptyState art="error" title="The Products page choices couldn't be loaded" description={failed}>
		{#snippet actions()}<Button onclick={load}>Try again</Button>{/snippet}
	</EmptyState>
{:else if !answer || !draft}
	<Skeleton class="h-96 w-full max-w-2xl" />
{:else}
	<form onsubmit={save} novalidate class="grid max-w-2xl gap-6">
		{#each GROUPS as group (group.id)}
			{@const error = problem(group.id)}
			<Card>
				<CardHeader>
					<CardTitle>{group.title}</CardTitle>
					<CardDescription>{group.help} Tick the choices to offer, and pick the one the page starts on.</CardDescription>
				</CardHeader>
				<CardContent>
					<RadioGroup bind:value={draft[group.id].default as string} class="grid gap-3" aria-label="{group.title}: the choice the page starts on">
						<div class="text-muted-foreground grid grid-cols-[1fr_auto] gap-x-6 text-xs font-medium tracking-wide uppercase" aria-hidden="true">
							<span>Offer this choice</span><span>Starts on</span>
						</div>
						{#each group.choices as [key, text] (key)}
							<div class="grid grid-cols-[1fr_auto] items-center gap-x-6">
								<div class="flex items-center gap-3">
									<Checkbox id="{group.id}-{key}" checked={isOn(group.id, key)} onCheckedChange={(on) => toggle(group.id, key, on === true)} />
									<Label for="{group.id}-{key}" class="font-normal">{text}</Label>
								</div>
								<RadioGroupItem value={key} id="{group.id}-start-{key}" disabled={!isOn(group.id, key)} aria-label="{text}: start on this choice" />
							</div>
						{/each}
					</RadioGroup>
					{#if error}<p class="text-destructive mt-3 text-sm" role="alert">{error}</p>{/if}
					{#if draft[group.id].enabled.length === 1}
						<p class="text-muted-foreground mt-3 text-sm">With one choice left, visitors don't see this list at all.</p>
					{/if}
				</CardContent>
			</Card>
		{/each}
		<div class="flex flex-wrap gap-2">
			<Button type="submit" disabled={saving || !changed || !valid}>{#if saving}<Spinner />{/if} Save choices</Button>
			<Button type="button" variant="outline" disabled={saving || atDefaults} onclick={useAll}>Offer every choice</Button>
		</div>
	</form>
{/if}
