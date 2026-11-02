// extension/shopee-collect.js: it reads Shopee's review list the way collect.js reads Lazada's. Run with: npm run test:extension
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { pretendShopee } from './pretend-shopee.mjs';

await import('../../extension/shopee-collect.js');
const { collect, productIds, day } = globalThis.DefaketiveShopeeCollect;

const URL_ = "https://shopee.ph/Crocs-Kids'-Baya-Clog-in-Navy-i.159408769.58117695286?sp_atk=abc";
const run = (feed, extra = {}) => {
	const pauses = [];
	const steps = [];
	return collect({ url: URL_, fetchText: feed.fetchText, sleep: async (ms) => pauses.push(ms), onStep: (s) => steps.push(s), ...extra }).then(
		(result) => ({ result, pauses, steps })
	);
};

test('finds the shop and item in either kind of Shopee address', () => {
	assert.deepEqual(productIds(URL_), { shopId: '159408769', itemId: '58117695286' });
	assert.deepEqual(productIds('https://shopee.ph/product/159408769/58117695286'), { shopId: '159408769', itemId: '58117695286' });
	assert.equal(productIds('https://shopee.ph/search?keyword=crocs'), null);
	assert.equal(productIds('not a link'), null);
	// A Mall page opened from a search names the listing its ratings belong to.
	assert.deepEqual(productIds('https://shopee.ph/Lenovo-LE302-i.768326746.55809231840?vItemId=48852265195&vShopId=1257811163'), { shopId: '1257811163', itemId: '48852265195' });
});

test('reads the star counts 1 star first and sends them 5 stars first', async () => {
	const feed = pretendShopee({ counts: [1, 0, 2, 0, 63], written: { 5: 4, 3: 1, 1: 1 } });
	const { result } = await run(feed);
	assert.equal(result.status, 'ok');
	assert.deepEqual(result.ratings.scores, [63, 0, 2, 0, 1]);
	assert.ok(Math.abs(result.ratings.average - 4.88) < 0.01);
	assert.deepEqual(result.levels, {
		1: { stop_reason: 'feed_ended' },
		2: { stop_reason: 'none_listed' },
		3: { stop_reason: 'feed_ended' },
		4: { stop_reason: 'none_listed' },
		5: { stop_reason: 'feed_ended' }
	});
	// 6 written reviews in all: the one probed product.
	assert.equal(result.reviews.length, 6);
});

test('also reads a count list with the total first', async () => {
	const feed = pretendShopee({ counts: [1, 0, 2, 0, 63], written: { 5: 4 }, summaryOf6: true });
	const { result } = await run(feed);
	assert.deepEqual(result.ratings.scores, [63, 0, 2, 0, 1]);
});

test('collects every written review of each star level in the scanner order, 59 a request, one at a time', async () => {
	const feed = pretendShopee({ counts: [3, 4, 8, 15, 400], written: { 5: 150, 4: 15, 3: 8, 2: 4, 1: 3 } });
	const { result, pauses } = await run(feed);
	assert.equal(result.status, 'ok');
	assert.deepEqual(result.levels[5], { stop_reason: 'feed_ended' });
	const perStar = Object.fromEntries([1, 2, 3, 4, 5].map((s) => [s, result.reviews.filter((r) => r.rating === s).length]));
	assert.deepEqual(perStar, { 1: 3, 2: 4, 3: 8, 4: 15, 5: 150 });
	// First the counts (type 0), then 3, 2, 4, 1, 5; the 5-star level takes three requests for its 150 reviews, then one more that comes back empty.
	assert.deepEqual(
		feed.requests.map((r) => [r.star, r.offset]),
		[[0, 0], [3, 0], [2, 0], [4, 0], [1, 0], [5, 0], [5, 59], [5, 118], [5, 150]]
	);
	assert.ok(feed.requests.every((r) => r.limit <= 59 && r.itemId === '58117695286' && r.shopId === '159408769'));
	assert.ok(feed.requests.slice(1).every((r) => r.withText));
	assert.equal(pauses.length, feed.requests.length - 1);
	assert.ok(pauses.every((ms) => ms === 1000));
});

