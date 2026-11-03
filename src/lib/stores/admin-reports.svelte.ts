import { json } from '#lib/api.js';
import type { AdminReports } from '#lib/admin-types.js';
import { adminApi } from './admin.svelte.js';

/**
 * The problem reports people sent (admin_api.py: GET /api/admin/reports), with what the admin has narrowed them to.
 * The admin page loads it once so the tab can say how many are new; the Reports tab uses the same list.
 */
class Reports {
	data = $state<AdminReports | null>(null);
	failed = $state('');
	/** 'new' needs a look, 'done' is handled, 'all' is both. */
	status = $state<'new' | 'done' | 'all'>('new');
	category = $state('');
	query = $state('');
	/** The report whose button was just pressed, so it can show it is working. */
	busy = $state<number | null>(null);

	#requests = 0;

	/** How many have nobody's attention yet (whatever the list is narrowed to). */
	get newCount(): number {
		return this.data?.counts.new ?? 0;
	}

	async load() {
		const id = ++this.#requests;
		this.failed = '';
		const params = new URLSearchParams({ status: this.status, category: this.category, q: this.query.trim() });
		try {
			const answer = await adminApi<AdminReports>(`/api/admin/reports?${params}`);
			if (id === this.#requests) this.data = answer;
		} catch (error) {
			if (id === this.#requests) this.failed = (error as Error).message;
		}
	}

	/** Mark one handled, or open again. Throws the server's message when it can't. */
	async mark(reportId: number, status: 'new' | 'done') {
		this.busy = reportId;
		try {
			await adminApi(`/api/admin/reports/${reportId}`, json('PUT', { status }));
			await this.load();
		} finally {
			this.busy = null;
		}
	}
}

export const reports = new Reports();
