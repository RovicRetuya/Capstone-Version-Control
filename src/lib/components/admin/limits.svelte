<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { json } from '#lib/api.js';
	import EmptyState from '#lib/components/app/empty-state.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '#lib/components/ui/card/index.js';
	import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from '#lib/components/ui/field/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Progress } from '#lib/components/ui/progress/index.js';
	import { Skeleton } from '#lib/components/ui/skeleton/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { adminApi } from '#lib/stores/admin.svelte.js';
	import type { AdminLimits, DailyLimits } from '#lib/admin-types.js';

	// The three daily limits protections.py counts. A change counts at once, and the server keeps it (admin_api.py).
	const FIELDS: { name: keyof DailyLimits; label: string; help: string }[] = [
		{
			name: 'site',
			label: 'Whole site',
			help: 'New checks everyone together can start in a day. It also keeps the load on Lazada small.'
		},
		{ name: 'account', label: 'Each account', help: 'New checks one signed-in account can start in a day.' },
		{
			name: 'network',
			label: 'Each internet connection (guests)',
			help: 'New checks guests on one internet connection can start in a day. Phone networks put many people on one connection. Guests also get 3 free checks per browser.'
		}
	];

	let answer = $state<AdminLimits | null>(null);
	let failed = $state('');
	let values = $state<Record<keyof DailyLimits, string>>({ site: '', account: '', network: '' });
	let saving = $state(false);

	async function load() {
		failed = '';
		try {
			show(await adminApi<AdminLimits>('/api/admin/limits'));
		} catch (error) {
			failed = (error as Error).message;
		}
	}
	function show(next: AdminLimits) {
		answer = next;
		values = { site: String(next.limits.site), account: String(next.limits.account), network: String(next.limits.network) };
	}
	load();

	const problem = (name: keyof DailyLimits) => {
		const text = values[name].trim();
		if (!/^\d+$/.test(text) || Number(text) > (answer?.max ?? 10000)) return `Use a whole number from 0 to ${(answer?.max ?? 10000).toLocaleString()}.`;
		return '';
	};
	const changed = $derived(answer !== null && FIELDS.some(({ name }) => values[name].trim() !== String(answer!.limits[name])));
	const valid = $derived(FIELDS.every(({ name }) => !problem(name)));
	const atDefaults = $derived(answer !== null && FIELDS.every(({ name }) => values[name].trim() === String(answer!.defaults[name])));

	async function save(event: SubmitEvent) {
		event.preventDefault();
		if (!valid || !changed) return;
		saving = true;
		try {
			const body = Object.fromEntries(FIELDS.map(({ name }) => [name, Number(values[name].trim())]));
			show(await adminApi<AdminLimits>('/api/admin/limits', json('PUT', body)));
			toast.success('Daily limits saved. They count from now on.');
		} catch (error) {
			toast.error((error as Error).message);
		} finally {
			saving = false;
		}
	}
	function useDefaults() {
		if (!answer) return;
		values = { site: String(answer.defaults.site), account: String(answer.defaults.account), network: String(answer.defaults.network) };
	}
</script>

{#if failed && !answer}
	<EmptyState art="error" title="The daily limits couldn't be loaded" description={failed}>
		{#snippet actions()}<Button onclick={load}>Try again</Button>{/snippet}
	</EmptyState>
{:else if !answer}
	<Skeleton class="h-96 w-full max-w-2xl" />
{:else}
	{@const used = answer.site_used_today}
	{@const site = answer.limits.site}
	<div class="grid max-w-2xl gap-6">
		<Card>
			<CardHeader>
				<CardTitle>Today</CardTitle>
				<CardDescription>New checks started on the whole site since midnight (Philippine time).</CardDescription>
			</CardHeader>
			<CardContent class="grid gap-2">
				<p class="text-2xl font-semibold tabular-nums">{used} <span class="text-muted-foreground text-base font-normal">of {site} checks</span></p>
				<Progress value={site ? Math.min(100, (used / site) * 100) : 100} aria-label="Checks used today" />
				{#if used >= site}<p class="text-muted-foreground text-sm">Today's limit is reached. Saved reports still open for everyone.</p>{/if}
			</CardContent>
		</Card>

		<Card>
			<form onsubmit={save} novalidate class="contents">
				<CardHeader>
					<CardTitle>Daily limits</CardTitle>
					<CardDescription>
						How many new checks can start each day. Opening saved reports is never limited. 0 stops new checks.
					</CardDescription>
				</CardHeader>
				<CardContent>
					<FieldGroup>
						{#each FIELDS as field (field.name)}
							{@const error = problem(field.name)}
							<Field data-invalid={error ? true : undefined}>
								<FieldLabel for="limit-{field.name}">{field.label}</FieldLabel>
								<Input
									id="limit-{field.name}"
									name={field.name}
									inputmode="numeric"
									class="max-w-40 tabular-nums"
									bind:value={values[field.name]}
									aria-invalid={error ? true : undefined}
									aria-describedby="limit-{field.name}-help"
								/>
								<FieldDescription id="limit-{field.name}-help">
									{field.help} Starting value: {answer.defaults[field.name]}.
								</FieldDescription>
								{#if error}<FieldError>{error}</FieldError>{/if}
							</Field>
						{/each}
					</FieldGroup>
				</CardContent>
				<CardFooter class="flex flex-wrap gap-2">
					<Button type="submit" disabled={saving || !changed || !valid}>{#if saving}<Spinner />{/if} Save limits</Button>
					<Button type="button" variant="outline" disabled={saving || atDefaults} onclick={useDefaults}>Use starting values</Button>
				</CardFooter>
			</form>
		</Card>
	</div>
{/if}
