<script lang="ts">
	import CheckIcon from '@lucide/svelte/icons/check';
	import { ApiError, api, json } from '#lib/api.js';
	import PasswordInput from '#lib/components/app/password-input.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '#lib/components/ui/dialog/index.js';
	import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from '#lib/components/ui/field/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';

	// "Forgot password": a request to the admin (password_requests.py), who sets a new password and sends it to the
	// email given here. The remembered password is only compared on the server; it is never saved.
	let { open = $bindable(false), email: startEmail = '' }: { open?: boolean; email?: string } = $props();

	let name = $state('');
	let email = $state('');
	let last = $state('');
	let sendTo = $state('');
	let busy = $state(false);
	let sent = $state('');
	let errors = $state<Record<string, string>>({});

	$effect(() => {
		if (!open) return;
		name = last = sent = '';
		email = sendTo = startEmail;
		errors = {};
	});

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		errors = {};
		if (!name.trim()) errors.name = 'Enter the name on your account.';
		if (!email.trim()) errors.email = 'Enter the email on your account.';
		if (!sendTo.trim()) errors.send_to = 'Enter the email to send the new password to.';
		if (Object.keys(errors).length) return;
		busy = true;
		try {
			const answer = await api<{ message: string }>(
				'/api/password-request',
				json('POST', { name: name.trim(), email: email.trim(), last_password: last, send_to: sendTo.trim() })
			);
			sent = answer.message;
			last = '';
		} catch (error) {
			if (error instanceof ApiError && error.body.fields) errors = error.body.fields;
			else errors.form = error instanceof ApiError ? error.message : 'The request could not be sent. Check your connection and try again.';
		} finally {
			busy = false;
		}
	}
</script>

<Dialog bind:open>
	<DialogContent class="sm:max-w-md">
		<DialogHeader>
			<DialogTitle>Forgot your password?</DialogTitle>
			<DialogDescription>
				Tell the admin who you are. They will set a new password for your account and send it to the email you give below.
			</DialogDescription>
		</DialogHeader>
		{#if sent}
			<p class="flex items-start gap-2 text-sm" role="status"><CheckIcon class="text-success mt-0.5 size-4 shrink-0" aria-hidden="true" /> {sent}</p>
			<DialogFooter><Button onclick={() => (open = false)}>Close</Button></DialogFooter>
		{:else}
			<form onsubmit={submit} novalidate class="grid gap-4">
				<FieldGroup>
					<Field data-invalid={errors.name ? true : undefined}>
						<FieldLabel for="forgot-name">Username</FieldLabel>
						<Input id="forgot-name" name="name" autocomplete="name" placeholder="The name on your account" bind:value={name} aria-invalid={errors.name ? true : undefined} />
						{#if errors.name}<FieldError>{errors.name}</FieldError>{/if}
					</Field>
					<Field data-invalid={errors.email ? true : undefined}>
						<FieldLabel for="forgot-email">Email</FieldLabel>
						<Input id="forgot-email" name="email" type="email" autocomplete="email" placeholder="The email you signed up with" bind:value={email} aria-invalid={errors.email ? true : undefined} />
						{#if errors.email}<FieldError>{errors.email}</FieldError>{/if}
					</Field>
					<Field>
						<FieldLabel for="forgot-last">Last remembered password</FieldLabel>
						<PasswordInput id="forgot-last" name="last_password" autocomplete="new-password" bind:value={last} />
						<FieldDescription>Optional, but it helps the admin know it is you. It is checked and thrown away, never saved.</FieldDescription>
					</Field>
					<Field data-invalid={errors.send_to ? true : undefined}>
						<FieldLabel for="forgot-send">Send the new password to this email</FieldLabel>
						<Input id="forgot-send" name="send_to" type="email" autocomplete="off" placeholder="An email you can open" bind:value={sendTo} aria-invalid={errors.send_to ? true : undefined} />
						{#if errors.send_to}<FieldError>{errors.send_to}</FieldError>{/if}
					</Field>
				</FieldGroup>
				{#if errors.form}<p class="text-destructive text-sm" role="alert">{errors.form}</p>{/if}
				<DialogFooter>
					<Button type="button" variant="outline" onclick={() => (open = false)} disabled={busy}>Cancel</Button>
					<Button type="submit" disabled={busy}>{#if busy}<Spinner />{/if} Send request</Button>
				</DialogFooter>
			</form>
		{/if}
	</DialogContent>
</Dialog>
