import type {
	ActivityEntry,
	BadgeView,
	Category,
	Marketplace,
	Product,
	Review,
	SafetyCheckAccuracy,
	Sentence,
	Term
} from './types.js';

export const MARKETPLACES: Record<Marketplace, string> = {
	shopee: 'Shopee PH',
	lazada: 'Lazada PH',
	temu: 'Temu PH'
};

/**
 * The marketplaces DeFaketive scans from a pasted link: Lazada PH only (webapp.SCAN_PLATFORMS). Shopee PH is
 * checked through the extension instead (EXTENSION_MARKETPLACES). Shopee and Temu links are still recognised, so a
 * report saved from them still opens from its link, but a pasted link is never scanned.
 */
export const SCAN_MARKETPLACES: readonly Marketplace[] = ['lazada'];
export const scannable = (platform?: Marketplace | null): boolean => Boolean(platform) && SCAN_MARKETPLACES.includes(platform!);
export const LAZADA_ONLY = 'DeFaketive checks Lazada PH products only.';

/**
 * Shopee PH is checked only through the browser extension (extension/shopee*.js), in the shopper's own browser:
 * the site has no scanner for it. A link pasted here is answered with how to use the extension instead.
 */
export const EXTENSION_MARKETPLACES: readonly Marketplace[] = ['shopee'];
export const viaExtension = (platform?: Marketplace | null): boolean => Boolean(platform) && EXTENSION_MARKETPLACES.includes(platform!);
export const EXTENSION_ONLY = 'Shopee PH products are checked with the DeFaketive extension. Open the product on Shopee and press Check with DeFaketive.';
/** Why a pasted link of this marketplace is not scanned here. */
export const refusalFor = (platform: Marketplace): string =>
	viaExtension(platform) ? EXTENSION_ONLY : `${LAZADA_ONLY} This ${MARKETPLACES[platform]} link can't be checked.`;

/** Lazada scans read this many written reviews from each star level (webapp.LAZADA_REVIEWS_PER_STAR). */
export const LAZADA_REVIEWS_PER_STAR = 60;

/**
 * How long a live scan of one product takes, link to report. Lazada is read in the background from its review
 * feed (timed 12 Oct 2026: 63 seconds for a listing with 145 reviews, 134 for one with 298). Anything else keeps
 * the earlier figure, from one Lazada listing read off the page (11 Oct 2026: 195 seconds).
 */
const SCAN_TIMES: Partial<Record<Marketplace, string>> = { lazada: '1 to 2 minutes' };
export const typicalScanTime = (platform?: string) => SCAN_TIMES[platform as Marketplace] ?? 'about 3 minutes';

// --- The verdict ------------------------------------------------------------
// A product without a view was checked by an older model. It is shown as "not
// analyzed", never as clear: a missing result must not read as "no problems".

export const NO_VIEW: BadgeView = {
	available: false,
	state: 'not_analyzed',
	tone: 'unknown',
	headline: 'Not analyzed yet',
	detail: 'Open the report to check it with the current review model.',
	reviews_analyzed: 0,
	counts: { safety: 0, counterfeit: 0, defect: 0 },
	badges: [],
	labels: []
};

export const view = (product?: Product | null): BadgeView => product?.badge_view ?? NO_VIEW;
export const tone = (product?: Product | null) => view(product).tone || 'unknown';
export const counts = (product?: Product | null) => ({
	safety: 0,
	counterfeit: 0,
	defect: 0,
	...(view(product).counts ?? {})
});
export const labelOf = (product: Product, category: Category) =>
	view(product).labels?.find((item) => item.category === category)?.label ?? category;

export const reviewCount = (product?: Product | null) =>
	Number(view(product).reviews_analyzed || product?.comments?.length || product?.reviews_collected || 0) || 0;

/** The four groups a shopper sees. They are words, not a score. */
export type ChipKind = 'safety' | 'caution' | 'clear' | 'unknown';

/**
 * One name for each group, used everywhere it is named: chips on cards, filters, charts, numbers and the legend.
 * The sentence under a chip (the verdict headline) is the server's and says why.
 */
export const GROUP_NAMES: Record<ChipKind, string> = {
	clear: 'No warnings',
	caution: 'Caution',
	safety: 'Safety reports',
	unknown: 'No result yet'
};

