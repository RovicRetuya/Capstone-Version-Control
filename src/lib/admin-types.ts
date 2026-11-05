// What the server's admin routes answer (admin_api.py).
import type { FilterChoices } from './product-filters.js';

/** The signed-in admin, or null. */
export interface AdminMe {
	admin: { id: number; name: string; email: string } | null;
	/** Why this admin was just signed out (the session ended, the account is gone). */
	notice?: string;
}

/** One account as the admin app lists it. Never a password, and never which products it holds. */
export interface AdminAccount {
	id: number;
	name: string;
	email: string;
	/** When the account was made (ISO). */
	joined: string;
	admin: boolean;
	/** The signed-in admin's own account. */
	you: boolean;
	/** The main admin, Admin@defake.com. */
	main: boolean;
	/** Products in its History, items in its Wishlist, and new checks it started today. */
	history: number;
	wishlist: number;
	checks_today: number;
}

export interface AdminAccounts {
	accounts: AdminAccount[];
	/** Every account and every admin, whatever the search. */
	total: number;
	admins: number;
}

/** New checks a day: for the whole site, for each account, and for each internet connection guests use. */
export interface DailyLimits {
	site: number;
	account: number;
	network: number;
}

export interface AdminLimits {
	limits: DailyLimits;
	/** The numbers the server starts with when no admin has saved any. */
	defaults: DailyLimits;
	site_used_today: number;
	max: number;
}

/** What the Products page offers (the admin's choice), and the full set it starts from. See product-filters.ts for the names. */
export interface AdminFilters {
	filters: FilterChoices;
	defaults: FilterChoices;
}

/** One problem report, as the admin reads it. */
export interface AdminReport {
	id: number;
	/** When it was sent (SQLite's UTC text; problem-report.ts reportTime shows it). */
	created_at: string;
	category: string;
	/** The category in words, as the person picked it. */
	label: string;
	message: string;
	/** The email the person gave to be written back at; '' when they gave none. */
	email: string;
	/** The page they were on. */
	page: string;
	status: 'new' | 'done';
	/** Their account, or null for a guest. */
	user: { name: string; email: string } | null;
}

export interface AdminReports {
	reports: AdminReport[];
	/** Every report, whatever the list is narrowed to. */
	counts: { new: number; done: number; total: number };
}

/** One "Forgot password" request. The password the person typed is never kept: only whether it matched the account's. */
export interface AdminPasswordRequest {
	id: number;
	created_at: string;
	/** What the person typed as the name and the email on the account. */
	name: string;
	email: string;
	/** Where the new password should be sent. */
	send_to: string;
	status: 'new' | 'done';
	handled_at: string | null;
	/** An account has that email, the name typed is its name, and the remembered password was its password. */
	account_found: boolean;
	name_matches: boolean;
	password_matched: boolean;
}

export interface AdminPasswordRequests {
	requests: AdminPasswordRequest[];
	counts: { new: number; done: number; total: number };
}

/** What the admin gets back after setting a new password: shown once. */
export interface AdminPasswordReset {
	id: number;
	password: string;
	emailed: boolean;
	send_to: string;
	name: string;
}

/** One saved product, as the admin's Products list shows it. */
export interface AdminProduct {
	link: string;
	name: string;
	platform: string;
	price: string | number | null;
	rating: number | null;
	review_count: number | null;
	result: string;
	reviews_read: number | null;
	reviews_listed: number | null;
	/** How it got here (the site's own scan, the extension, or the starter set). */
	source: string;
	saved: string;
}

export interface AdminProducts {
	products: AdminProduct[];
	/** Every saved product, whatever the list is narrowed to, and the count for each marketplace. */
	total: number;
	platforms: Record<string, number>;
	shown: number;
}
