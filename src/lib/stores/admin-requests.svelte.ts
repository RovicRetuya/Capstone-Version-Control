import { json } from '#lib/api.js';
import type { AdminPasswordRequests, AdminPasswordReset } from '#lib/admin-types.js';
import { adminApi } from './admin.svelte.js';

/**
 * The "Forgot password" requests (admin_api.py: GET /api/admin/password-requests), with what the admin has narrowed them to.
 * Loaded once by the admin page so the tab can say how many are new; the tab uses the same list.
 */
class PasswordRequests {
	data = $state<AdminPasswordRequests | null>(null);
	failed = $state('');
	status = $state<'new' | 'done' | 'all'>('new');
	query = $state('');
	/** The request whose button was just pressed, so it can show it is working. */
	busy = $state<number | null>(null);

	#requests = 0;

	get newCount(): number {
		return this.data?.counts.new ?? 0;
	}

	async load() {
		const id = ++this.#requests;
		this.failed = '';
		const params = new URLSearchParams({ status: this.status, q: this.query.trim() });
		try {
			const answer = await adminApi<AdminPasswordRequests>(`/api/admin/password-requests?${params}`);
			if (id === this.#requests) this.data = answer;
		} catch (error) {
			if (id === this.#requests) this.failed = (error as Error).message;
		}
	}

	/** Mark one handled without changing a password, or open it again. Throws the server's message when it can't. */
	async mark(requestId: number, status: 'new' | 'done') {
		this.busy = requestId;
		try {
			await adminApi(`/api/admin/password-requests/${requestId}`, json('PUT', { status }));
			await this.load();
		} finally {
			this.busy = null;
		}
	}

	/** Set a new password on the account, send it to the email given, and close the request. The password is returned once. */
	async reset(requestId: number): Promise<AdminPasswordReset> {
		this.busy = requestId;
		try {
			const answer = await adminApi<AdminPasswordReset>(`/api/admin/password-requests/${requestId}/reset`, json('POST'));
			await this.load();
			return answer;
		} finally {
			this.busy = null;
		}
	}
}

export const passwordRequests = new PasswordRequests();