/**
 * Which group a product is in. The colour follows the level the checker decided (its "tone"):
 * red is only for serious or repeated safety reports. A safety mention below that level still lifts a product
 * to Caution, so one report is never hidden behind "No warnings" or "No result yet".
 */
export function chipFor(product?: Product | null): { kind: ChipKind; label: string } {
	const t = tone(product);
	const kind: ChipKind =
		t === 'high' ? 'safety' : t === 'moderate' || counts(product).safety > 0 ? 'caution' : t === 'low' ? 'clear' : 'unknown';
	return { kind, label: GROUP_NAMES[kind] };
}

/**
 * True when a saved report was made by an earlier version of the checker. The report is still shown, as it
 * was stored; the page says so and offers to check again. Unknown (an older server) counts as up to date,
 * and a product that was never analysed already says "Not analyzed yet".
 */
export const behindChecker = (product?: Product | null) =>
	product?.checked_with_current === false && view(product).state !== 'not_analyzed';

/** True when a product is shown as Caution only because of a safety mention, not because of its verdict. */
export const liftedBySafety = (product?: Product | null) =>
	chipFor(product).kind === 'caution' && tone(product) !== 'moderate';

// Most concerning first. A safety report outranks fake and defect reports even when
// there are too few reviews for a verdict.
export function concernRank(product: Product): number {
	const t = tone(product);
	if (t === 'high') return 0;
	if (counts(product).safety > 0) return 1;
	return { moderate: 2, unknown: 3, low: 4 }[t] ?? 3;
}
export function byConcern(a: Product, b: Product): number {
	const ca = counts(a);
	const cb = counts(b);
	return (
		concernRank(a) - concernRank(b) ||
		cb.safety - ca.safety ||
		cb.counterfeit + cb.defect - (ca.counterfeit + ca.defect)
	);
}
export const needsAttention = (product: Product) =>
	['high', 'moderate'].includes(tone(product)) || counts(product).safety > 0;

/** A filter is one of the four groups, both warning groups together, or everything. */
export type ConcernFilter = 'all' | 'attention' | ChipKind;
export function matchesConcern(product: Product, filter: ConcernFilter): boolean {
	if (filter === 'all') return true;
	if (filter === 'attention') return needsAttention(product);
	return chipFor(product).kind === filter;
}

// --- Listing details --------------------------------------------------------

export const safeLink = (value: unknown): string =>
	/^https?:\/\//i.test(String(value ?? '')) ? String(value) : '';

export function safeImage(product?: Product | null): string {
	const candidate = product?.img || product?.image || product?.image_url || product?.thumbnail;
	return /^(https?:\/\/|\/static\/)/i.test(String(candidate ?? '')) ? String(candidate) : '';
}

export const money = (value?: string | null) =>
	String(value || '—').replace(/(?:PHP|Php|php)\s*|â‚±/g, '₱');

export function marketKey(product?: Product | null): Marketplace | 'other' {
	const name = String(product?.platform ?? '').toLowerCase();
	return (['shopee', 'lazada', 'temu'] as const).find((key) => name.includes(key)) ?? 'other';
}
export function platformName(product?: Product | null): string {
	const platform = product?.platform;
	if (!platform) return 'Marketplace';
	return MARKETPLACES[String(platform).toLowerCase() as Marketplace] ?? platform;
}
/** The words on a button that leaves for the listing itself: it names where it goes. */
export function listingLabel(product?: Product | null): string {
	const key = marketKey(product);
	return key === 'other' ? 'View the listing' : `View on ${MARKETPLACES[key].replace(' PH', '')}`;
}

/**
 * A listing address reduced to what names the product, so two copies of one link compare equal.
 * Host and path are enough for Shopee and Lazada (the rest is tracking). Temu gives every product the same
 * path (/goods.html), so its goods_id is part of the identity; without it all Temu listings look like one.
 */
export function linkIdentity(value: unknown): string {
	try {
		const url = new URL(String(value ?? '').trim());
		const host = url.hostname.toLowerCase().replace(/^www\./, '');
		const id = `${host}${url.pathname.replace(/\/+$/, '').toLowerCase()}`;
		const goods = host.endsWith('temu.com') ? url.searchParams.get('goods_id') : null;
		return goods ? `${id}?goods_id=${goods}` : id;
	} catch {
		return '';
	}
}

