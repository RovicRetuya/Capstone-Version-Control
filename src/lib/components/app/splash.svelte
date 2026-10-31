<script lang="ts">
	import { onMount } from 'svelte';
	import logo from '#lib/assets/logo.png';
	import photo from '#lib/assets/splash-bg.jpg';

	// The screen people see first: the logo, the name and the tagline. It stays until the person presses Enter.
	let show = $state(false);
	let leaving = $state(false);

	function enter() {
		if (leaving) return;
		leaving = true;
		setTimeout(() => (show = false), 500);
	}

	onMount(() => {
		show = true;
	});
</script>

<svelte:window onkeydown={(e) => show && e.key === 'Enter' && enter()} />

{#if show}
	<div class="splash" class:leaving style:--photo="url({photo})" role="dialog" aria-label="DeFaketive. A safer you.">
		<span class="swoosh tl" aria-hidden="true"></span>
		<span class="swoosh br" aria-hidden="true"></span>
		<div class="stack">
			<img src={logo} alt="" class="mark" />
			<div class="name" aria-hidden="true"><span>De</span><span class="f">F</span><span>aketive</span></div>
			<div class="tag"><i></i><span>A SAFER YOU</span><i></i></div>
			<button type="button" class="go" onclick={enter}>Enter</button>
		</div>
	</div>
{/if}

<style>
	.splash {
		--navy: #0b1f4d;
		--mustard: #f5b014;
		position: fixed;
		inset: 0;
		z-index: 200;
		display: grid;
		place-items: center;
		overflow: hidden;
		background: linear-gradient(rgba(11, 31, 77, 0.18), rgba(11, 31, 77, 0.18)), var(--photo) center / cover no-repeat, #0b1f4d;
		color: var(--navy);
		transition: opacity 0.5s ease, transform 0.5s ease;
	}
	.splash.leaving {
		opacity: 0;
		transform: scale(1.04);
		pointer-events: none;
	}
	.stack {
		position: relative;
		z-index: 1;
		padding: clamp(1rem, 3vw, 2rem) !important;
		display: grid;
		justify-items: center;
		gap: 0.8rem;
		padding: 1.5rem;
		text-align: center;
	}
	.stack::before {
		content: '';
		position: absolute;
		z-index: -1;
		inset: -34% -46%;
		pointer-events: none;
		background: radial-gradient(closest-side, rgba(255, 255, 255, 0.86) 0%, rgba(255, 255, 255, 0.62) 45%, rgba(255, 255, 255, 0) 100%);
	}
	.mark {
		width: clamp(4.5rem, 12vw, 6.5rem);
		filter: drop-shadow(0 0 10px rgba(255, 255, 255, 0.9)) drop-shadow(0 0 22px rgba(255, 255, 255, 0.6));
		animation: pop 0.9s cubic-bezier(0.2, 0.9, 0.3, 1.25) 0.15s both;
	}
	.name {
		font: 900 clamp(1.8rem, 5.5vw, 3.2rem) / 1 'Archivo Black', 'Arial Black', Impact, sans-serif;
		text-shadow: 0 0 10px rgba(255, 255, 255, 0.95), 0 0 24px rgba(255, 255, 255, 0.7), 0 0 2px #fff;
		font-style: italic;
		letter-spacing: -0.02em;
		animation: up 0.8s cubic-bezier(0.2, 0.7, 0.2, 1) 0.7s both;
	}
	.f {
		color: var(--mustard);
	}
	.tag {
		display: flex;
		align-items: center;
		gap: 1rem;
		font: 600 clamp(0.65rem, 1.8vw, 0.85rem) / 1 Inter, system-ui, sans-serif;
		letter-spacing: 0.45em;
		font-weight: 800;
		text-shadow: 0 0 8px #fff, 0 0 18px rgba(255, 255, 255, 0.85);
		animation: up 0.8s cubic-bezier(0.2, 0.7, 0.2, 1) 1.1s both;
	}
	.tag i {
		display: block;
		width: clamp(1.5rem, 6vw, 3.5rem);
		height: 2px;
		box-shadow: 0 0 8px rgba(255, 255, 255, 0.95);
		border-radius: 2px;
		background: var(--navy);
		transform-origin: center;
		animation: grow 0.7s ease-out 1.4s both;
	}
	.go {
		margin-top: 0.6rem;
		padding: 0.55rem 1.8rem;
		border: 0;
		border-radius: 999px;
		background: var(--navy);
		color: #fff;
		font: 600 0.85rem Inter, system-ui, sans-serif;
		box-shadow: 0 6px 18px -6px rgba(0, 0, 0, 0.55);
		cursor: pointer;
		animation: up 0.7s ease-out 1.8s both;
	}
	.go:hover {
		background: #14357f;
		box-shadow: 0 0 0 3px var(--mustard);
	}
	.swoosh {
		position: absolute;
		width: 70vmax;
		height: 70vmax;
		border-radius: 50%;
		background: var(--navy);
		box-shadow: 0 0 0 0.9vmax var(--mustard);
	}
	.tl {
		left: -52vmax;
		top: -52vmax;
		animation: slide-tl 1.1s cubic-bezier(0.2, 0.7, 0.2, 1) both;
	}
	.br {
		right: -52vmax;
		bottom: -52vmax;
		animation: slide-br 1.1s cubic-bezier(0.2, 0.7, 0.2, 1) 0.15s both;
	}
	@keyframes pop {
		from {
			opacity: 0;
			transform: scale(0.3) rotate(-12deg);
		}
	}
	@keyframes up {
		from {
			opacity: 0;
			transform: translateY(26px);
		}
	}
	@keyframes grow {
		from {
			transform: scaleX(0);
		}
	}
	@keyframes slide-tl {
		from {
			transform: translate(-30vmax, -30vmax);
		}
	}
	@keyframes slide-br {
		from {
			transform: translate(30vmax, 30vmax);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.mark,
		.name,
		.tag,
		.tag i,
		.go,
		.swoosh {
			animation: none;
		}
		.splash {
			transition: opacity 0.2s;
		}
	}
</style>
