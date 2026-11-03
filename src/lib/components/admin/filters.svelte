<script lang="ts">
	import PlusIcon from '@lucide/svelte/icons/plus';
	import { toast } from 'svelte-sonner';
	import { json } from '#lib/api.js';
	import EmptyState from '#lib/components/app/empty-state.svelte';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#lib/components/ui/card/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import { RadioGroup, RadioGroupItem } from '#lib/components/ui/radio-group/index.js';
	import * as Select from '#lib/components/ui/select/index.js';
	import { Skeleton } from '#lib/components/ui/skeleton/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { adminApi } from '#lib/stores/admin.svelte.js';
	import {
		FILTER_KIND_ORDER,
		FILTER_KINDS,
		LABEL_MAX,
		MARKETPLACE_CHOICES,
		MAX_CUSTOM,
		ORDER_FIELD_ORDER,
		ORDER_FIELDS,
		SHOW_CHOICES,
		SHOW_LABEL,
		SORT_CHOICES,
		SORT_LABEL,
		suggestedLabel,
		type CustomChoice,
		type Direction,
		type FilterChoices,
		type FilterKind,
		type OrderField
	} from '#lib/product-filters.js';
	import type { AdminFilters } from '#lib/admin-types.js';

	// What the Products page offers visitors: which choices appear in its two lists, which one is picked first, and the
	// options the admin makes up. The server keeps it (admin_api.py) and everybody reads it, so a change shows on the next
	// visit to the page.
	type Group = 'show' | 'sort';
	const GROUPS: { id: Group; title: string; help: string; builtIn: [string, string][]; adding: string }[] = [
		{
			id: 'show',
			title: SHOW_LABEL,
			help: 'Which results visitors can narrow the list to.',
			builtIn: SHOW_CHOICES,
			adding: 'a filter, such as a minimum rating, a top price, a number of reviews or a marketplace'
		},
		{
			id: 'sort',
			title: SORT_LABEL,
			help: 'Which orders visitors can sort the list by.',
			builtIn: SORT_CHOICES,
			adding: 'an order, such as by rating, price, reviews, date or name'
		}
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
		draft = copy({ ...next.filters, custom: next.filters.custom ?? [] });
	}
	load();

	// Every choice in a list: the built-in ones, then the ones the admin added.
	const rowsOf = (group: Group): { key: string; text: string; made?: CustomChoice }[] => {
		const built = (GROUPS.find((g) => g.id === group)?.builtIn ?? []).map(([key, text]) => ({ key, text }));
		const made = (draft?.custom ?? []).filter((c) => c.group === group).map((c) => ({ key: c.id, text: c.label, made: c }));
		return [...built, ...made];
	};
	const isOn = (group: Group, key: string) => (draft![group].enabled as string[]).includes(key);
	function setEnabled(group: Group, next: string[]) {
		if (!draft) return;
		(draft[group].enabled as string[]) = next;
		// The choice that is picked first must stay on: if it was just turned off, start on the first one left.
		if (!next.includes(draft[group].default as string)) (draft[group].default as string) = next[0] ?? '';
	}
	function toggle(group: Group, key: string, on: boolean) {
		setEnabled(group, rowsOf(group).map((row) => row.key).filter((k) => (k === key ? on : isOn(group, k))));
	}
	const problem = (group: Group) => (draft && !draft[group].enabled.length ? 'Keep at least one choice on.' : '');
	const valid = $derived(draft !== null && !problem('show') && !problem('sort'));
	const changed = $derived(answer !== null && draft !== null && JSON.stringify(draft) !== JSON.stringify(answer.filters));
	const atDefaults = $derived(answer !== null && draft !== null && JSON.stringify(draft) === JSON.stringify(answer.defaults));

	// --- Adding and editing an option of the admin's own --------------------------------------------------------------
	interface Form {
		group: Group;
		/** The option being edited, or null for a new one. */
		editing: string | null;
		kind: FilterKind | OrderField;
		value: string;
		direction: Direction;
		label: string;
		/** True once the admin typed a name, so a change of kind or number no longer rewrites it. */
		named: boolean;
		error: string;
	}
	let form = $state<Form | null>(null);

	function startForm(group: Group, existing?: CustomChoice) {
		if (existing) {
			const direction = existing.direction ?? 'desc';
			// A name that is still the automatic one keeps following the number; one the admin wrote stays.
			const automatic = suggestedLabel(group, existing.kind, existing.value ?? '', direction);
			form = {
				group,
				editing: existing.id,
				kind: existing.kind,
				value: existing.value === undefined ? '' : String(existing.value),
				direction,
				label: existing.label,
				named: existing.label !== automatic,
				error: ''
			};
			return;
		}
		const kind: FilterKind | OrderField = group === 'show' ? 'min_rating' : 'rating';
		form = { group, editing: null, kind, value: group === 'show' ? String(FILTER_KINDS.min_rating.example) : '', direction: 'desc', label: '', named: false, error: '' };
	}
	function pickKind(kind: string) {
		if (!form) return;
		form.kind = kind as FilterKind | OrderField;
		if (form.group === 'show') form.value = String(FILTER_KINDS[kind as FilterKind].example);
	}
	const numberOf = (text: string) => (text.trim() === '' ? NaN : Number(text));
	/** What is wrong with the form, or ''. The server checks the same things. */
	function formProblem(f: Form): string {
		if (f.group === 'show') {
			const info = FILTER_KINDS[f.kind as FilterKind];
			if (f.kind === 'marketplace') {
				if (!MARKETPLACE_CHOICES.some(([key]) => key === f.value)) return 'Choose a marketplace.';
			} else {
				const number = numberOf(f.value);
				if (!Number.isFinite(number) || number < (info.min ?? 0) || number > (info.max ?? Infinity)) {
					return `The number must be from ${info.min?.toLocaleString()} to ${info.max?.toLocaleString()}.`;
				}
			}
		}
		const name = f.label.trim();
		if (!name) return 'Give it a name visitors will see.';
		if (name.length > LABEL_MAX) return `The name can be at most ${LABEL_MAX} characters.`;
		return '';
	}
	// A start for the name, until the admin types their own.
	$effect(() => {
		if (!form || form.named) return;
		const value = form.group === 'show' ? (form.kind === 'marketplace' ? form.value : numberOf(form.value)) : '';
		if (form.group === 'show' && (value === '' || (typeof value === 'number' && !Number.isFinite(value)))) form.label = '';
		else form.label = suggestedLabel(form.group, form.kind, value, form.direction);
	});

	function submitForm(event: SubmitEvent) {
		event.preventDefault();
		if (!form || !draft) return;
		const wrong = formProblem(form);
		if (wrong) {
			form.error = wrong;
			return;
		}
		const made: CustomChoice = {
			id: form.editing ?? newId(),
			group: form.group,
			label: form.label.trim(),
			kind: form.kind,
			...(form.group === 'show' ? { value: form.kind === 'marketplace' ? form.value : Number(form.value) } : { direction: form.direction })
		};
		if (form.editing) {
			draft.custom = draft.custom.map((c) => (c.id === made.id ? made : c));
		} else {
			draft.custom = [...draft.custom, made];
			// A new option is offered at once; the admin can untick it.
			setEnabled(form.group, [...rowsOf(form.group).map((row) => row.key).filter((k) => k === made.id || isOn(form!.group, k))]);
		}
		form = null;
	}
	function newId(): string {
		for (;;) {
			const id = `c${Math.random().toString(36).slice(2, 8).padEnd(6, '0')}`;
			if (!draft!.custom.some((c) => c.id === id)) return id;
		}
	}
	function removeOption(option: CustomChoice) {
		if (!draft) return;
		const group = option.group;
		const left = rowsOf(group).map((row) => row.key).filter((k) => k !== option.id && isOn(group, k));
		draft.custom = draft.custom.filter((c) => c.id !== option.id);
		setEnabled(group, left);
		if (form?.editing === option.id) form = null;
	}

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
		if (answer) draft = copy({ ...answer.defaults, custom: answer.defaults.custom ?? [] });
	}
	const howMany = $derived(draft?.custom.length ?? 0);
	const WAYS = (field: OrderField) => ORDER_FIELDS[field];
