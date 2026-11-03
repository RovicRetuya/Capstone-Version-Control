// The two choices on the Products page, "Filter by result" and "Order by". The admin decides which choices appear,
// which one is picked first, and can add options of their own (admin_api.py, the admin page's Products page tab).
// This file names the built-in choices, says how each admin-made kind is applied to a product, and is shared by the
// Products page and the admin tab.
import { GROUP_NAMES, marketKey, reviewCount, type ConcernFilter } from './product.js';
import type { Product } from './types.js';

export type SortKey = 'fewest' | 'most' | 'reviews';
/** What an admin-made filter checks. */
export type FilterKind = 'min_rating' | 'max_price' | 'min_reviews' | 'marketplace';
/** What an admin-made order sorts by. */
export type OrderField = 'rating' | 'price' | 'reviews' | 'checked' | 'name';
export type Direction = 'asc' | 'desc';

export const SHOW_LABEL = 'Filter by result';
export const SORT_LABEL = 'Order by';

/** Every built-in result choice, in the order the page lists them. The same four group names as everywhere else, plus both warning groups together. */
export const SHOW_CHOICES: [ConcernFilter, string][] = [
	['all', 'All products'],
	['attention', `${GROUP_NAMES.caution} or ${GROUP_NAMES.safety.toLowerCase()}`],
	['safety', GROUP_NAMES.safety],
	['caution', GROUP_NAMES.caution],
	['clear', GROUP_NAMES.clear],
	['unknown', GROUP_NAMES.unknown]
];

export const SORT_CHOICES: [SortKey, string][] = [
	['fewest', 'Fewest reported problems'],
	['most', 'Most reported problems'],
	['reviews', 'Most reviews analyzed']
];

/** An option the admin made up. Its id is in the list's `enabled` like a built-in choice's name. */
export interface CustomChoice {
	id: string;
	group: 'show' | 'sort';
	/** What visitors see in the list. */
	label: string;
	kind: FilterKind | OrderField;
	/** A filter's number, or its marketplace ('lazada' or 'shopee'). Orders have none. */
	value?: number | string;
	/** An order's direction. Filters have none. */
	direction?: Direction;
}

/** What the page offers: the choices that are on, the one picked first, and the options the admin added. */
export interface FilterChoices {
	show: { enabled: string[]; default: string };
	sort: { enabled: string[]; default: string };
	custom: CustomChoice[];
}

/** Every choice on, starting at "All products" ordered by fewest problems: how the page was before the admin could change it. */
export const ALL_CHOICES: FilterChoices = {
	show: { enabled: SHOW_CHOICES.map(([key]) => key), default: 'all' },
	sort: { enabled: SORT_CHOICES.map(([key]) => key), default: 'fewest' },
	custom: []
};

/** What the first line under the title says, from the built-in order the admin starts with. */
export const ORDER_SENTENCE: Record<SortKey, string> = {
	fewest: 'Products with the fewest reported problems appear first.',
	most: 'Products with the most reported problems appear first.',
	reviews: 'Products with the most reviews analyzed appear first.'
};

/** The first line under the title, for whichever order the page starts on (an admin-made one is named by its label). */
export function orderSentence(choices: FilterChoices): string {
	const start = choices.sort.default;
	const made = choices.custom.find((choice) => choice.group === 'sort' && choice.id === start);
	return made ? `Products are ordered by "${made.label}".` : (ORDER_SENTENCE[start as SortKey] ?? ORDER_SENTENCE.fewest);
}

// --- What a product has to be asked --------------------------------------------------------------------------------

/** The number in a price like "₱1,299.00" (the first one in "₱100 - ₱200"), or null when the report has no price. */
export function priceNumber(product: Product): number | null {
	const found = String(product.price ?? '').replace(/,/g, '').match(/\d+(?:\.\d+)?/);
	return found ? Number(found[0]) : null;
}

/** The listing's own star rating, or null when the report has none. */
export function ratingNumber(product: Product): number | null {
	const rating = Number(product.rating);
	return Number.isFinite(rating) && rating > 0 ? rating : null;
}

/** When the report was made, as a time (0 when unknown). */
export function checkedTime(product: Product): number {
	return Date.parse(product.analysis_date || product.analyzed_at || product.updated_at || '') || 0;
}

/** Whether a product passes an admin-made filter. A product with no price (or no rating) never passes a price (or rating) filter. */
export function customFilter(choice: CustomChoice): (product: Product) => boolean {
	const value = choice.value;
	switch (choice.kind) {
		case 'min_rating':
			return (product) => (ratingNumber(product) ?? -1) >= Number(value);
		case 'max_price':
			return (product) => {
				const price = priceNumber(product);
				return price !== null && price <= Number(value);
			};
		case 'min_reviews':
			return (product) => reviewCount(product) >= Number(value);
		case 'marketplace':
			return (product) => marketKey(product) === value;
		default:
			return () => true;
	}
}

