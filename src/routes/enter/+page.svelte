<script lang="ts">
	import { goto } from '$app/navigation';
	import { session as adminSession } from '#lib/stores/admin.svelte.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { fly } from 'svelte/transition';
	import FileSearchIcon from '@lucide/svelte/icons/file-search';
	import LanguagesIcon from '@lucide/svelte/icons/languages';
	import ShieldCheckIcon from '@lucide/svelte/icons/shield-check';
	import logo from '#lib/assets/logo.png';
	import texture from '#lib/assets/page-texture.jpg';
	import EnterForm from '#lib/components/app/enter-form.svelte';
	import SignupForm from '#lib/components/app/signup-form.svelte';
	import { Button } from '#lib/components/ui/button/index.js';

	const points = [
		{ icon: ShieldCheckIcon, title: 'Safety warnings first', text: 'Reports of fire, burns and shocks are checked on their own, so good reviews never hide them.' },
		{ icon: LanguagesIcon, title: 'Reads Taglish', text: 'Reviews in Filipino and English are read the way shoppers write them.' },
		{ icon: FileSearchIcon, title: 'See the proof', text: 'Every warning shows the exact reviews behind it, in the reviewers’ own words.' }
	];

	let signup = $state(false);
	// Sliding between sign in and sign up; none for people who asked for less motion.
	const reduced = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
	// Sign up slides in from the right, going back to sign in from the left.
	const slide = $derived({ x: signup ? 28 : -28, duration: reduced ? 0 : 320 });

	// Getting in is the way past the first screen (which has its own Explore), so it is not played again after it.
	function markSplashSeen() {
		try {
			sessionStorage.setItem('splash-seen', '1');
		} catch {
			// Storage blocked: the first screen may show once more.
		}
	}
	function signedIn() {
		void goto('/app/home');
	}
	// Without signing in, people use the guest page (/scan): a few free checks a day, no account.
	// Someone still signed in on this browser (as a shopper, or as the admin, which is a separate sign-in) is signed
	// out first: the guest page sends signed-in people to their account.
	async function guest() {
		markSplashSeen();
		if (!adminSession.ready) await adminSession.load();
		const steps: Promise<unknown>[] = [];
		if (auth.user) steps.push(auth.signOut());
		if (adminSession.me) steps.push(adminSession.signOut());
		await Promise.allSettled(steps);
		void goto('/scan');
	}
</script>

<svelte:head><title>DeFaketive · {signup ? 'Create account' : 'Sign in'}</title></svelte:head>

<!-- One light, textured page under both halves, so the background runs on without a seam. -->
<main class="tex-page enter grid grid-cols-1 min-h-svh lg:grid-cols-[1fr_1.15fr]" style:--tex="url({texture})" style:--tex-wash="rgba(250, 249, 247, 0.55)">
	<section class="flex flex-col justify-between gap-10 p-8 sm:p-12">
		<div class="hero-in inline-flex w-fit items-center gap-3 rounded-full bg-white px-4 py-2 shadow-md">
			<img src={logo} alt="" class="size-8" />
			<span class="text-lg font-extrabold tracking-wide">DeFaketive</span>
		</div>
		<div class="hero-in max-w-lg space-y-8">
			<div class="space-y-4">
				<h1 class="text-3xl leading-tight font-bold tracking-tight sm:text-4xl">Know what buyers really say before you buy.</h1>
				<p class="text-muted-foreground text-base">Paste a Lazada PH link. DeFaketive reads the reviews for safety problems, fakes and defects, then shows you the proof.</p>
			</div>
			<ul class="grid gap-3">
				{#each points as point (point.title)}
					<li class="flex items-start gap-4 rounded-2xl bg-white/90 p-4 shadow-sm ring-1 ring-black/5">
						<span class="grid size-10 shrink-0 place-items-center rounded-full" style="background:#0b1f4d;color:#f5b014"><point.icon class="size-5" aria-hidden="true" /></span>
						<div>
							<h2 class="font-semibold">{point.title}</h2>
							<p class="text-muted-foreground text-sm">{point.text}</p>
						</div>
					</li>
				{/each}
			</ul>
		</div>
		<p class="text-muted-foreground flex items-center gap-3 text-sm font-semibold tracking-[0.3em]"><span class="h-0.5 w-10 rounded" style="background:#f5b014"></span>A SAFER YOU</p>
	</section>

	<section class="grid place-items-center px-6 py-12">
		<div class="hero-in card w-full max-w-lg rounded-3xl p-8 shadow-xl ring-1 ring-black/5 sm:p-10">
			{#key signup}
			<div class="space-y-6" in:fly={slide}>
			<div class="space-y-2">
				<h2 class="text-3xl font-semibold tracking-tight sm:text-4xl">{signup ? 'Create your account' : 'Welcome back'}</h2>
				<p class="text-muted-foreground">
					{signup ? 'Free account: unlimited scans, saved history, a wishlist.' : 'Sign in to keep your history and wishlist. Admins are taken to the admin side automatically.'}
				</p>
			</div>
			{#if signup}
				<SignupForm ondone={signedIn} />
			{:else}
				<EnterForm onshopper={signedIn} />
				<div class="text-muted-foreground flex items-center gap-3 text-xs"><span class="bg-border h-px flex-1"></span>or<span class="bg-border h-px flex-1"></span></div>
				<Button variant="outline" size="lg" class="guest w-full" onclick={guest}>Enter without signing in</Button>
				<p class="text-muted-foreground text-xs">Without an account you get a few free checks a day.</p>
			{/if}
			<p class="text-muted-foreground text-center text-sm">
				{#if signup}
					Already have an account?
					<button type="button" class="text-primary font-medium underline underline-offset-4" onclick={() => (signup = false)}>Sign in</button>
				{:else}
					New to DeFaketive?
					<button type="button" class="text-primary font-medium underline underline-offset-4" onclick={() => (signup = true)}>Create an account</button>
				{/if}
			</p>
			</div>
			{/key}
		</div>
	</section>
</main>

<style>
	/* The box: the page texture under a light wash, with a mustard top edge. */
	.card {
		border-top: 6px solid #f5b014;
		overflow: hidden;
		background: linear-gradient(rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0.8)), var(--tex) 65% 35% / max(100vw, 70rem) auto no-repeat, #fff;
	}
	/* Always the light, textured page, whatever theme the app is in (the dark theme would hide the texture). */
	.enter {
		--background: #faf9f7;
		--foreground: #0b1f4d;
		--card: #fff;
		--card-foreground: #0b1f4d;
		--primary: #0b1f4d;
		--primary-foreground: #fff;
		--muted-foreground: #5b6785;
		--border: #d5dbea;
		--input: #d5dbea;
		--ring: #3556b8;
		--destructive: #c0262d;
		color: var(--foreground);
		color-scheme: light;
	}
	.enter :global(input),
	.enter :global(.guest) {
		background: #fff;
		color: var(--foreground);
		border-color: var(--input);
	}
</style>
