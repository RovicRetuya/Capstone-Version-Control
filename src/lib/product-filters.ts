// The two choices on the Products page, "Filter by result" and "Order by". The admin decides which choices appear and
// which one is picked first (admin_api.py, the admin page's Filters tab); this file names them for both screens.
import { GROUP_NAMES, type ConcernFilter } from './product.js';

export type SortKey = 'fewest' | 'most' | 'reviews';

export const SHOW_LABEL = 'Filter by result';
export const SORT_LABEL = 'Order by';

/** Every result choice, in the order the page lists them. The same four group names as everywhere else, plus both warning groups together. */
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

/** What the page offers: the choices that are on, and the one picked first. */
export interface FilterChoices {
	show: { enabled: ConcernFilter[]; default: ConcernFilter };
	sort: { enabled: SortKey[]; default: SortKey };
}

/** Every choice on, starting at "All products" ordered by fewest problems: how the page was before the admin could change it. */
export const ALL_CHOICES: FilterChoices = {
	show: { enabled: SHOW_CHOICES.map(([key]) => key), default: 'all' },
	sort: { enabled: SORT_CHOICES.map(([key]) => key), default: 'fewest' }
};

/** What the first line under the title says, from the order the admin starts with. */
export const ORDER_SENTENCE: Record<SortKey, string> = {
	fewest: 'Products with the fewest reported problems appear first.',
	most: 'Products with the most reported problems appear first.',
	reviews: 'Products with the most reviews analyzed appear first.'
};
