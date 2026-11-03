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
	/** The main admin, Admin@defake.com: it can't be deleted. */
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