/** The comparison an admin-made order sorts by. A product with nothing to order by goes last, whichever way it runs. */
export function customCompare(choice: CustomChoice): (a: Product, b: Product) => number {
	const way = choice.direction === 'desc' ? -1 : 1;
	const by = (read: (product: Product) => number | string | null) => (a: Product, b: Product) => {
		const x = read(a);
		const y = read(b);
		if (x === null && y === null) return 0;
		if (x === null) return 1;
		if (y === null) return -1;
		return (typeof x === 'string' && typeof y === 'string' ? x.localeCompare(y, undefined, { sensitivity: 'base' }) : Number(x) - Number(y)) * way;
	};
	switch (choice.kind) {
		case 'rating':
			return by(ratingNumber);
		case 'price':
			return by(priceNumber);
		case 'reviews':
			return by((product) => reviewCount(product));
		case 'checked':
			return by((product) => checkedTime(product) || null);
		case 'name':
			return by((product) => String(product.name ?? '').trim() || null);
		default:
			return () => 0;
	}
}

// --- What the admin's form offers -----------------------------------------------------------------------------------

export interface FilterKindInfo {
	name: string;
	/** One line under the field: what it does, and what it leaves out. */
	help: string;
	/** A number kind's bounds (the server checks the same ones); a marketplace has none. */
	min?: number;
	max?: number;
	step?: number;
	/** What goes in the field to start with. */
	example: number | string;
	/** A name for it, so the admin has a start. */
	label: (value: number | string) => string;
}

const peso = (value: number | string) => `₱${Number(value).toLocaleString('en-PH')}`;
const MARKET_NAMES: Record<string, string> = { lazada: 'Lazada PH', shopee: 'Shopee PH' };

export const FILTER_KINDS: Record<FilterKind, FilterKindInfo> = {
	min_rating: {
		name: 'Minimum star rating',
		help: "The listing's own rating, from 1 to 5. Products with no rating saved are left out.",
		min: 1,
		max: 5,
		step: 0.1,
		example: 4,
		label: (value) => `Rated ${value} stars or more`
	},
	max_price: {
		name: 'Maximum price',
		help: 'In pesos. Products whose report has no price (some Shopee ones) are left out.',
		min: 1,
		max: 10_000_000,
		step: 1,
		example: 500,
		label: (value) => `Under ${peso(value)}`
	},
	min_reviews: {
		name: 'Minimum reviews analyzed',
		help: 'How many reviews were read for the report. Keeps out thin reports.',
		min: 1,
		max: 1_000_000,
		step: 1,
		example: 100,
		label: (value) => `At least ${Number(value).toLocaleString('en-PH')} reviews read`
	},
	marketplace: {
		name: 'Marketplace',
		help: 'Only products checked on this marketplace.',
		example: 'lazada',
		label: (value) => `${MARKET_NAMES[String(value)] ?? value} only`
	}
};
export const FILTER_KIND_ORDER: FilterKind[] = ['min_rating', 'max_price', 'min_reviews', 'marketplace'];
export const MARKETPLACE_CHOICES: [string, string][] = Object.entries(MARKET_NAMES);

export interface OrderFieldInfo {
	name: string;
	/** What each direction is called, and what it makes a name in the list. */
	asc: { way: string; label: string };
	desc: { way: string; label: string };
}
export const ORDER_FIELDS: Record<OrderField, OrderFieldInfo> = {
	rating: { name: 'Star rating', asc: { way: 'Lowest first', label: 'Lowest rated' }, desc: { way: 'Highest first', label: 'Highest rated' } },
	price: { name: 'Price', asc: { way: 'Lowest first', label: 'Lowest price' }, desc: { way: 'Highest first', label: 'Highest price' } },
	reviews: { name: 'Reviews analyzed', asc: { way: 'Fewest first', label: 'Fewest reviews read' }, desc: { way: 'Most first', label: 'Most reviews read' } },
	checked: { name: 'Date checked', asc: { way: 'Oldest first', label: 'Oldest checked' }, desc: { way: 'Newest first', label: 'Newest checked' } },
	name: { name: 'Product name', asc: { way: 'A to Z', label: 'Name A to Z' }, desc: { way: 'Z to A', label: 'Name Z to A' } }
};
export const ORDER_FIELD_ORDER: OrderField[] = ['rating', 'price', 'reviews', 'checked', 'name'];

/** A start for the name of a new option. */
export function suggestedLabel(group: 'show' | 'sort', kind: FilterKind | OrderField, value: number | string, direction: Direction): string {
	if (group === 'sort') return ORDER_FIELDS[kind as OrderField][direction].label;
	return FILTER_KINDS[kind as FilterKind].label(value);
}

/** The longest name the server takes, and the most options it keeps (admin_api.py LABEL_MAX, MAX_CUSTOM). */
export const LABEL_MAX = 40;
export const MAX_CUSTOM = 20;
