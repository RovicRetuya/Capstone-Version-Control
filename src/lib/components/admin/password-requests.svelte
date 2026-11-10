<script lang="ts">
	import CheckIcon from '@lucide/svelte/icons/check';
	import CopyIcon from '@lucide/svelte/icons/copy';
	import KeyRoundIcon from '@lucide/svelte/icons/key-round';
	import MailIcon from '@lucide/svelte/icons/mail';
	import SearchIcon from '@lucide/svelte/icons/search';
	import XIcon from '@lucide/svelte/icons/x';
	import { toast } from 'svelte-sonner';
	import EmptyState from '#lib/components/app/empty-state.svelte';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Card } from '#lib/components/ui/card/index.js';
	import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '#lib/components/ui/dialog/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import * as Select from '#lib/components/ui/select/index.js';
	import { Skeleton } from '#lib/components/ui/skeleton/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { reportTime } from '#lib/problem-report.js';
	import { passwordRequests as requests } from '#lib/stores/admin-requests.svelte.js';
	import type { AdminPasswordReset } from '#lib/admin-types.js';

	// People who pressed "Forgot password" on the sign-in page (password_requests.py). The admin checks the three clues
	// the server worked out (an account has that email, the name fits, the remembered password was right), then sets a
	// new password: it is emailed to the address the person gave and shown here once.
	const STATUSES: [typeof requests.status, string][] = [
		['new', 'Needs a look'],
		['done', 'Handled'],
		['all', 'All requests']
	];
	const nameOf = (value: string) => STATUSES.find(([key]) => key === value)?.[1] ?? '';

	requests.load();

	let timer: ReturnType<typeof setTimeout> | undefined;
	function onSearch() {
		clearTimeout(timer);
		timer = setTimeout(() => requests.load(), 250);
	}
	const narrowed = $derived(requests.status !== 'all' || requests.query.trim() !== '');
	function showAll() {
		requests.status = 'all';
		requests.query = '';
		requests.load();
	}

	let shown = $state<AdminPasswordReset | null>(null);
	let showOpen = $state(false);
	let copied = $state(false);

	async function reset(id: number) {
		try {
			shown = await requests.reset(id);
			copied = false;
			showOpen = true;
		} catch (error) {
			toast.error((error as Error).message);
		}
	}
	async function mark(id: number, status: 'new' | 'done') {
		try {
			await requests.mark(id, status);
			toast.success(status === 'done' ? 'Marked as handled.' : 'Opened again.');
		} catch (error) {
			toast.error((error as Error).message);
		}
	}
	async function copy() {
		if (!shown) return;
		try {
			await navigator.clipboard.writeText(shown.password);
			copied = true;
		} catch {
			toast.error('Could not copy. Select the password and copy it.');
		}
	}
</script>

