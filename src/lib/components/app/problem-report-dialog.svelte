<script lang="ts">
	import { page } from '$app/state';
	import { toast } from 'svelte-sonner';
	import { api, ApiError, json } from '#lib/api.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '#lib/components/ui/dialog/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import * as Select from '#lib/components/ui/select/index.js';
	import { Spinner } from '#lib/components/ui/spinner/index.js';
	import { Textarea } from '#lib/components/ui/textarea/index.js';
	import { REPORT_CATEGORIES, REPORT_EMAIL_MAX, REPORT_MAX, REPORT_MIN, REPORT_PAGE_MAX } from '#lib/problem-report.js';
	import { auth } from '#lib/stores/auth.svelte.js';
	import { ui } from '#lib/stores/ui.svelte.js';

	// "Report a problem": a short form any page can open (ui.openReport). The server keeps it for the team and the admin
	// reads it on the admin page (problem_reports.py, admin_api.py). The page the person was on goes with it, so
	// nobody has to explain where they were.
	let category = $state('other');
	let message = $state('');
	let email = $state('');
	let where = $state('');
	let error = $state('');
	let busy = $state(false);

	// Each time the pop-up opens it starts clean, on the kind the opener named, with the account's email filled in.
	$effect(() => {
		if (!ui.reportOpen) return;
		category = ui.reportCategory;
		message = '';
		email = auth.user?.email ?? '';
		error = '';
		where = (page.url.pathname + page.url.search).slice(0, REPORT_PAGE_MAX);
	});

	const length = $derived(message.trim().length);
	const label = (value: string) => REPORT_CATEGORIES.find(([key]) => key === value)?.[1] ?? '';

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		error = '';
		if (length < REPORT_MIN) {
			error = `Please tell us a little more (at least ${REPORT_MIN} characters).`;
			return;
		}
		busy = true;
		try {
			const answer = await api<{ message?: string }>('/api/problem-report', json('POST', { category, message: message.trim(), email: email.trim(), page: where }));
			ui.reportOpen = false;
			toast.success(answer.message || 'Thanks. Your report was sent.');
		} catch (problem) {
			error = problem instanceof ApiError ? problem.message : 'The report could not be sent. Check your connection and try again.';
		} finally {
			busy = false;
		}
	}
</script>

<Dialog bind:open={ui.reportOpen}>
	<DialogContent class="sm:max-w-lg">
		<DialogHeader>
			<DialogTitle>Report a problem</DialogTitle>
			<DialogDescription>
				Tell the team what went wrong. They see your message, the page you are on{auth.user ? ', and your name and account email' : ''}, so they can look into it.
			</DialogDescription>
		</DialogHeader>
		<form onsubmit={submit} novalidate class="grid gap-4">
			<div class="grid gap-1.5">
				<Label for="report-kind">What is it about?</Label>
				<Select.Root type="single" bind:value={category}>
					<Select.Trigger id="report-kind" class="w-full">{label(category)}</Select.Trigger>
					<Select.Content>
						{#each REPORT_CATEGORIES as [key, text] (key)}<Select.Item value={key} label={text}>{text}</Select.Item>{/each}
					</Select.Content>
				</Select.Root>
			</div>
			<div class="grid gap-1.5">
				<Label for="report-message">What happened?</Label>
				<Textarea
					id="report-message"
					rows={5}
					maxlength={REPORT_MAX}
					placeholder="For example: I pressed Check on a Shopee product and the box said it was done, but no report opened."
					bind:value={message}
					aria-invalid={error ? true : undefined}
					aria-describedby="report-help"
				/>
				<p id="report-help" class="text-muted-foreground flex justify-between gap-3 text-xs">
					<span>At least {REPORT_MIN} characters.</span>
					<span class="tabular-nums" aria-live="off">{message.length} / {REPORT_MAX}</span>
				</p>
			</div>
			<div class="grid gap-1.5">
				<Label for="report-email">Your email (optional)</Label>
				<Input id="report-email" type="email" autocomplete="email" maxlength={REPORT_EMAIL_MAX} placeholder="So the team can write back" bind:value={email} />
			</div>
			{#if where}<p class="text-muted-foreground text-xs">Sent with this page: <span class="font-mono break-all">{where}</span></p>{/if}
			{#if error}<p class="text-destructive text-sm" role="alert">{error}</p>{/if}
			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (ui.reportOpen = false)} disabled={busy}>Cancel</Button>
				<Button type="submit" disabled={busy}>{#if busy}<Spinner />{/if} Send report</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>