/** Find analyzed products by name without asking the server: every word that matches counts, whole phrase first. */
export function searchProducts(products: Product[], query: string, limit = 30): Product[] {
	const phrase = String(query ?? '').trim().toLowerCase();
	const terms = phrase.match(/[a-z0-9]+/g) ?? [];
	if (!terms.length) return [];
	return products
		.map((product, index) => {
			const name = String(product.name ?? '').toLowerCase();
			const overlap = terms.filter((term) => name.includes(term)).length;
			return { product, index, overlap: overlap / terms.length, exact: name.includes(phrase) ? 1 : 0, hit: overlap > 0 };
		})
		.filter((entry) => entry.hit)
		.sort((a, b) => b.exact - a.exact || b.overlap - a.overlap || a.index - b.index)
		.slice(0, limit)
		.map((entry) => entry.product);
}

/** What a pasted address is: not a link, a supported marketplace link, or a link we can't read. */
export function queryContext(value: string): { isUrl: boolean; platform: Marketplace | null } {
	let parsed: URL;
	try {
		parsed = new URL(String(value ?? '').trim());
	} catch {
		return { isUrl: false, platform: null };
	}
	if (!/^https?:$/.test(parsed.protocol)) return { isUrl: false, platform: null };
	const host = parsed.hostname.toLowerCase();
	if (host === 'shopee.ph' || host.endsWith('.shopee.ph')) return { isUrl: true, platform: 'shopee' };
	if (host === 'lazada.com.ph' || host.endsWith('.lazada.com.ph')) return { isUrl: true, platform: 'lazada' };
	if (host === 'temu.com' || host.endsWith('.temu.com')) return { isUrl: true, platform: 'temu' };
	return { isUrl: true, platform: null };
}

// --- Dates ------------------------------------------------------------------

/** When a product was last opened here, or else when it was analyzed. */
export function scanTime(product: Product, entry?: ActivityEntry): number {
	return (
		entry?.openedAt ||
		Date.parse(product.analyzed_at || product.analysis_date || product.updated_at || '') ||
		0
	);
}

export function reportDate(product: Product): string | null {
	return dateText(product.analysis_date || product.analyzed_at || product.updated_at);
}

/** A date as the screens write it ("Oct 19, 2026"), or null when there is none or it can't be read. */
export function dateText(value?: string | null): string | null {
	if (!value || Number.isNaN(Date.parse(value))) return null;
	return new Intl.DateTimeFormat('en-PH', { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value));
}

export function dayLabel(time: number): string {
	if (!time) return 'Earlier';
	const day = new Date(time);
	const today = new Date();
	const start = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
	const daysAgo = Math.round((start(today) - start(day)) / 86400000);
	if (daysAgo === 0) return 'Today';
	if (daysAgo === 1) return 'Yesterday';
	return new Intl.DateTimeFormat('en-PH', {
		month: 'short',
		day: 'numeric',
		...(day.getFullYear() === today.getFullYear() ? {} : { year: 'numeric' })
	}).format(day);
}

export const shortDate = (time: number) =>
	new Intl.DateTimeFormat('en-PH', { month: 'short', day: 'numeric' }).format(time);
export const shortTime = (time: number) =>
	new Intl.DateTimeFormat('en-PH', { hour: 'numeric', minute: '2-digit' }).format(time);

// --- People -----------------------------------------------------------------

export const firstName = (name?: string | null) => String(name ?? '').trim().split(/\s+/)[0] || '';
export function initials(name?: string | null): string {
	const parts = String(name ?? '').trim().split(/\s+/).filter(Boolean);
	if (!parts.length) return '';
	return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
}

// --- Sentiment and review evidence ------------------------------------------

export type SentimentName = 'Positive' | 'Uncertain' | 'Negative';

export function sentimentData(product: Product): { label: SentimentName; value: number }[] {
	const found = product.sentiment_summary?.sentiment_counts ?? {};
	return [
		{ label: 'Positive', value: Number(found.positive || 0) },
		{ label: 'Uncertain', value: Number(found.uncertain ?? found.neutral ?? 0) },
		{ label: 'Negative', value: Number(found.negative || 0) }
	];
}

export function sentimentPercentages(product: Product) {
	const data = sentimentData(product);
	const total = data.reduce((sum, item) => sum + item.value, 0);
	const shares = product.sentiment_summary?.sentiment_shares;
	// A per-star sample is weighted back to the listing: percentages use the shares, counts stay counts.
	if (shares) {
		return data.map((item) => ({ ...item, percent: Number(shares[item.label.toLowerCase()] || 0) * 100 }));
	}
	return data.map((item) => ({ ...item, percent: total ? (item.value / total) * 100 : 0 }));
}

