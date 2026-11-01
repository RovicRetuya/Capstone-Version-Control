// A pretend Shopee PH review list, answering the requests extension/shopee-collect.js makes, the way the real list
// answered when it was probed from a product page (shopee.ph/api/v4/item/get_ratings): `type` 0 is every rating,
// 1-5 one star level; `filter` 1 is reviews with text only; `limit` up to 59; past the end, success with no
// `ratings`; `item_rating_summary.rating_count` lists 1 star first, and there is no average in the summary. Reviews carry names, user ids and seller replies,
// which the collector must never keep.

/**
 * written: written reviews per star (the rest of `counts` are ratings without text). counts is 1 star first.
 * Options: blankEvery (every Nth review has no text), check (answer a check from this request on, as
 * 'error' or 'page'), brokenAt (answer an error page from this request on), total (override the reported total),
 * summaryOf6 (put the total first in rating_count), listDepth (entries a list gives; default no limit).
 */
export function pretendShopee({ counts, written, blankEvery = 0, check = 0, checkAs = 'error', brokenAt = 0, total, summaryOf6 = false, listDepth = Infinity } = {}) {
	const byStar = {};
	let id = 7000000000;
	for (const star of [5, 4, 3, 2, 1]) {
		byStar[star] = Array.from({ length: written[star] ?? 0 }, (_, n) => ({
			orderid: 1,
			itemid: 58117695286,
			cmtid: id++,
			ctime: n % 2 ? 1792222408 : 1780000000,
			rating_star: star,
			userid: 194742696,
			author_username: `real_person_${n}`,
			anonymous: false,
			comment: blankEvery && n % blankEvery === blankEvery - 1 ? '' : `  ${star}-star review number ${n}  `,
			product_items: [{ model_name: 'Navy,J1' }],
			ItemRatingReply: { comment: 'Thank you po!' },
			like_count: n % 4
		}));
	}
	const requests = [];
	const sum = counts.reduce((a, b) => a + b, 0);

	async function fetchText(url) {
		const query = new URL(url).searchParams;
		const star = Number(query.get('type'));
		const offset = Number(query.get('offset'));
		const limit = Number(query.get('limit'));
		const withText = query.get('filter') === '1';
		requests.push({ star, offset, limit, withText, itemId: query.get('itemid'), shopId: query.get('shopid') });
		if (check && requests.length >= check) {
			return checkAs === 'error'
				? JSON.stringify({ error: 90309999, error_msg: null, data: null, action_type: 2 })
				: '<html><body>Please verify you are human /verify/captcha</body></html>';
		}
		if (brokenAt && requests.length >= brokenAt) return '<html>Service unavailable</html>';
		let list = star === 0 ? [5, 4, 3, 2, 1].flatMap((s) => byStar[s]) : byStar[star];
		if (withText) list = list.filter((review) => review.comment);
		const page = list.slice(0, listDepth).slice(offset, offset + Math.min(limit, 59));
		const data = { item_rating_summary: { rating_total: total ?? sum, rating_count: summaryOf6 ? [sum, ...counts] : counts } };
		if (page.length) data.ratings = page;
		return JSON.stringify({ error: 0, error_msg: null, data });
	}

	return { fetchText, requests };
}
