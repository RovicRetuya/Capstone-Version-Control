// The "Report a problem" form and the admin's view of what was sent (problem_reports.py, admin_api.py).

/** What a report can be about, and what the person picks it as. The names are the ones the server accepts. */
export const REPORT_CATEGORIES: [string, string][] = [
	['wrong-result', 'A result looks wrong'],
	['scan-problem', 'A scan failed or got stuck'],
	['display-bug', 'Something looks or works broken'],
	['account', 'Sign in or account'],
	['other', 'Something else']
];

/** The server's limits (problem_reports.py MIN_MESSAGE, MAX_MESSAGE, MAX_EMAIL, MAX_PAGE). */
export const REPORT_MIN = 10;
export const REPORT_MAX = 2000;
export const REPORT_EMAIL_MAX = 200;
export const REPORT_PAGE_MAX = 300;

/** The server keeps the time as SQLite writes it ("2026-11-03 14:05:09", UTC): read it as UTC and show it as local time. */
export function reportTime(created: string): string {
	const when = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(created) ? created : `${created.replace(' ', 'T')}Z`);
	return Number.isNaN(when.getTime())
		? created
		: when.toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}
