<script lang="ts">
	import XIcon from '@lucide/svelte/icons/x';
	import { InputGroupAddon, InputGroupButton } from '#lib/components/ui/input-group/index.js';

	// The "clear" button at the end of a link box: shows only when there is something to clear, and puts the cursor
	// back in the box so the next link can be pasted at once.
	let { value = $bindable(''), disabled = false }: { value: string; disabled?: boolean } = $props();

	function clear(event: MouseEvent) {
		value = '';
		const box = (event.currentTarget as HTMLElement).closest('[data-slot="input-group"]')?.querySelector('input');
		box?.focus();
	}
</script>

{#if value}
	<InputGroupAddon align="inline-end">
		<InputGroupButton size="icon-xs" aria-label="Clear the link" title="Clear the link" {disabled} onclick={clear}><XIcon /></InputGroupButton>
	</InputGroupAddon>
{/if}
