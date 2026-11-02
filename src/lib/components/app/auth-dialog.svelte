<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { toast } from 'svelte-sonner';
	import { ApiError } from '#lib/api.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Checkbox } from '#lib/components/ui/checkbox/index.js';
	import {
		Dialog,
		DialogContent,
		DialogDescription,
		DialogHeader,
		DialogTitle
	} from '#lib/components/ui/dialog/index.js';
	import { Field, FieldError, FieldGroup, FieldLabel } from '#lib/components/ui/field/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Separator } from '#lib/components/ui/separator/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { firstName } from '#lib/product.js';
	import { tryAdminSignIn } from '#lib/stores/admin.svelte.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { library } from '#lib/stores/library.svelte.js';
	import { ui } from '#lib/stores/ui.svelte.js';
	import Logo from './logo.svelte';
	import PasswordInput from './password-input.svelte';

	let fullName = $state('');
	let email = $state('');
	let password = $state('');
	let confirm = $state('');
	let agree = $state(false);
	let busy = $state(false);
	let errors = $state<Record<string, string>>({});
	let formError = $state('');

	const signup = $derived(ui.authKind === 'signup');

	function reset() {
		errors = {};
		formError = '';
	}

	// Switching between sign in and sign up clears old errors but keeps what was typed.
	$effect(() => {
		ui.authKind;
		ui.authOpen;
		reset();
	});

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		reset();
		busy = true;
		try {
			// The admin account signs in to the admin side; every other account goes on to the shopping app.
			if (!signup && (await tryAdminSignIn(email.trim(), password))) {
				email = password = '';
				ui.authOpen = false;
				ui.afterAuth = '';
				await goto('/admin');
				return;
			}
			const me = signup
				? await auth.signUp({ full_name: fullName, email, password, confirm, agree })
				: await auth.signIn(email, password);
			fullName = email = password = confirm = '';
			agree = false;
			ui.authOpen = false;
			await library.loadAccount();
			// A new account is greeted by the welcome tour instead (a notice here would sit over its buttons on a phone).
			if (!signup) toast(`Signed in as ${me.user?.name}.`);
			// From the landing page go to the app; otherwise stay where you were, or go where you were headed.
			const here = page.url.pathname;
			const next = ui.afterAuth || (here === '/' ? '/app/home' : here.startsWith('/scan') ? '/app/analyze' : '');
			ui.afterAuth = '';
			if (next && next !== here) await goto(next);
			// A new account gets the welcome tour, on whatever page they are now.
			if (signup) ui.tourOpen = true;
		} catch (error) {
			const failure = error as ApiError;
			const fields = (failure.body?.fields ?? {}) as Record<string, string>;
			if (Object.keys(fields).length) errors = fields;
			else formError = failure.message;
		} finally {
			busy = false;
		}
	}

	function continueAsGuest() {
		ui.authOpen = false;
		goto('/scan');
	}
</script>

<Dialog bind:open={ui.authOpen}>
	<DialogContent class="max-h-[calc(100svh-2rem)] overflow-y-auto sm:max-w-md">
		<DialogHeader>
			<Logo href="#" class="mb-2 w-fit" />
			<DialogTitle class="text-xl">{signup ? 'Create account' : 'Sign in'}</DialogTitle>
			<DialogDescription>
				{signup ? 'Free account: unlimited scans, saved history, a wishlist.' : 'Welcome back. Detect the defect.'}
			</DialogDescription>
		</DialogHeader>

		{#if ui.authNotice}
			<p class="bg-muted rounded-lg px-3 py-2 text-sm" role="status">{ui.authNotice}</p>
		{/if}

		<form onsubmit={submit} novalidate class="grid gap-4">
			<FieldGroup class="gap-4">
				{#if signup}
					<Field data-invalid={!!errors.full_name}>
						<FieldLabel for="auth-name">Full name</FieldLabel>
						<Input id="auth-name" name="full_name" autocomplete="name" placeholder="Juan Dela Cruz" maxlength={100} bind:value={fullName} aria-invalid={!!errors.full_name} />
						{#if errors.full_name}<FieldError>{errors.full_name}</FieldError>{/if}
					</Field>
				{/if}
				<Field data-invalid={!!errors.email}>
					<FieldLabel for="auth-email">Email</FieldLabel>
					<Input id="auth-email" name="email" type="email" autocomplete="email" placeholder="you@example.com" bind:value={email} aria-invalid={!!errors.email} />
					{#if errors.email}<FieldError>{errors.email}</FieldError>{/if}
				</Field>
				<Field data-invalid={!!errors.password}>
					<FieldLabel for="auth-password">Password</FieldLabel>
					<PasswordInput id="auth-password" name="password" autocomplete={signup ? 'new-password' : 'current-password'} placeholder="At least 8 characters" bind:value={password} invalid={!!errors.password} />
					{#if errors.password}<FieldError>{errors.password}</FieldError>{/if}
				</Field>
				{#if signup}
					<Field data-invalid={!!errors.confirm}>
						<FieldLabel for="auth-confirm">Confirm password</FieldLabel>
						<PasswordInput id="auth-confirm" name="confirm" autocomplete="new-password" placeholder="Re-enter password" bind:value={confirm} invalid={!!errors.confirm} />
						{#if errors.confirm}<FieldError>{errors.confirm}</FieldError>{/if}
					</Field>
					<Field orientation="horizontal" data-invalid={!!errors.agree}>
						<Checkbox id="auth-agree" bind:checked={agree} aria-invalid={!!errors.agree} />
						<FieldLabel for="auth-agree" class="block font-normal">
							I agree to the
							<button type="button" class="underline underline-offset-4" onclick={() => ui.openTerms('terms')}>Terms of Service</button>
							and
							<button type="button" class="underline underline-offset-4" onclick={() => ui.openTerms('privacy')}>Privacy Policy</button>.
						</FieldLabel>
					</Field>
					{#if errors.agree}<FieldError>{errors.agree}</FieldError>{/if}
				{/if}
			</FieldGroup>

			{#if formError}
				<p class="text-destructive text-sm" role="alert">{formError}</p>
			{/if}

			<Button type="submit" size="lg" disabled={busy}>
				{#if busy}<Spinner />{/if}
				{#if signup}{busy ? 'Creating account…' : 'Create account'}{:else}{busy ? 'Signing in…' : 'Sign in'}{/if}
			</Button>
		</form>

		{#if !signup}
			<div class="flex items-center gap-3" aria-hidden="true">
				<Separator class="flex-1" /><span class="text-muted-foreground text-xs">or</span><Separator class="flex-1" />
			</div>
			<Button variant="outline" size="lg" onclick={continueAsGuest}>
				{auth.left > 0
					? `Continue as guest — ${auth.left} free scan${auth.left === 1 ? '' : 's'} left today`
					: 'Continue as guest — no free scans left today'}
			</Button>
		{/if}

		<p class="text-muted-foreground text-center text-sm">
			{#if signup}
				Already have an account?
				<button type="button" class="text-primary underline underline-offset-4" onclick={() => (ui.authKind = 'signin')}>Sign in</button>
			{:else}
				No account yet?
				<button type="button" class="text-primary underline underline-offset-4" onclick={() => (ui.authKind = 'signup')}>Sign up — it's free</button>
			{/if}
		</p>
	</DialogContent>
</Dialog>
