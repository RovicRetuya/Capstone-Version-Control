import { goto } from '$app/navigation';
import { page } from '$app/state';
import { toast } from 'svelte-sonner';
import { api, ApiError, json } from '#lib/api.js';
import { reportHrefFor } from '#lib/nav.js';
import {
	isShortLink,
	LAZADA_ONLY,
	linkFrom,
	linkIdentity,
	listingId,
	queryContext,
	refusalFor,
	safeLink,
	scannable,
	searchProducts,
	view,
	viaExtension
} from '#lib/product.js';
import type { Job, Marketplace } from '#lib/types.js';
import { auth } from './auth.svelte.js';
import { catalog } from './catalog.svelte.js';
import { library } from './library.svelte.js';
import { prefs } from './prefs.svelte.js';
import { ui } from './ui.svelte.js';

/** What Home and the bell show about the latest scan. "attention" means we lost contact with it. */
export interface ScanSummary extends Partial<Omit<Job, 'state'>> {
	state: 'running' | 'complete' | 'error' | 'attention';
	productLink?: string;
	resultLinks?: string[];
	resultsPending?: boolean;
	/** The finished scan's report (or its problem) has been opened, so the header no longer points at it. */
	seen?: boolean;
}

export interface Feedback {
	title: string;
	message: string;
	kind: 'error' | 'warning';
}

const STORAGE_KEY = 'defaketive-home-scan';

/** The heading of the notice shown while a scan waits for a person: the visitor, or on the public site the team. */
export const needsYouTitle = (job: { needs_team?: boolean } | null | undefined) =>
	job?.needs_team ? 'Waiting for our team' : 'This scan needs you';
const POLL_MS = 2500;

/** A scanner crash comes back as Python's own error text (file paths, a stack trace). A shopper gets a plain line instead. */
const LOOKS_TECHNICAL = /Traceback|site-packages|\.venv|Stacktrace|selenium|webdriver|chromedriver|File "|\/home\/|at 0x[0-9a-f]+/i;
const SCAN_FAILED =
	"This site couldn't read that product by itself. Install the DeFaketive browser extension, open the product page on Lazada PH or Shopee PH and press Check. Saved reports still open here.";
export const plainScanMessage = (message: string | null | undefined, fallback: string): string =>
	!message ? fallback : LOOKS_TECHNICAL.test(message) || message.length > 400 ? SCAN_FAILED : message;

/** The guest screen lives under /scan. A scan started there stays there. */
const onGuestScreen = () => page.url.pathname.startsWith('/scan');
const reportHref = (link: string) => reportHrefFor(link, onGuestScreen());
/** A scan that finished without one product to show. The app lists what it found; the guest screen has no list. */
const NOTHING_TO_OPEN: Feedback = {
	title: 'No report to open',
	message: 'The scan finished, but it did not find a product at that link. Check the link and try again.',
	kind: 'warning'
};

class Scan {
	summary = $state<ScanSummary | null>(null);
	/** True while a search request or a live scan is in flight. */
	busy = $state(false);
	elapsed = $state('0:00');
	/** A message for the Analyze page: why a scan couldn't start, or why it stopped. */
	feedback = $state<Feedback | null>(null);

	#token = 0;
	#timer: ReturnType<typeof setInterval> | null = null;

