<script lang="ts">
	import { ApiError, api, json } from '#lib/api.js';
	import PasswordInput from '#lib/components/app/password-input.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Field, FieldError, FieldGroup, FieldLabel } from '#lib/components/ui/field/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { library } from '#lib/stores/library.svelte.js';

	// `onshopper` runs once a shopper account is signed in (an admin account leaves for the admin app instead).
	let { onshopper, idPrefix = 'enter' }: { onshopper: () => void; idPrefix?: string } = $props();

	// Where the admin app lives (it is a separate app). Set VITE_ADMIN_URL when it is not on this PC's port 5175.
	const adminUrl: string = import.meta.env.VITE_ADMIN_URL ?? 'http://localhost:5175/';

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
			// One form for everyone: an admin account signs in to the admin side, any other account to the shopping app.
			try {
				await api('/api/admin/login', json('POST', credentials));
				markSplashSeen();
				location.href = adminUrl;
				return;
			} catch (problem) {
				// 403: right password, but not an admin. 404: the admin sign-in is not offered at this address.
				// Anything else (wrong password, too many tries) is final, and is shown as it is.
				if (!(problem instanceof ApiError) || (problem.status !== 403 && problem.status !== 404)) throw problem;
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
