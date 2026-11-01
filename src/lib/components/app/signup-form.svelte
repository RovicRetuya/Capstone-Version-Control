<script lang="ts">
	import { ApiError } from '#lib/api.js';
	import PasswordInput from '#lib/components/app/password-input.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import { Field, FieldError, FieldGroup, FieldLabel } from '#lib/components/ui/field/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { library } from '#lib/stores/library.svelte.js';
	import { ui } from '#lib/stores/ui.svelte.js';

	// `ondone` runs once the account is made (and signed in).
	let { ondone }: { ondone: () => void } = $props();

	let fullName = $state('');
	let email = $state('');
	let password = $state('');
	let confirm = $state('');
	let agree = $state(false);
	let busy = $state(false);
	let errors = $state<Record<string, string>>({});
	let formError = $state('');

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		errors = {};
		formError = '';
		busy = true;
		try {
			await auth.signUp({ full_name: fullName, email, password, confirm, agree });
			await library.loadAccount();
			try {
				sessionStorage.setItem('splash-seen', '1');
			} catch {
				// Storage blocked: the first screen may show once more.
			}
			// A new account gets the welcome tour, as in the sign-up dialog.
			ui.tourOpen = true;
			ondone();
		} catch (error) {
			const failure = error as ApiError;
			const fields = (failure.body?.fields ?? {}) as Record<string, string>;
			if (Object.keys(fields).length) errors = fields;
			else formError = failure.message ?? 'The server could not be reached. Try again.';
		} finally {
			busy = false;
		}
	}
</script>

<form onsubmit={submit} novalidate class="grid gap-4">
	<FieldGroup class="gap-4">
		<Field data-invalid={!!errors.full_name}>
			<FieldLabel for="up-name">Full name</FieldLabel>
			<Input id="up-name" name="full_name" autocomplete="name" placeholder="Juan Dela Cruz" maxlength={100} bind:value={fullName} aria-invalid={!!errors.full_name} />
			{#if errors.full_name}<FieldError>{errors.full_name}</FieldError>{/if}
		</Field>
		<Field data-invalid={!!errors.email}>
			<FieldLabel for="up-email">Email</FieldLabel>
			<Input id="up-email" name="email" type="email" autocomplete="email" placeholder="you@example.com" bind:value={email} aria-invalid={!!errors.email} />
			{#if errors.email}<FieldError>{errors.email}</FieldError>{/if}
		</Field>
		<Field data-invalid={!!errors.password}>
			<FieldLabel for="up-password">Password</FieldLabel>
			<PasswordInput id="up-password" name="password" autocomplete="new-password" placeholder="At least 8 characters" bind:value={password} invalid={!!errors.password} />
			{#if errors.password}<FieldError>{errors.password}</FieldError>{/if}
		</Field>
		<Field data-invalid={!!errors.confirm}>
			<FieldLabel for="up-confirm">Confirm password</FieldLabel>
			<PasswordInput id="up-confirm" name="confirm" autocomplete="new-password" placeholder="Re-enter password" bind:value={confirm} invalid={!!errors.confirm} />
			{#if errors.confirm}<FieldError>{errors.confirm}</FieldError>{/if}
		</Field>
		<Field orientation="horizontal" data-invalid={!!errors.agree}>
			<Checkbox id="up-agree" bind:checked={agree} aria-invalid={!!errors.agree} />
			<FieldLabel for="up-agree" class="block font-normal">
				I agree to the
				<button type="button" class="underline underline-offset-4" onclick={() => ui.openTerms('terms')}>Terms of Service</button>
				and
				<button type="button" class="underline underline-offset-4" onclick={() => ui.openTerms('privacy')}>Privacy Policy</button>.
			</FieldLabel>
		</Field>
		{#if errors.agree}<FieldError>{errors.agree}</FieldError>{/if}
	</FieldGroup>
	{#if formError}<p class="text-destructive text-sm" role="alert">{formError}</p>{/if}
	<Button type="submit" disabled={busy}>{#if busy}<Spinner />{/if} {busy ? 'Creating account…' : 'Create account'}</Button>
</form>
