// Tests for the eight newer features: hover card, carousel, search palette, phone sheets, Undo toast,
// product photos, landing sample report, and the "/" shortcut.
import { chromium } from 'playwright-core';
import { signUp } from './_signin.mjs';
import fs from 'node:fs';

const base = process.env.BASE || 'http://localhost:5173';
const out = 'tests/e2e/shots';
fs.mkdirSync(out, { recursive: true });
const LINK = 'https://www.lazada.com.ph/products/pdp-i5246060610-s31099995054.html';

let failures = 0;
const check = (ok, what) => {
	console.log(`${ok ? 'PASS' : 'FAIL'}  ${what}`);
	if (!ok) failures += 1;
};
const settle = (page, ms = 900) => page.waitForTimeout(ms);

const LABELS = [
	{ category: 'safety', label: 'Safety problem', helper: 'x', informs_only: false },
	{ category: 'defect', label: 'Faulty or broken', helper: 'x', informs_only: false },
	{ category: 'quality', label: 'Poor quality', helper: 'x', informs_only: true },
	{ category: 'counterfeit', label: 'Possible fake', helper: 'x', informs_only: false },
	{ category: 'not_as_described', label: 'Not as advertised', helper: 'x', informs_only: true }
];
const mk = (i, state, tone, headline, counts, extra = {}) => ({
	name: `Test listing ${i} ${state.replace(/_/g, ' ')} power bank`,
	link: `https://shopee.ph/test-${i}`, price: '₱499.00', rating: 4.2, platform: ['shopee', 'lazada', 'temu'][i % 3], reviews_collected: 40,
	img: i === 2 ? 'http://127.0.0.1:9/broken.png' : '',
	analysis_date: new Date(Date.now() - i * 86400000).toISOString(),
	badge_view: {
		available: true, state, tone, headline, detail: `Detail for ${headline}.`, reviews_analyzed: 40, counts, labels: LABELS,
		badges: counts.safety ? [{ category: 'safety', label: 'Safety problem', helper: 'x', informs_only: false, mentions: counts.safety, reviews_analyzed: 40, phrase: 'x', summary: 'x', more_evidence: 0, evidence: [{ text: 'It overheated and started to smoke.', rating: 1, hazard: 'overheating or burns', highlights: [[3, 13], [29, 34]] }] }] : []
	},
	...extra
});
const fake = [
	mk(0, 'safety_warning', 'high', 'Reviewers report safety problems', { safety: 4, defect: 0, counterfeit: 0 }),
	mk(1, 'possible_counterfeit_or_defect', 'moderate', 'Reviewers report fakes or defects', { safety: 0, defect: 6, counterfeit: 3 }),
	mk(2, 'no_warning_signs', 'low', 'No warning signs found', { safety: 0, defect: 0, counterfeit: 0 }),
	mk(3, 'insufficient_evidence', 'unknown', 'Not enough reviews to judge', { safety: 0, defect: 0, counterfeit: 0 }),
	mk(4, 'no_warning_signs', 'low', 'No warning signs found', { safety: 0, defect: 0, counterfeit: 0 }),
	mk(5, 'possible_safety_issue', 'moderate', 'Some reviewers mention safety concerns', { safety: 1, defect: 0, counterfeit: 0 }),
	mk(6, 'no_warning_signs', 'low', 'No warning signs found', { safety: 0, defect: 0, counterfeit: 0 })
];
const detailFor = (p) => ({
	product: { ...p, category: 'Power banks', sentiment_summary: { sentiment_counts: { positive: 20, uncertain: 8, negative: 12 }, coverage: { reviews_listed: 40 } },
		comments: [
			{ author: 'a', rating: 1, time: '2026-09-30', content: 'It overheated and started to smoke.', sentiment_analysis: { label: 'negative', review_tags: ['safety'], sentences: [{ text_raw: 'It overheated and started to smoke.', tags: ['safety'], terms: [{ span: [3, 13], ngram: 'overheated', category: 'safety' }] }] } },
			{ author: 'b', rating: 5, time: '2026-09-20', content: 'Great, charges fast.', sentiment_analysis: { label: 'positive', review_tags: [], sentences: [] } }
		] },
	recommendations: []
});

