// How the DeFaketive extension reads a Shopee PH product's reviews.
//
// The same shape of collection as collect.js (Lazada), from the review list Shopee's own product page loads
// (shopee.ph/api/v4/item/get_ratings), asked from inside the product page with the shopper's own session:
//   - the star counts from the first page (rating_count, 1 star first; sent on as 5 stars first, as collect.js does);
//   - then up to 60 written reviews (filter=1) from each star level (type=1..5), in the order 3, 2, 4, 1, 5;
//     59 per request, which is the most the list gives; at most its first 300 entries, as collect.js reads;
//   - a review is kept only when its stars are the level asked for and it has text;
//   - one request at a time, a second apart.
// If Shopee answers with a check or verification instead of reviews, collection stops and the shopper is told;
// nothing is done to get past one. Reviewers' names, ids, photos and sellers' replies are never read.
//
// This file only defines DefaketiveShopeeCollect. shopee-page.js runs it inside the product page; the tests run it
// in Node with a pretend review list (tests/extension/shopee-collect.test.mjs).
globalThis.DefaketiveShopeeCollect = (() => {
	const FEED = 'https://shopee.ph/api/v4/item/get_ratings';
	const ORDER = [3, 2, 4, 1, 5];
	const QUOTA = 60;
	const PAGE_SIZE = 59;
	const FIRST_PAGE_SIZE = 6;
	const DEPTH = 300;
	const PAUSE_MS = 1000;
	const MANILA_HOURS = 8;
	// What Shopee sends in place of reviews when it wants a check: its anti-bot error code, or a verification page.
	const CHECK_ERROR = 90309999;
	const CHECK_MARKERS = ['90309999', '/verify/', 'captcha', 'is_customer_verification_required'];

	/** {shopId, itemId} from -i.<shop>.<item> or /product/<shop>/<item>, or null. */
	function productIds(url) {
		let path;
		try {
			path = new URL(url).pathname;
		} catch {
			return null;
		}
		const found = path.match(/-i\.(\d+)\.(\d+)$/) || path.match(/^\/product\/(\d+)\/(\d+)$/);
		return found ? { shopId: found[1], itemId: found[2] } : null;
	}
	const clean = (text) =>
		String(text ?? '')
			.replace(/ /g, ' ')
			.replace(/\s+/g, ' ')
			.trim();
	const whole = (value) => {
		const parsed = Math.trunc(Number.parseFloat(value));
		return Number.isFinite(parsed) ? parsed : 0;
	};
	/** Shopee gives a review's time in seconds; DeFaketive keeps the day, in Philippine time. */
	const day = (seconds) => {
		const value = Number(seconds);
		return Number.isFinite(value) && value > 0 ? new Date((value + MANILA_HOURS * 3600) * 1000).toISOString().slice(0, 10) : '';
	};
	// star 0 is every rating; 1-5 one star level. written asks for reviews with text only.
	const feedUrl = ({ shopId, itemId }, star, offset, limit, written) =>
		`${FEED}?filter=${written ? 1 : 0}&flag=1&itemid=${itemId}&limit=${limit}&offset=${offset}&shopid=${shopId}&type=${star}`;

	/** One page of the list: {data}, or {problem: 'check' | 'unavailable'}. */
	async function readPage(fetchText, ids, star, offset, limit, written) {
		let text;
		try {
			text = String(await fetchText(feedUrl(ids, star, offset, limit, written)));
		} catch {
			return { problem: 'unavailable' };
		}
		let body = null;
		try {
			body = JSON.parse(text);
		} catch {
			/* not JSON: a check page, or an error page */
		}
		if (body && typeof body === 'object' && body.error === 0 && body.data && typeof body.data === 'object') return { data: body.data };
		if (body && body.error === CHECK_ERROR) return { problem: 'check' };
		if (CHECK_MARKERS.some((marker) => text.includes(marker))) return { problem: 'check' };
		return { problem: 'unavailable' };
	}

	/** The five star counts, 5 stars first, or null if they don't add up. */
	function starCounts(summary) {
		let counts = summary && Array.isArray(summary.rating_count) ? summary.rating_count.map(Number) : null;
		// Some answers put the total first, then 1 star to 5 stars.
		if (counts && counts.length === 6) counts = counts.slice(1);
		if (!counts || counts.length !== 5 || counts.some((count) => !Number.isInteger(count) || count < 0)) return null;
		const reported = whole(summary.rating_total);
		const sum = counts.reduce((a, b) => a + b, 0);
		if (reported && Math.abs(sum - reported) > 0.05 * reported) return null;
		return counts.reverse();
	}

	/** One entry of the list, as DeFaketive keeps it. No name, no id of the shopper, no seller reply. */
	function review(item, star) {
		return {
			comment_id: String(item.cmtid ?? ''),
			rating: whole(item.rating_star),
			source_rating_filter: star,
			time: day(item.ctime),
			content: clean(item.comment),
			variation: clean(item.product_items?.[0]?.model_name),
			like_count: whole(item.like_count)
		};
	}

	/** Up to 60 written reviews of one star level, and why collection of that level stopped. */
	async function collectLevel({ fetchText, sleep, ids, star, listed, onCount }) {
		const collected = [];
		const seen = new Set();
		let stop = '';
		let offset = 0;
		while (!stop) {
			if (offset) await sleep(PAUSE_MS);
			const { data, problem } = await readPage(fetchText, ids, star, offset, PAGE_SIZE, true);
			if (problem) return { problem };
			const items = Array.isArray(data.ratings) ? data.ratings : [];
			for (const item of items) {
				if (!item || typeof item !== 'object') continue;
				const entry = review(item, star);
				if (entry.rating !== star || !entry.content || !/^\d+$/.test(entry.comment_id)) continue;
				if (seen.has(entry.comment_id)) continue;
				seen.add(entry.comment_id);
				collected.push(entry);
				if (collected.length >= QUOTA) {
					stop = 'target_reached';
					break;
				}
			}
			onCount?.(collected.length);
			offset += items.length;
			if (stop) break;
			if (!items.length || offset >= listed) stop = 'feed_ended';
			else if (offset >= DEPTH) stop = 'feed_limit';
		}
		return { reviews: collected, stop };
	}

	/**
	 * Every review DeFaketive needs from a product page.
	 *   fetchText(url) -> the answer's text (the page's own fetch, with the shopper's session)
	 *   sleep(ms), onStep({step, star?, collected?}) for the progress panel
	 * Returns {status: 'ok', ratings, levels, reviews} or {status: 'not_a_product' | 'check' | 'unavailable' |
	 * 'no_ratings' | 'no_written_reviews'}. ratings.scores is 5 stars first, as collect.js gives it.
	 */
	async function collect({ url, fetchText, sleep = (ms) => new Promise((done) => setTimeout(done, ms)), onStep = () => {} }) {
		const ids = productIds(url);
		if (!ids) return { status: 'not_a_product' };
		onStep({ step: 'ratings' });
		const first = await readPage(fetchText, ids, 0, 0, FIRST_PAGE_SIZE, false);
		if (first.problem) return { status: first.problem };
		const summary = first.data.item_rating_summary;
		const counts = starCounts(summary);
		if (!counts) return { status: 'unavailable' };
		const listed = { 1: counts[4], 2: counts[3], 3: counts[2], 4: counts[1], 5: counts[0] };
		if (!counts.some(Boolean)) return { status: 'no_ratings' };

		const levels = {};
		const reviews = [];
		let done = 0;
		for (const star of ORDER) {
			if (!listed[star]) {
				levels[star] = { stop_reason: 'none_listed' };
				done += 1;
				continue;
			}
			onStep({ step: 'level', star, done, collected: reviews.length });
			await sleep(PAUSE_MS);
			const result = await collectLevel({
				fetchText,
				sleep,
				ids,
				star,
				listed: listed[star],
				onCount: (count) => onStep({ step: 'level', star, done, collected: reviews.length + count })
			});
			if (result.problem) return { status: result.problem };
			levels[star] = { stop_reason: result.stop };
			reviews.push(...result.reviews);
			done += 1;
		}
		if (!reviews.length) return { status: 'no_written_reviews' };
		// The list gives no average of its own, so it is worked out from the star counts (counts is 5 stars first).
		const total = counts.reduce((a, b) => a + b, 0);
		const average = counts.reduce((sum, count, i) => sum + count * (5 - i), 0) / total;
		return {
			status: 'ok',
			ratings: { scores: counts, average: Math.round(average * 100) / 100 },
			levels,
			reviews
		};
	}

	return { collect, productIds, clean, feedUrl, day, ORDER, QUOTA, PAGE_SIZE, DEPTH, PAUSE_MS };
})();
