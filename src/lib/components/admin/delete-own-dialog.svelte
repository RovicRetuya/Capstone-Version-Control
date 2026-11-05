<script lang="ts">
	import { goto } from '$app/navigation';
	import { toast } from 'svelte-sonner';
	import { ApiError, json } from '#lib/api.js';
	import PasswordInput from '#lib/components/app/password-input.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '#lib/components/ui/dialog/index.js';
	import { Field, FieldError, FieldGroup, FieldLabel } from '#lib/components/ui/field/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { adminApi, session } from '#lib/stores/admin.svelte.js';

	// An admin deletes their own account here (admin_api.py: DELETE /api/admin/accounts/<own id>), with their password.
	// The server refuses for the only admin left, and says so.
	let { open = $bindable(false) }: { open?: boolean } = $props();

	let password = $state('');
	let busy = $state(false);
	let error = $state('');

	$effect(() => {
		if (open) {
			password = '';
			error = '';
		}
	});

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (!session.me) return;
		if (!password) {
			error = 'Enter your password to confirm.';
			return;
		}
		busy = true;
		error = '';
		try {
			await adminApi(`/api/admin/accounts/${session.me.id}`, { ...json('DELETE', { current_password: password }) });
			session.me = null;
			open = false;
			toast.success('Your account was deleted.');
			await goto('/enter');
		} catch (problem) {
			error = problem instanceof ApiError ? problem.message : 'The server could not be reached. Try again.';
		} finally {
			busy = false;
		}
	}
</script>

<Dialog bind:open>
	<DialogContent class="sm:max-w-md">
		<DialogHeader>
			<DialogTitle>Delete your account?</DialogTitle>
			<DialogDescription>
				This deletes your admin account for good, and you are signed out. You can only do this while another admin exists. Other accounts are not touched.
			</DialogDescription>
		</DialogHeader>
		<form onsubmit={submit} novalidate class="grid gap-4">
			<FieldGroup>
				<Field data-invalid={error ? true : undefined}>
					<FieldLabel for="delete-own-password">Your password</FieldLabel>
					<PasswordInput id="delete-own-password" name="current_password" autocomplete="current-password" bind:value={password} invalid={!!error} />
					{#if error}<FieldError>{error}</FieldError>{/if}
				</Field>
			</FieldGroup>
			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (open = false)} disabled={busy}>Keep my account</Button>
				<Button type="submit" variant="destructive" disabled={busy}>{#if busy}<Spinner />{/if} Delete my account</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>