// A pretend visitor who already opened the pretend products, so they show as their own history.
const SEED = (items) => { try { if (!localStorage.getItem('defaketive-activity')) localStorage.setItem('defaketive-activity', JSON.stringify(Object.fromEntries(items.map((p, i) => [p.link, { product: p, openedAt: Date.now() - i * 129600000 }])))); } catch {} };
const browser = await chromium.launch({ channel: 'chrome', headless: true });
async function fresh(width, height, { fakeCatalog = false, empty = false } = {}) {
	const context = await browser.newContext({ viewport: { width, height } });
	await signUp(context, base);
	if (fakeCatalog) await context.addInitScript(SEED, fake);
	const page = await context.newPage();
	if (fakeCatalog || empty) {
		await page.route('**/api/products', (r) => r.fulfill({ json: { products: empty ? [] : fake, count: empty ? 0 : fake.length } }));
		await page.route('**/api/saved/products', (r) => r.fulfill({ json: { products: empty ? [] : fake, count: empty ? 0 : fake.length } }));
		await page.route('**/api/products/detail**', (r) => {
			const link = new URL(r.request().url()).searchParams.get('link');
			const p = fake.find((x) => x.link === link);
			return p ? r.fulfill({ json: detailFor(p) }) : r.continue();
		});
		await page.route('**/api/picks', (r) => r.fulfill({ json: { products: [] } }));
	}
	return { context, page };
}

// ---- 1. Search palette (Ctrl+K) and "/" ----------------------------------------------------
{
	const { context, page } = await fresh(1280, 900);
	await page.goto(base + '/app/home', { waitUntil: 'networkidle' });
	await settle(page);
	await page.keyboard.press('Control+k');
	await page.getByRole('dialog').waitFor();
	check(await page.getByPlaceholder('Search pages and products…').isVisible(), 'Ctrl+K opens the search pop-up');
	await page.screenshot({ path: `${out}/feat_palette.png` });
	await page.keyboard.type('settings');
	await page.waitForTimeout(300);
	await page.keyboard.press('Enter');
	await page.waitForURL(/\/app\/settings/);
	check(true, 'typing "settings" and Enter opens Settings');

	await page.waitForTimeout(800);
	await page.keyboard.press('Control+k');
	await page.getByRole('dialog').waitFor();
	await page.keyboard.type('Type C');
	await page.waitForTimeout(300);
	await page.keyboard.press('Enter');
	await page.waitForURL(/\/app\/report\?link=/);
	check(true, 'searching a product name opens its report');

	await page.keyboard.press('Control+k');
	await page.getByRole('dialog').waitFor();
	await page.keyboard.press('Escape');
	await page.waitForTimeout(300);
	check(!(await page.getByRole('dialog').isVisible().catch(() => false)), 'Escape closes the pop-up');

	// "/" jumps to the scan bar.
	await page.goto(base + '/app/home', { waitUntil: 'networkidle' });
	await settle(page, 600);
	await page.keyboard.press('/');
	check(await page.evaluate(() => document.activeElement?.hasAttribute('data-scan-input')), '"/" on Home focuses the scan bar');
	await page.keyboard.type('a/b');
	check((await page.evaluate(() => document.activeElement?.value)) === 'a/b', 'typing "/" inside the bar still types a slash');

	await page.goto(base + '/app/settings', { waitUntil: 'networkidle' });
	await settle(page, 600);
	await page.keyboard.press('/');
	await page.waitForURL(/\/app\/analyze/);
	await page.waitForTimeout(500);
	check(await page.evaluate(() => document.activeElement?.id === 'search-query'), '"/" on another page opens Analyze with the bar focused');
	await context.close();
}

// ---- 2. Undo on the wishlist ---------------------------------------------------------------
{
	const { context, page } = await fresh(1280, 900);
	await page.goto(`${base}/app/report?link=${encodeURIComponent(LINK)}`, { waitUntil: 'networkidle' });
	await settle(page);
	await page.getByRole('button', { name: /^Save$/ }).click();
	await page.getByRole('button', { name: 'Undo' }).waitFor({ timeout: 5000 });
	check(true, 'saving shows a toast with Undo');
	await page.screenshot({ path: `${out}/feat_undo.png`, clip: { x: 700, y: 600, width: 580, height: 300 } });
	await page.getByRole('button', { name: 'Undo' }).click();
	await page.getByText('Undone.').first().waitFor({ timeout: 5000 });
	const wishlist = await page.evaluate(() => JSON.parse(localStorage.getItem('defaketive-wishlist') || '[]'));
	check(wishlist.length === 0, 'Undo takes the product back out of the wishlist');
	await context.close();
}