export type EvidenceFilter = 'all' | 'reported' | 'negative' | 'uncertain' | 'positive';
export type ReviewSentiment = 'positive' | 'uncertain' | 'negative' | 'unanalyzed';
export function sentimentLabel(review: Review): ReviewSentiment {
	const label = String(review?.sentiment_analysis?.label ?? 'unanalyzed').toLowerCase();
	return (label === 'neutral' ? 'uncertain' : label) as ReviewSentiment;
}

const sentenceTags = (sentence?: Sentence) => [...(sentence?.tags ?? []), ...(sentence?.extra_tags ?? [])];
const sentenceTerms = (sentence?: Sentence): Term[] => [
	...(sentence?.terms ?? []),
	...(sentence?.extra_terms ?? [])
];
export const reviewTags = (review: Review): string[] => [
	...(review?.sentiment_analysis?.review_tags ?? []),
	...(review?.sentiment_analysis?.review_extra_tags ?? [])
];

/** The kinds of problem, most serious first: the three that can change the verdict, then the two that can't. */
export const CATEGORY_ORDER: Category[] = ['safety', 'defect', 'counterfeit', 'quality', 'not_as_described'];
/** Where a kind of problem sits in that order. One this app does not know goes last. */
export function categoryPlace(category: string): number {
	const place = CATEGORY_ORDER.indexOf(category as Category);
	return place < 0 ? CATEGORY_ORDER.length : place;
}
/** Where a review sorts in a list: by the most serious problem it reports. A review that reports nothing comes last. */
export const seriousness = (review: Review): number =>
	Math.min(CATEGORY_ORDER.length, ...reviewTags(review).map(categoryPlace));

/** The words the check matched in a review: only words from a label the sentence was tagged with, never a negated one. */
export function matchedWords(review: Review): Map<string, string> {
	const found = new Map<string, string>();
	for (const sentence of review?.sentiment_analysis?.sentences ?? []) {
		const tags = new Set(sentenceTags(sentence));
		for (const term of sentenceTerms(sentence)) {
			if (term.negated || !term.category || !tags.has(term.category)) continue;
			const raw = Array.isArray(term.span) ? String(sentence.text_raw ?? '').slice(term.span[0], term.span[1]) : '';
			const word = String(term.ngram || raw).trim().toLowerCase();
			if (word && !found.has(word)) found.set(word, term.category);
		}
	}
	return found;
}

/** How many reviews each warning word appears in, most common first. */
export function warningWords(reviews: Review[]) {
	const tally = new Map<string, { word: string; category: string; count: number }>();
	for (const review of reviews) {
		for (const [word, category] of matchedWords(review)) {
			const entry = tally.get(word) ?? { word, category, count: 0 };
			entry.count += 1;
			tally.set(word, entry);
		}
	}
	return [...tally.values()].sort((a, b) => b.count - a.count || a.word.localeCompare(b.word));
}

/** Split a quote into plain and highlighted pieces, using the character ranges the server sent. */
export function segments(text: string, spans: [number, number][] | undefined): { text: string; mark: boolean }[] {
	const source = String(text ?? '');
	const merged: [number, number][] = [];
	(spans ?? [])
		.map(([a, b]): [number, number] => [Math.max(0, Number(a) || 0), Math.min(source.length, Number(b) || 0)])
		.filter(([start, end]) => end > start)
		.sort((a, b) => a[0] - b[0])
		.forEach(([start, end]) => {
			const last = merged[merged.length - 1];
			if (last && start <= last[1]) last[1] = Math.max(last[1], end);
			else merged.push([start, end]);
		});
	const pieces: { text: string; mark: boolean }[] = [];
	let cursor = 0;
	for (const [start, end] of merged) {
		if (start > cursor) pieces.push({ text: source.slice(cursor, start), mark: false });
		pieces.push({ text: source.slice(start, end), mark: true });
		cursor = end;
	}
	if (cursor < source.length) pieces.push({ text: source.slice(cursor), mark: false });
	return pieces.length ? pieces : [{ text: source, mark: false }];
}