test('keeps no names, ids or seller replies, tidies the text, and gives the day in Manila time', async () => {
	const feed = pretendShopee({ counts: [0, 0, 0, 0, 5], written: { 5: 5 } });
	const { result } = await run(feed);
	const review = result.reviews[0];
	assert.deepEqual(Object.keys(review).sort(), ['comment_id', 'content', 'like_count', 'rating', 'source_rating_filter', 'time', 'variation']);
	assert.equal(review.content, '5-star review number 0');
	assert.equal(review.variation, 'Navy,J1');
	assert.match(review.time, /^\d{4}-\d{2}-\d{2}$/);
	const text = JSON.stringify(result);
	for (const secret of ['real_person', 'Thank you po', '194742696']) assert.equal(text.includes(secret), false);
	assert.equal(day(1792222408), '2026-10-17');
	// 16:00 UTC is already the next day in Manila.
	assert.equal(day(Date.UTC(2026, 0, 1, 16) / 1000), '2026-01-02');
	assert.equal(day(0), '');
});

test('skips reviews without text', async () => {
	const feed = pretendShopee({ counts: [0, 0, 0, 0, 30], written: { 5: 30 }, blankEvery: 3 });
	const { result } = await run(feed);
	assert.equal(result.reviews.length, 20);
	assert.ok(result.reviews.every((r) => r.content && r.rating === r.source_rating_filter));
});

test('reads a long level to the end of its list', async () => {
	const feed = pretendShopee({ counts: [0, 0, 0, 0, 900], written: { 5: 900 } });
	const { result } = await run(feed);
	assert.deepEqual(result.levels[5], { stop_reason: 'feed_ended' });
	assert.equal(result.reviews.length, 900);
});

test('keeps what a list gives when Shopee cuts it short', async () => {
	const feed = pretendShopee({ counts: [0, 0, 0, 0, 900], written: { 5: 900 }, listDepth: 354 });
	const { result } = await run(feed);
	assert.deepEqual(result.levels[5], { stop_reason: 'feed_ended' });
	assert.equal(result.reviews.length, 354);
});

test('keeps a review Shopee lists twice, as a separate review', async () => {
	const feed = pretendShopee({ counts: [0, 0, 0, 0, 5], written: { 5: 5 } });
	const fetchText = async (url) => {
		const body = JSON.parse(await feed.fetchText(url));
		if (body.data.ratings) body.data.ratings = [body.data.ratings[0], ...body.data.ratings];
		return JSON.stringify(body);
	};
	const { result } = await run({ fetchText });
	assert.equal(result.reviews.length, 6);
	assert.equal(new Set(result.reviews.map((r) => r.comment_id)).size, 6);
	assert.ok(result.reviews.every((r) => /^\d+$/.test(r.comment_id)));
	assert.equal(result.skipped.repeat_id, 1);
});

test('stops at once, and keeps nothing, when Shopee asks for a check', async () => {
	for (const checkAs of ['error', 'page']) {
		const feed = pretendShopee({ counts: [0, 0, 5, 5, 40], written: { 5: 40, 4: 5, 3: 5 }, check: 3, checkAs });
		const { result } = await run(feed);
		assert.deepEqual(result, { status: 'check' });
		assert.equal(feed.requests.length, 3, 'no request after the check');
	}
});

test('says "unavailable" for an error page, a bad count, or a failed request', async () => {
	assert.equal((await run(pretendShopee({ counts: [1, 1, 1, 1, 1], written: {}, brokenAt: 1 }))).result.status, 'unavailable');
	assert.equal((await run(pretendShopee({ counts: [1, 1, 1, 1, 1], written: {}, total: 500 }))).result.status, 'unavailable');
	const failing = await collect({ url: URL_, fetchText: async () => Promise.reject(new Error('offline')), sleep: async () => {} });
	assert.equal(failing.status, 'unavailable');
});

test('says why there is nothing to check', async () => {
	assert.equal((await run(pretendShopee({ counts: [0, 0, 0, 0, 0], written: {} }))).result.status, 'no_ratings');
	assert.equal((await run(pretendShopee({ counts: [0, 0, 0, 0, 12], written: {} }))).result.status, 'no_written_reviews');
	const away = await collect({ url: 'https://shopee.ph/search?keyword=crocs', fetchText: async () => '', sleep: async () => {} });
	assert.equal(away.status, 'not_a_product');
});
