<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { ApiError, json } from '#lib/api.js';
	import PasswordInput from '#lib/components/app/password-input.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '#lib/components/ui/dialog/index.js';
	import { Field, FieldError, FieldGroup, FieldLabel } from '#lib/components/ui/field/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { adminApi } from '#lib/stores/admin.svelte.js';

	// An admin account is admin-only, so its password is changed here (the shopping app's Settings can't be reached).
	let { open = $bindable(false) }: { open?: boolean } = $props();

	let current = $state('');
	let next = $state('');
	let again = $state('');
	let busy = $state(false);
	let errors = $state<Record<string, string>>({});

	$effect(() => {
		if (open) {
			current = next = again = '';
			errors = {};
		}
	});

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		errors = {};
		if (!current) errors.current_password = 'Enter your current password.';
		if (next.length < 8) errors.new_password = 'Use at least 8 characters.';
		else if (next !== again) errors.again = "The two new passwords don't match.";
		if (Object.keys(errors).length) return;
		busy = true;
		try {
			await adminApi('/api/admin/password', json('PUT', { current_password: current, new_password: next }));
			open = false;
			toast.success('Your password was changed.');
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
			<DialogTitle>Change your password</DialogTitle>
			<DialogDescription>Choose a password only you know.</DialogDescription>
		</DialogHeader>
		<form onsubmit={submit} novalidate class="grid gap-4">
			<FieldGroup>
				<Field data-invalid={errors.current_password ? true : undefined}>
					<FieldLabel for="pw-current">Current password</FieldLabel>
					<PasswordInput id="pw-current" name="current_password" autocomplete="current-password" bind:value={current} invalid={!!errors.current_password} />
					{#if errors.current_password}<FieldError>{errors.current_password}</FieldError>{/if}
				</Field>
				<Field data-invalid={errors.new_password ? true : undefined}>
					<FieldLabel for="pw-new">New password</FieldLabel>
					<PasswordInput id="pw-new" name="new_password" autocomplete="new-password" placeholder="At least 8 characters" bind:value={next} invalid={!!errors.new_password} />
					{#if errors.new_password}<FieldError>{errors.new_password}</FieldError>{/if}
				</Field>
				<Field data-invalid={errors.again ? true : undefined}>
					<FieldLabel for="pw-again">New password again</FieldLabel>
					<PasswordInput id="pw-again" name="again" autocomplete="new-password" bind:value={again} invalid={!!errors.again} />
					{#if errors.again}<FieldError>{errors.again}</FieldError>{/if}
				</Field>
			</FieldGroup>
			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (open = false)} disabled={busy}>Cancel</Button>
				<Button type="submit" disabled={busy}>{#if busy}<Spinner />{/if} Change password</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>