/** Split a review into plain and highlighted pieces for the words the check matched. */
export function highlightReview(review: Review): { text: string; mark: boolean }[] {
	const content = review.content || 'No written review was collected.';
	const terms = [...matchedWords(review).keys()].sort((a, b) => b.length - a.length);
	if (!terms.length) return [{ text: content, mark: false }];
	const pattern = new RegExp(`(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'ig');
	return content
		.split(pattern)
		.filter((piece) => piece !== '')
		.map((piece) => ({ text: piece, mark: terms.includes(piece.toLowerCase()) }));
}

/** How well the safety check did against reviews that two people read by hand. The figures come from the server. */
export function accuracyCopy(accuracy?: SafetyCheckAccuracy | null): string {
	const closing = 'A flagged review is a reason to read, not proof of danger, and no flags is not proof of safety.';
	if (!accuracy) return closing;
	const harmless = accuracy.flags_raised - accuracy.flags_confirmed;
	return `It is not perfect. When we tested it on ${Number(accuracy.sentences_checked).toLocaleString()} review sentences that two people had checked by hand, it caught ${accuracy.reports_caught} of ${accuracy.reports_confirmed} real safety reports, and ${harmless} of the ${accuracy.flags_raised} sentences it flagged turned out to be harmless. ${closing}`;
}

/** The same figures in one line, for the labels card on a report. */
export function accuracyBrief(accuracy?: SafetyCheckAccuracy | null): string {
	const closing = 'A flag is a reason to read, not proof.';
	if (!accuracy) return closing;
	return `In a test on ${Number(accuracy.sentences_checked).toLocaleString()} hand-checked review sentences, the check caught ${accuracy.reports_caught} of ${accuracy.reports_confirmed} real safety reports. ${closing}`;
}

// --- What each verdict means -------------------------------------------------

/** In the order the server tests them. The wording matches dashboard_utils.VERDICT_HEADLINES. */
export const VERDICT_GUIDE: { state: string; tone: string; label: string; meaning: string }[] = [
	{ state: 'safety_warning', tone: 'high', label: 'Reviewers report safety problems', meaning: 'Two or more separate reports of fire, explosion or electric shock, or safety problems that are common in the reviews' },
	{ state: 'possible_safety_issue', tone: 'moderate', label: 'Some reviewers mention safety concerns', meaning: 'One report of fire, explosion or electric shock, or a few less severe safety reports' },
	{ state: 'possible_counterfeit_or_defect', tone: 'moderate', label: 'Reviewers report fakes or defects', meaning: 'More fake or breakage reports than is typical for the product type' },
	{ state: 'reviews_may_be_unreliable', tone: 'unknown', label: 'These reviews may not be trustworthy', meaning: 'Many reviews look duplicated or generic' },
	{ state: 'no_warning_signs', tone: 'low', label: 'No warning signs found', meaning: 'Enough reviews, and no problem reaches a warning level. This is not proof that a product is safe' },
	{ state: 'insufficient_evidence', tone: 'unknown', label: 'Not enough reviews to judge', meaning: 'Too few reviews for an overall result; any reports are still shown' }
];

/** The group a verdict is shown as, before any safety mention lifts it (see chipFor). */
export const groupOfTone = (value: string): ChipKind =>
	({ high: 'safety', moderate: 'caution', low: 'clear' } as Record<string, ChipKind>)[value] ?? 'unknown';

/** The four groups, and what each one means. The order runs from calm to serious, then the one with no answer. */
export const VERDICT_GROUPS: { kind: ChipKind; label: string; meaning: string }[] = [
	{ kind: 'clear', label: GROUP_NAMES.clear, meaning: "Enough reviews and nothing at a warning level. Not proof it's safe." },
	{ kind: 'caution', label: GROUP_NAMES.caution, meaning: 'More fakes or defects than usual, or a safety concern, even from one reviewer.' },
	{ kind: 'safety', label: GROUP_NAMES.safety, meaning: 'Two or more reports of fire, explosion or shock, or safety problems that are common.' },
	{ kind: 'unknown', label: GROUP_NAMES.unknown, meaning: 'Too few reviews, reviews that may not be trustworthy, or not analyzed yet.' }
];

/** Said wherever the verdicts are listed against their groups. */
export const SAFETY_LIFT_NOTE =
	'A product with any safety mention is shown as Caution at least, whatever its result, so one report is never hidden.';