// ---- 3. Carousel and hover card, photos -----------------------------------------------------
{
	const { context, page } = await fresh(1280, 900, { fakeCatalog: true });
	await page.goto(base + '/app/home', { waitUntil: 'networkidle' });
	await settle(page, 1200);
	const next = page.getByRole('button', { name: /Show more: Recently checked/ });
	check(await next.isVisible(), 'a long row shows carousel arrows');
	const prev = page.getByRole('button', { name: /Show earlier: Recently checked/ });
	check(await prev.isDisabled(), 'the earlier arrow starts switched off');
	const before = await page.locator('[data-embla-container]').first().evaluate((el) => getComputedStyle(el).transform);
	await next.click();
	await page.waitForTimeout(1200);
	const after = await page.locator('[data-embla-container]').first().evaluate((el) => getComputedStyle(el).transform);
	check(before !== after, 'the next arrow slides the row');
	check(await prev.isEnabled(), 'the earlier arrow switches on after sliding');
	await page.screenshot({ path: `${out}/feat_carousel.png` });

	// Hover card on the first card's name.
	await prev.click();
	await page.waitForTimeout(900);
	const name = page.getByRole('link', { name: /Test listing 0/ }).first();
	await name.hover();
	await page.waitForTimeout(1100);
	check(await page.getByText('Open the report to read every review.').isVisible(), 'resting on a product shows its preview');
	check(await page.getByText('Reviewers report safety problems').nth(1).isVisible().catch(() => false) || (await page.getByText('Reviewers report safety problems').count()) > 0, 'the preview shows the result');
	await page.screenshot({ path: `${out}/feat_hovercard.png` });

	// Photos: a product with no picture and one whose picture fails both show the calm tile.
	await page.mouse.move(5, 5);
	await page.goto(base + '/app/products', { waitUntil: 'networkidle' });
	await settle(page, 1500);
	check((await page.getByText('No photo').count()) >= 7, 'products without a working photo show the "No photo" tile');
	await page.screenshot({ path: `${out}/feat_photos.png`, clip: { x: 256, y: 0, width: 1024, height: 900 } });
	await context.close();
}

// ---- 4. Real photo + viewer ----------------------------------------------------------------
{
	const { context, page } = await fresh(1280, 900);
	await page.goto(`${base}/app/report?link=${encodeURIComponent(LINK)}`, { waitUntil: 'networkidle' });
	await settle(page, 1500);
	const open = page.getByRole('button', { name: /View a larger photo/ });
	check(await open.isVisible(), 'the report photo can be opened larger');
	await open.click();
	await page.getByRole('dialog').getByRole('img').waitFor({ timeout: 5000 });
	check(true, 'the photo viewer opens');
	await page.screenshot({ path: `${out}/feat_viewer.png` });
	await page.keyboard.press('Escape');
	await context.close();
}

// ---- 5. Phone sheets -----------------------------------------------------------------------
{
	const { context, page } = await fresh(390, 844, { fakeCatalog: true });
	await page.goto(base + '/app/products', { waitUntil: 'networkidle' });
	await settle(page, 1200);
	check(await page.getByRole('button', { name: /^Filters/ }).isVisible(), 'phone: Products has a Filters button');
	check(!(await page.locator('#filter-risk').isVisible()), 'phone: the inline filters are hidden');
	await page.getByRole('button', { name: /^Filters/ }).click();
	await page.getByRole('dialog').getByText('Filter products').waitFor();
	await page.screenshot({ path: `${out}/feat_sheet_products.png` });
	await page.locator('#filter-risk-sheet').click();
	await page.getByRole('option', { name: 'Safety reports', exact: true }).click();
	await page.waitForTimeout(400);
	check(await page.getByRole('button', { name: /Show 1 product/ }).isVisible(), 'phone: choosing a filter updates the count on the sheet button');
	await page.getByRole('button', { name: /Show 1 product/ }).click();
	await page.waitForTimeout(500);
	check(await page.getByText(/1 product shown/).isVisible(), 'phone: closing the sheet leaves the filter applied');

	await page.goto(`${base}/app/report?link=${encodeURIComponent(fake[0].link)}`, { waitUntil: 'networkidle' });
	await settle(page, 1500);
	await page.getByRole('tab', { name: /Reviews/ }).click();
	await page.waitForTimeout(500);
	await page.getByRole('button', { name: /^Filters/ }).click();
	await page.getByRole('dialog').getByText('Filter reviews').waitFor();
	check(true, 'phone: the Reviews tab filters open from the bottom');
	await page.screenshot({ path: `${out}/feat_sheet_evidence.png` });
	await context.close();
}

// ---- 6. Landing: no example report, just the scan box --------------------------------------
{
	const { context, page } = await fresh(1280, 900);
	await page.goto(base + '/', { waitUntil: 'networkidle' });
	await settle(page, 1200);
	check((await page.getByText('Example report', { exact: true }).count()) === 0, 'landing shows no example report');
	check(await page.getByPlaceholder('Paste a Lazada PH link...').isVisible(), 'landing still has the scan box');
	const wide = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
	check(wide <= 1, 'landing does not scroll sideways');
	await page.screenshot({ path: `${out}/feat_landing.png` });
	await context.close();
}

await browser.close();
console.log(failures ? `\n${failures} check(s) FAILED` : '\nAll checks passed.');
process.exit(failures ? 1 : 0);