	/** Pick up a scan that was running when the page was reloaded. */
	restore() {
		try {
			const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || 'null');
			if (saved && typeof saved === 'object' && ['running', 'complete', 'error', 'attention'].includes(saved.state)) {
				this.summary = saved;
				if (saved.state === 'running' && saved.id) this.#poll(saved.id, saved);
			}
		} catch {
			/* no saved scan */
		}
	}

	/** Forget the last scan, for example when the person who ran it signs out. */
	reset() {
		this.#token += 1;
		this.#stopClock();
		this.summary = null;
		this.busy = false;
		this.feedback = null;
		try {
			sessionStorage.removeItem(STORAGE_KEY);
		} catch {
			/* nothing stored */
		}
	}

	#set(summary: ScanSummary) {
		this.summary = summary;
		try {
			sessionStorage.setItem(STORAGE_KEY, JSON.stringify(summary));
		} catch {
			/* the status lasts for this page */
		}
	}

	#startClock(createdAt?: string) {
		this.#stopClock();
		const parsed = Date.parse(createdAt || '');
		const started = Number.isNaN(parsed) ? Date.now() : parsed;
		const update = () => {
			const seconds = Math.max(0, Math.floor((Date.now() - started) / 1000));
			this.elapsed = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
		};
		update();
		this.#timer = setInterval(update, 1000);
	}

	#stopClock() {
		if (this.#timer) clearInterval(this.#timer);
		this.#timer = null;
	}

	/**
	 * Look a product up, or start a live scan. A link that was already checked opens its saved
	 * report at once; only collecting new reviews counts as a scan.
	 */
	async search(options: {
		query: string;
		marketplace: Marketplace;
		live: boolean;
		productCount: number;
		reviewCount: number;
	}) {
		if (this.busy) return;
		// The apps copy a title with a link, and a phone adds tracking to it: use the product link inside.
		let query = linkFrom(options.query);
		if (!query) return;
		if (isShortLink(query)) {
			// The Lazada app's short link names no product. Ask the server where it goes before looking anything up.
			this.busy = true;
			try {
				const data = await api<{ link: string }>(`/api/resolve-link?url=${encodeURIComponent(query)}`);
				query = data.link;
			} catch {
				this.feedback = {
					title: "Couldn't open that link",
					message: 'Open the product in your browser instead, copy its address from there, and paste it here.',
					kind: 'error'
				};
				return;
			} finally {
				this.busy = false;
			}
		}
		const context = queryContext(query);
		if (context.isUrl && !context.platform) {
			this.feedback = {
				title: 'Unsupported product link',
				message: `${LAZADA_ONLY} Paste a link to a Lazada PH product.`,
				kind: 'error'
			};
			return;
		}
		this.feedback = null;
		// Anything already analyzed opens at once, whoever scanned it: only collecting new reviews counts as a scan.
		if (!options.live && context.platform) {
			const saved = catalog.lookup(query) ?? library.mine.find((p) => linkIdentity(p.link) === linkIdentity(query));
			if (saved) return goto(reportHref(saved.link));
		}
		// A Shopee or Temu link opens a report saved from it (above), but is never scanned here. Shopee has the extension.
		if (context.platform && !scannable(context.platform)) {
			this.feedback = {
				title: viaExtension(context.platform) ? 'Check Shopee PH with the extension' : 'Lazada PH only',
				message: refusalFor(context.platform),
				kind: 'warning'
			};
			return;
		}
		if (!options.live && !context.isUrl) {
			const matches = searchProducts(catalog.browse, query);
			if (matches.length) {
				catalog.results = matches;
				return goto('/app/products');
			}
		}
		this.busy = true;
		let started = false;
		try {
			const data = await api('/api/search', json('POST', {
				query,
				platform: context.platform || options.marketplace,
				live: options.live,
				product_count: context.platform ? 1 : options.productCount,
				review_count: options.reviewCount
			}));
			// Only a guest's free-scan count changes here. It must never sign a signed-in person out.
			if (data.guest && !auth.user) auth.apply({ user: null, guest: data.guest });
			if (data.job) {
				started = true;
				this.#poll(data.job.id, data.job);
				return;
			}
			const products = data.products ?? [];
			catalog.results = products;
			if (!products.length) {
				this.feedback = {
					title: 'No saved match',
					message:
						'No saved report matched this search. Choose Collect fresh reviews to get them from the marketplace, or try another name.',
					kind: 'warning'
				};
				return;
			}
			if (context.isUrl && products.length === 1) await goto(reportHref(products[0].link));
			else await goto('/app/products');
		} catch (error) {
			const failure = error as ApiError;
			if (failure.body?.limit_reached) {
				auth.apply({ user: null, guest: failure.body.guest });
				this.feedback = { title: 'Out of free scans for today', message: failure.message, kind: 'warning' };
				// After signing in, come back to Analyze with the same link still filled in.
				ui.openAuth('signin', failure.message, '/app/analyze');
			} else {
				this.feedback = { title: 'Scan could not start', message: failure.message, kind: 'error' };
			}
		} finally {
			if (!started) this.busy = false;
		}
	}

	/**
	 * Reviews the DeFaketive browser extension collected on a Lazada product page (/check-from-extension). The
	 * server checks that they add up and analyses them; the job is then followed like a live scan's.
	 * Returns `{ failure }` (why it could not start), `{ saved }` (the product's report is recent, so the server kept
	 * it and nothing was checked: open that report), or null when it started.
	 */
	async submitCollected(
		product: Record<string, unknown>
	): Promise<{ failure: string } | { saved: { link: string; days_ago: number; keeps_for: number } } | null> {
		if (this.busy) return { failure: 'Another check is still running. Wait for it to finish, then try again.' };
		this.feedback = null;
		this.busy = true;
		let started = false;
		try {
			const data = await api('/api/extension/check', json('POST', { product }));
			if (data.existing) return { saved: data.existing };
			if (!data.job) return { failure: 'The check could not start. Please try again.' };
			started = true;
			this.#poll(data.job.id, data.job);
			return null;
		} catch (error) {
			return { failure: (error as Error).message || 'The check could not start. Please try again.' };
		} finally {
			if (!started) this.busy = false;
		}
	}

	async #poll(id: string, initial: Partial<Job> = {}) {
		const token = ++this.#token;
		this.busy = true;
		const base: ScanSummary = { ...initial, id, state: 'running' };
		this.#set(base);
		this.#startClock(initial.created_at);

		const tick = async () => {
			try {
				const update = await api<Job>(`/api/jobs/${id}`);
				if (this.#token !== token) return;
				const job: ScanSummary = { ...base, ...update, id };

				if (job.state === 'complete') {
					this.#stopClock();
					this.busy = false;
					// Keep the finished result even if refreshing the catalog fails.
					await Promise.all([catalog.load(), catalog.loadAll()]);
					const loaded = !catalog.error;
					if (!loaded) toast.warning('The scan finished, but saved results could not be refreshed. Reopen Home to try again.');
					if (this.#token !== token) return;
					// The session catalog now holds exactly what this scan collected. It goes into this person's own
					// history (their account, or this browser for a guest); the products table keeps it for everyone.
					if (loaded) library.recordScan(catalog.products);
					const direct = queryContext(job.query ?? '').isUrl;
					// Only the product that was asked for: never "the only product there is", which opened the wrong report.
					const wanted = listingId(job.query);
					const product =
						direct && loaded
							? (catalog.products.find(
									(p) => linkIdentity(p.link) === linkIdentity(job.query) || (wanted && listingId(p.link) === wanted)
								) ?? null)
							: null;
					this.#set({
						...job,
						productLink: product?.link || (direct ? safeLink(job.query) : ''),
						resultLinks: loaded ? catalog.products.map((p) => p.link).filter(safeLink) : [],
						resultsPending: !loaded
					});
					toast.success('Your report is ready.');
					prefs.notify(
						'Your DeFaketive report is ready',
						product ? `${product.name || 'Your product'}: ${view(product).headline}` : 'Open DeFaketive to read it.'
					);
					// A visitor who stayed on the Analyze page continues straight to the report.
					// Other pages keep their place and show the finished scan on Home.
					if (loaded && (page.url.pathname.endsWith('/analyze') || page.url.pathname === '/scan')) {
						if (product) await goto(reportHref(product.link));
						else if (onGuestScreen()) this.feedback = NOTHING_TO_OPEN;
						else {
							catalog.results = catalog.products;
							await goto('/app/products');
						}
					}
					return;
				}

				if (job.state === 'error') {
					this.#stopClock();
					this.busy = false;
					this.#set(job);
					this.feedback = {
						title: 'Live scan stopped',
						message: plainScanMessage(job.message, "The marketplace couldn't complete this scan."),
						kind: 'error'
					};
					prefs.notify("Your scan couldn't finish", plainScanMessage(job.message, 'Open DeFaketive to try again.'));
					return;
				}

				// The scraper opened a Chrome window for a login or a check. Say so once, wherever the person is.
				if (job.needs_you && !this.summary?.needs_you) {
					if (job.needs_team) {
						toast.warning('Your check is waiting for our team', { description: job.message });
						prefs.notify('Your DeFaketive check is waiting for our team', job.message || 'A team member has to clear a Lazada check.');
					} else {
						toast.warning('Your scan needs you', { description: job.message });
						prefs.notify('Your DeFaketive scan needs you', job.message || 'Look for the Chrome window that just opened.');
					}
				}
				this.#set(job);
				setTimeout(tick, POLL_MS);
			} catch (error) {
				if (this.#token !== token) return;
				this.#stopClock();
				this.#set({ ...(this.summary ?? base), state: 'attention', message: (error as Error).message });
				this.feedback = {
					title: 'Could not read scan progress',
					message: (error as Error).message,
					kind: 'error'
				};
			}
		};
		return tick();
	}

	/**
	 * The finished scan has been looked at: its report was opened (`link`, from the report page), or the header
	 * or Home button took the person to it. A running scan is never marked.
	 */
	markSeen(link?: string) {
		const current = this.summary;
		if (!current || current.seen || (current.state !== 'complete' && current.state !== 'error')) return;
		if (link !== undefined && (!current.productLink || linkIdentity(link) !== linkIdentity(current.productLink))) return;
		this.#set({ ...current, seen: true });
	}

	/** The Home status card's button: open the report, the results, or the scan's progress. */
	async open(): Promise<void> {
		const scan = this.summary;
		if (!scan) return;
		if (scan.state === 'complete') {
			if (scan.resultsPending) {
				await catalog.load();
				if (catalog.error) {
					toast.error('Saved results are still unavailable. Please try opening the report again shortly.');
					return;
				}
				const direct = queryContext(scan.query ?? '').isUrl;
				const product = direct
					? (catalog.products.find((p) => linkIdentity(p.link) === linkIdentity(scan.query)) ??
						(catalog.products.length === 1 ? catalog.products[0] : null))
					: null;
				this.#set({
					...scan,
					productLink: product?.link || scan.productLink,
					resultLinks: catalog.products.map((p) => p.link).filter(safeLink),
					resultsPending: false
				});
				return this.open();
			}
			this.markSeen();
			if (safeLink(scan.productLink)) return goto(reportHref(scan.productLink!));
			if (onGuestScreen()) {
				this.feedback = NOTHING_TO_OPEN;
				return;
			}
			const links = new Set(scan.resultLinks ?? []);
			catalog.results = [...catalog.products, ...catalog.all].filter((p, index, list) => links.has(p.link) && list.findIndex((other) => other.link === p.link) === index);
			return goto('/app/products');
		}
		await goto(onGuestScreen() ? '/scan' : '/app/analyze');
		if (scan.state === 'attention' && scan.id) this.#poll(scan.id, scan as Partial<Job>);
		if (scan.state === 'error') {
			this.markSeen();
			this.feedback = {
				title: 'Live scan stopped',
				message: plainScanMessage(scan.message, 'Try another product link.'),
				kind: 'error'
			};
		}
	}
}

export const scan = new Scan();