</script>

{#if failed && !answer}
	<EmptyState art="error" title="The Products page choices couldn't be loaded" description={failed}>
		{#snippet actions()}<Button onclick={load}>Try again</Button>{/snippet}
	</EmptyState>
{:else if !answer || !draft}
	<Skeleton class="h-96 w-full max-w-2xl" />
{:else}
	<div class="grid max-w-2xl gap-6">
		{#each GROUPS as group (group.id)}
			{@const error = problem(group.id)}
			<Card>
				<CardHeader>
					<CardTitle>{group.title}</CardTitle>
					<CardDescription>{group.help} Tick the choices to offer, and pick the one the page starts on.</CardDescription>
				</CardHeader>
				<CardContent class="grid gap-4">
					<RadioGroup bind:value={draft[group.id].default as string} class="grid gap-3" aria-label="{group.title}: the choice the page starts on">
						<div class="text-muted-foreground grid grid-cols-[1fr_auto] gap-x-6 text-xs font-medium tracking-wide uppercase" aria-hidden="true">
							<span>Offer this choice</span><span>Starts on</span>
						</div>
						{#each rowsOf(group.id) as row (row.key)}
							<div class="grid grid-cols-[1fr_auto] items-center gap-x-6">
								<div class="flex flex-wrap items-center gap-x-3 gap-y-1">
									<Checkbox id="{group.id}-{row.key}" checked={isOn(group.id, row.key)} onCheckedChange={(on) => toggle(group.id, row.key, on === true)} />
									<Label for="{group.id}-{row.key}" class="font-normal">{row.text}</Label>
									{#if row.made}
										<Badge variant="secondary">Added by you</Badge>
										<Button type="button" variant="ghost" size="sm" onclick={() => startForm(group.id, row.made)} aria-label="Edit {row.text}">Edit</Button>
										<Button type="button" variant="ghost" size="sm" class="text-destructive hover:text-destructive" onclick={() => removeOption(row.made!)} aria-label="Remove {row.text}">Remove</Button>
									{/if}
								</div>
								<RadioGroupItem value={row.key} id="{group.id}-start-{row.key}" disabled={!isOn(group.id, row.key)} aria-label="{row.text}: start on this choice" />
							</div>
						{/each}
					</RadioGroup>
					{#if error}<p class="text-destructive text-sm" role="alert">{error}</p>{/if}
					{#if draft[group.id].enabled.length === 1}
						<p class="text-muted-foreground text-sm">With one choice left, visitors don't see this list at all.</p>
					{/if}

					{#if form && form.group === group.id}
						{@const f = form}
						<form onsubmit={submitForm} novalidate class="bg-muted/40 grid gap-4 rounded-lg border p-4" aria-label={f.editing ? 'Edit this option' : 'Add your own option'}>
							<p class="text-sm font-medium">{f.editing ? 'Edit this option' : `Add your own: ${group.adding}`}</p>

							{#if group.id === 'show'}
								<div class="grid gap-1.5">
									<Label for="made-kind">Filter by</Label>
									<Select.Root type="single" value={f.kind} onValueChange={pickKind}>
										<Select.Trigger id="made-kind" class="w-full sm:w-72">{FILTER_KINDS[f.kind as FilterKind].name}</Select.Trigger>
										<Select.Content>
											{#each FILTER_KIND_ORDER as kind (kind)}<Select.Item value={kind} label={FILTER_KINDS[kind].name}>{FILTER_KINDS[kind].name}</Select.Item>{/each}
										</Select.Content>
									</Select.Root>
									<p class="text-muted-foreground text-sm" id="made-kind-help">{FILTER_KINDS[f.kind as FilterKind].help}</p>
								</div>
								<div class="grid gap-1.5">
									{#if f.kind === 'marketplace'}
										<Label for="made-value">Marketplace</Label>
										<Select.Root type="single" bind:value={f.value}>
											<Select.Trigger id="made-value" class="w-full sm:w-72">{MARKETPLACE_CHOICES.find(([key]) => key === f.value)?.[1] ?? 'Choose one'}</Select.Trigger>
											<Select.Content>
												{#each MARKETPLACE_CHOICES as [key, text] (key)}<Select.Item value={key} label={text}>{text}</Select.Item>{/each}
											</Select.Content>
										</Select.Root>
									{:else}
										<Label for="made-value">Number</Label>
										<Input id="made-value" inputmode="decimal" class="w-full max-w-40 tabular-nums" bind:value={f.value} aria-describedby="made-kind-help" />
									{/if}
								</div>
							{:else}
								<div class="grid gap-4 sm:grid-cols-2">
									<div class="grid gap-1.5">
										<Label for="made-kind">Order by</Label>
										<Select.Root type="single" value={f.kind} onValueChange={pickKind}>
											<Select.Trigger id="made-kind" class="w-full">{WAYS(f.kind as OrderField).name}</Select.Trigger>
											<Select.Content>
												{#each ORDER_FIELD_ORDER as field (field)}<Select.Item value={field} label={ORDER_FIELDS[field].name}>{ORDER_FIELDS[field].name}</Select.Item>{/each}
											</Select.Content>
										</Select.Root>
									</div>
									<div class="grid gap-1.5">
										<Label for="made-direction">Which way</Label>
										<Select.Root type="single" bind:value={f.direction}>
											<Select.Trigger id="made-direction" class="w-full">{WAYS(f.kind as OrderField)[f.direction].way}</Select.Trigger>
											<Select.Content>
												<Select.Item value="desc" label={WAYS(f.kind as OrderField).desc.way}>{WAYS(f.kind as OrderField).desc.way}</Select.Item>
												<Select.Item value="asc" label={WAYS(f.kind as OrderField).asc.way}>{WAYS(f.kind as OrderField).asc.way}</Select.Item>
											</Select.Content>
										</Select.Root>
									</div>
								</div>
								<p class="text-muted-foreground -mt-2 text-sm">Products with nothing to order by (for example no price) go last.</p>
							{/if}

							<div class="grid gap-1.5">
								<Label for="made-label">Name visitors see</Label>
								<Input id="made-label" class="w-full sm:w-72" maxlength={LABEL_MAX} bind:value={f.label} oninput={() => (f.named = true)} />
							</div>
							{#if f.error}<p class="text-destructive text-sm" role="alert">{f.error}</p>{/if}
							<div class="flex flex-wrap gap-2">
								<Button type="submit" size="sm">{f.editing ? 'Update option' : 'Add option'}</Button>
								<Button type="button" size="sm" variant="outline" onclick={() => (form = null)}>Cancel</Button>
							</div>
						</form>
					{:else}
						<div>
							<Button type="button" variant="outline" size="sm" disabled={howMany >= MAX_CUSTOM} onclick={() => startForm(group.id)}>
								<PlusIcon /> Add your own option
							</Button>
							{#if howMany >= MAX_CUSTOM}<p class="text-muted-foreground mt-2 text-sm">You can add up to {MAX_CUSTOM} options. Remove one to add another.</p>{/if}
						</div>
					{/if}
				</CardContent>
			</Card>
		{/each}
		<form onsubmit={save} novalidate class="flex flex-wrap gap-2">
			<Button type="submit" disabled={saving || !changed || !valid}>{#if saving}<Spinner />{/if} Save choices</Button>
			<Button type="button" variant="outline" disabled={saving || atDefaults} onclick={useAll}>Offer every choice, remove mine</Button>
		</form>
	</div>
{/if}
