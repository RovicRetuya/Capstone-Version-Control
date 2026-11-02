<script lang="ts">
	import { goto } from '$app/navigation';
	import { ApiError } from '#lib/api.js';
	import PasswordInput from '#lib/components/app/password-input.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Field, FieldError, FieldGroup, FieldLabel } from '#lib/components/ui/field/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { tryAdminSignIn } from '#lib/stores/admin.svelte.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { library } from '#lib/stores/library.svelte.js';

	// `onshopper` runs once a shopper account is signed in (the admin account goes to the admin side instead).
	let { onshopper, idPrefix = 'enter' }: { onshopper: () => void; idPrefix?: string } = $props();

	let email = $state('');
	let password = $state('');
	let busy = $state(false);
	let error = $state('');

	function markSplashSeen() {
		try {
			sessionStorage.setItem('splash-seen', '1');
		} catch {
			// Storage blocked: the splash may show once more.
		}
	}

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (!email.trim() || !password) {
			error = 'Enter your email and password.';
			return;
		}
		busy = true;
		error = '';
		try {
			const credentials = { email: email.trim(), password };
			// One form for everyone: the admin account signs in to the admin side, any other account to the shopping app.
			if (await tryAdminSignIn(credentials.email, credentials.password)) {
				markSplashSeen();
				await goto('/admin');
				return;
			}
			await auth.signIn(credentials.email, credentials.password);
			await library.loadAccount();
			markSplashSeen();
			onshopper();
		} catch (problem) {
			error = problem instanceof ApiError ? problem.message : 'The server could not be reached. Try again.';
		} finally {
			busy = false;
		}
	}
</script>

<form onsubmit={submit} novalidate class="grid gap-4">
	<FieldGroup>
		<Field data-invalid={error ? true : undefined}>
			<FieldLabel for="{idPrefix}-email">Email</FieldLabel>
			<Input id="{idPrefix}-email" name="email" type="email" autocomplete="username" bind:value={email} aria-invalid={error ? true : undefined} />
		</Field>
		<Field data-invalid={error ? true : undefined}>
			<FieldLabel for="{idPrefix}-password">Password</FieldLabel>
			<PasswordInput id="{idPrefix}-password" name="password" autocomplete="current-password" bind:value={password} invalid={!!error} />
			{#if error}<FieldError>{error}</FieldError>{/if}
		</Field>
	</FieldGroup>
	<Button type="submit" disabled={busy}>{#if busy}<Spinner />{/if} Sign in</Button>
</form>