{#snippet clue(ok: boolean, yes: string, no: string)}
	<Badge variant={ok ? 'secondary' : 'outline'} class={ok ? '' : 'text-muted-foreground'}>
		{#if ok}<CheckIcon /> {yes}{:else}<XIcon /> {no}{/if}
	</Badge>
{/snippet}

<div class="flex flex-col gap-4">
	<div class="flex flex-col gap-3 lg:flex-row lg:items-end">
		<div class="grid w-full gap-2 lg:max-w-sm">
			<Label for="request-search">Search requests</Label>
			<div class="relative">
				<SearchIcon class="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
				<Input id="request-search" type="search" class="pl-9" placeholder="A name or an email" bind:value={requests.query} oninput={onSearch} />
			</div>
		</div>
		<div class="grid gap-2">
			<Label for="request-status">Show</Label>
			<Select.Root type="single" value={requests.status} onValueChange={(value) => ((requests.status = value as typeof requests.status), requests.load())}>
				<Select.Trigger id="request-status" class="w-full sm:w-48">{nameOf(requests.status)}</Select.Trigger>
				<Select.Content>
					{#each STATUSES as [key, text] (key)}<Select.Item value={key} label={text}>{text}</Select.Item>{/each}
				</Select.Content>
			</Select.Root>
		</div>
		{#if requests.data}
			<p class="text-muted-foreground text-sm lg:ml-auto" aria-live="polite">
				{requests.data.counts.new} {requests.data.counts.new === 1 ? 'needs' : 'need'} a look · {requests.data.counts.done} handled
			</p>
		{/if}
	</div>

	{#if requests.failed && !requests.data}
		<EmptyState art="error" title="The requests couldn't be loaded" description={requests.failed}>
			{#snippet actions()}<Button onclick={() => requests.load()}>Try again</Button>{/snippet}
		</EmptyState>
	{:else if !requests.data}
		<div class="grid gap-3" role="status" aria-label="Loading requests">
			{#each [0, 1, 2] as row (row)}<Skeleton class="h-28 w-full" />{/each}
		</div>
	{:else if !requests.data.requests.length}
		{#if requests.data.counts.total === 0}
			<EmptyState art="reviews" title="No requests yet" description="When someone uses Forgot password on the sign-in page, it shows up here." />
		{:else if requests.status === 'new' && !requests.query.trim()}
			<EmptyState art="reviews" title="Nothing needs a look" description="Every request has been handled.">
				{#snippet actions()}<Button variant="outline" onclick={showAll}>Show all requests</Button>{/snippet}
			</EmptyState>
		{:else}
			<EmptyState art="search" title="No requests match" description="Try another name or email, or another status.">
				{#snippet actions()}<Button variant="outline" onclick={showAll}>Show all requests</Button>{/snippet}
			</EmptyState>
		{/if}
	{:else}
		<ul class="grid gap-3" aria-label="Forgot password requests">
			{#each requests.data.requests as request (request.id)}
				<li data-request={request.id}>
					<Card class="gap-3 p-4">
						<div class="flex flex-wrap items-center gap-2">
							{#if request.status === 'new'}<Badge>New</Badge>{:else}<Badge variant="outline">Handled</Badge>{/if}
							<span class="text-muted-foreground text-sm">#{request.id} · {reportTime(request.created_at)}</span>
						</div>
						<dl class="grid gap-1 text-sm sm:grid-cols-[auto_1fr] sm:gap-x-4">
							<dt class="text-muted-foreground font-medium">Username</dt>
							<dd class="min-w-0 break-words">{request.name}</dd>
							<dt class="text-muted-foreground font-medium">Email</dt>
							<dd class="min-w-0 break-all">{request.email}</dd>
							<dt class="text-muted-foreground font-medium">Send the new password to</dt>
							<dd class="min-w-0 break-all">
								<a class="text-primary inline-flex items-center gap-1 underline underline-offset-4" href="mailto:{request.send_to}"><MailIcon class="size-3.5" aria-hidden="true" />{request.send_to}</a>
							</dd>
							<dt class="text-muted-foreground font-medium">Last remembered password</dt>
							<dd class="flex flex-wrap items-center gap-2">
								{@render clue(request.password_matched, 'It was the account’s password', 'It did not match')}
								<span class="text-muted-foreground text-xs">The password itself is not kept.</span>
							</dd>
						</dl>
						<div class="flex flex-wrap gap-2" aria-label="What the server found">
							{@render clue(request.account_found, 'An account has this email', 'No account has this email')}
							{@render clue(request.name_matches, 'The name fits', 'The name does not fit')}
						</div>
						<div class="flex flex-wrap gap-2">
							<Button size="sm" disabled={!request.account_found || requests.busy === request.id} onclick={() => reset(request.id)}>
								{#if requests.busy === request.id}<Spinner />{:else}<KeyRoundIcon />{/if}
								{request.status === 'done' ? 'Set another new password' : 'Set a new password and send it'}
							</Button>
							{#if request.status === 'new'}
								<Button size="sm" variant="outline" disabled={requests.busy === request.id} onclick={() => mark(request.id, 'done')}>Mark as handled</Button>
							{:else}
								<Button size="sm" variant="outline" disabled={requests.busy === request.id} onclick={() => mark(request.id, 'new')}>Open again</Button>
							{/if}
						</div>
					</Card>
				</li>
			{/each}
		</ul>
		{#if narrowed && requests.data.requests.length < requests.data.counts.total}
			<p class="text-muted-foreground text-sm">Showing {requests.data.requests.length} of {requests.data.counts.total}. <button type="button" class="text-primary underline underline-offset-4" onclick={showAll}>Show all</button></p>
		{/if}
	{/if}
</div>

<Dialog bind:open={showOpen}>
	<DialogContent class="sm:max-w-md">
		<DialogHeader>
			<DialogTitle>New password set</DialogTitle>
			<DialogDescription>
				{#if shown?.emailed}
					It was emailed to {shown.send_to}. This is the only time you can see it here.
				{:else}
					No email could be sent from the server (no mail account is set up), so give it to {shown?.name ?? 'the person'} yourself, for example by writing to {shown?.send_to}. This is the only time you can see it.
				{/if}
			</DialogDescription>
		</DialogHeader>
		<div class="flex items-center gap-2">
			<code class="bg-muted min-w-0 flex-1 rounded-md px-3 py-2 font-mono text-base break-all select-all" aria-label="The new password">{shown?.password}</code>
			<Button variant="outline" size="icon" aria-label="Copy the password" onclick={copy}>{#if copied}<CheckIcon />{:else}<CopyIcon />{/if}</Button>
		</div>
		<p class="text-muted-foreground text-sm">They should sign in with it, then change it in Settings. The request has been deleted, because it held email addresses.</p>
		<DialogFooter><Button onclick={() => (showOpen = false)}>Done</Button></DialogFooter>
	</DialogContent>
</Dialog>
