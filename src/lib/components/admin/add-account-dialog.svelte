<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { ApiError, json } from '#lib/api.js';
	import PasswordInput from '#lib/components/app/password-input.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '#lib/components/ui/dialog/index.js';
	import { Field, FieldError, FieldGroup, FieldLabel } from '#lib/components/ui/field/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { adminApi } from '#lib/stores/admin.svelte.js';

	// A shopper account made by the admin (admin_api.py: POST /api/admin/accounts). The admin hands the password over.
	let { open = $bindable(false), onadded }: { open?: boolean; onadded?: () => void } = $props();

	let name = $state('');
	let email = $state('');
	let password = $state('');
	let makeAdmin = $state(false);
	let busy = $state(false);
	let errors = $state<Record<string, string>>({});

	$effect(() => {
		if (open) {
			name = email = password = '';
			makeAdmin = false;
			errors = {};
		}
	});

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		errors = {};
		if (!name.trim()) errors.name = 'Enter their name.';
		if (!email.trim()) errors.email = 'Enter their email.';
		if (password.length < 8) errors.password = 'Use at least 8 characters.';
		if (Object.keys(errors).length) return;
		busy = true;
		try {
			await adminApi('/api/admin/accounts', json('POST', { name, email, password, admin: makeAdmin }));
			open = false;
			toast.success(makeAdmin ? `${name.trim()} was added as an admin.` : `${name.trim()}'s account was added.`);
			onadded?.();
		} catch (error) {
			if (error instanceof ApiError && error.body.fields) errors = error.body.fields;
			else toast.error((error as Error).message);
		} finally {
			busy = false;
		}
	}
</script>

<Dialog bind:open>
	<DialogContent class="sm:max-w-md">
		<DialogHeader>
			<DialogTitle>Add an account</DialogTitle>
			<DialogDescription>Give them the password yourself. A shopper account can change it in Settings; an admin changes it on this page.</DialogDescription>
		</DialogHeader>
		<form onsubmit={submit} novalidate class="grid gap-4">
			<FieldGroup>
				<Field data-invalid={errors.name ? true : undefined}>
					<FieldLabel for="add-name">Full name</FieldLabel>
					<Input id="add-name" name="name" autocomplete="off" bind:value={name} aria-invalid={errors.name ? true : undefined} />
					{#if errors.name}<FieldError>{errors.name}</FieldError>{/if}
				</Field>
				<Field data-invalid={errors.email ? true : undefined}>
					<FieldLabel for="add-email">Email</FieldLabel>
					<Input id="add-email" name="email" type="email" autocomplete="off" bind:value={email} aria-invalid={errors.email ? true : undefined} />
					{#if errors.email}<FieldError>{errors.email}</FieldError>{/if}
				</Field>
				<Field data-invalid={errors.password ? true : undefined}>
					<FieldLabel for="add-password">Password</FieldLabel>
					<PasswordInput id="add-password" name="password" autocomplete="new-password" placeholder="At least 8 characters" bind:value={password} invalid={!!errors.password} />
					{#if errors.password}<FieldError>{errors.password}</FieldError>{/if}
				</Field>
				<Field orientation="horizontal">
					<Checkbox id="add-admin" bind:checked={makeAdmin} />
					<FieldLabel for="add-admin" class="block font-normal">
						Make this account an admin. It can then manage accounts and limits here, but can no longer be used in the shopping app.
					</FieldLabel>
				</Field>
			</FieldGroup>
			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (open = false)} disabled={busy}>Cancel</Button>
				<Button type="submit" disabled={busy}>{#if busy}<Spinner />{/if} Add account</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>
