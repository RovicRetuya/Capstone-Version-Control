// Round 10: the rest of the wording table, the report date, Home as a dashboard, and the landing page
// opening a known link straight away. Uses the real saved products (read only) and test accounts.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import { signUp } from './_signin.mjs';

const base = process.env.BASE || 'http://localhost:5173';
fs.mkdirSync('tests/e2e/shots', { recursive: true });
const axeSource = fs.readFileSync('node_modules/axe-core/axe.min.js', 'utf8');
let failures = 0;
const check = (ok, what) => {
	console.log(`${ok ? 'PASS' : 'FAIL'}  ${what}`);
	if (!ok) failures += 1;
};
const pool = await (await fetch(`${base}/api/saved/products`)).json();
const byName = (pattern) => pool.products.find((p) => pattern.test(p.name));
const CLEAN = byName(/Type C Fast Charging/i);
const CAUTION = byName(/DoubleShock/i);
// A report read partly and not by star level, with too few reviews for a result and no warning. Saved Lazada
// products were all scanned again by star level on 12 Oct 2026, so this is a Temu one.
const FEW = byName(/wireless earphones true wireless earphones/i);
const report = (p, guest = false) => `${base}${guest ? '/scan' : '/app'}/report?link=${encodeURIComponent(p.link)}`;

const browser = await chromium.launch({ channel: 'chrome', headless: true });
async function open({ signedIn = true, width = 1280, height = 900, scheme = 'light' } = {}) {
	const context = await browser.newContext({ viewport: { width, height }, colorScheme: scheme });
	if (signedIn) await signUp(context, base);
	const page = await context.newPage();
	const errors = [];
	page.on('pageerror', (e) => errors.push(e.message));
	return { context, page, errors };
}
const settle = (page, ms = 1300) => page.waitForTimeout(ms);
async function openReport(page, product, guest = false) {
	await page.goto(report(product, guest), { waitUntil: 'networkidle' });
	await page.getByRole('group', { name: 'Result' }).waitFor({ timeout: 15000 });
	await settle(page, 1500);
}
const pageText = (page) => page.evaluate(() => document.body.innerText);
async function axe(page, label) {
	await page.waitForTimeout(1300);
	await page.evaluate(axeSource);
	const result = await page.evaluate(() => axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } }));
	check(result.violations.length === 0, `accessibility: ${label}${result.violations.length ? ' -> ' + result.violations.map((v) => v.id + ' ' + v.nodes[0].target.join(' ')).join('; ') : ''}`);
}

// ---- B. Every saved product now carries the date its report was made ---------------------------------
check(pool.products.every((p) => p.updated_at || p.analysis_date || p.analyzed_at), `every one of the ${pool.count} saved products has a report date`);

{
	const { context, page, errors } = await open();

	// ---- C. Home on a first visit ----
	await page.goto(base + '/app/home', { waitUntil: 'networkidle' });
	await settle(page, 1500);
	check((await page.getByRole('heading', { name: 'How it works' }).isVisible()) && (await page.getByRole('heading', { name: 'Shopping safety tips' }).isVisible()), 'Home, nothing checked yet: "How it works" and the tips are shown');
	check(await page.getByText('Check a product and anything that needs a closer look will be listed here.').isVisible(), 'Home, nothing checked yet: "Needs a look" says what will appear there');
	check((await page.getByText('Warnings by marketplace').count()) === 0, 'Home: the marketplace comparison chart is gone');

	// ---- A. Wording on a real report (a Lazada product read by star level) ----
	await openReport(page, CLEAN);
	const tabs = (await page.getByRole('tab').allInnerTexts()).map((t) => t.replace(/\s+/g, ' ').trim());
	check(tabs[0] === 'Summary' && tabs[1].startsWith('Reviews') && tabs[2].startsWith('Similar products'), `report tabs: ${tabs.join(' | ')}`);
	check((await page.getByRole('link', { name: /View on Lazada/ }).first().isVisible()) && (await page.getByText('Go to product').count()) === 0, 'the button to the listing says "View on Lazada"');
	let text = await pageText(page);
	check(/We read \d+ reviews, up to 60 from each star level\. The percentages are adjusted to reflect the listing's [\d,]+ ratings\./.test(text), 'the line about how many reviews were read is in plain words');
	check(/\(adjusted\)/.test(text) && !/weighted/i.test(text) && !/coverage\)/.test(text), 'no "weighted" and no "coverage" left; the percentages say "(adjusted)"');
	check(text.includes('We read extra low-star reviews on purpose, so the percentages are adjusted to reflect the whole listing.'), 'the sentiment card explains the adjustment in plain words');
	check(text.includes('Mixed or unclear reviews') && !/\bUncertain\b/.test(text), 'sentiment says "Mixed or unclear", not "Uncertain"');
	check((await page.getByText("Doesn't change the result").count()) === 1 && !text.includes('Informs only'), 'the two extra labels sit under one heading, "Doesn\'t change the result"');
	const reportDate = await page.evaluate(() => [...document.querySelectorAll('dl > div')].find((el) => el.querySelector('dt')?.textContent.trim() === 'Report date')?.querySelector('dd')?.textContent.trim() ?? '');
	check(/^[A-Z][a-z]{2} \d{1,2}, \d{4}$/.test(reportDate), `the report shows its date (${reportDate})`);
	await page.screenshot({ path: 'tests/e2e/shots/round10_report.png' });
	await page.getByRole('tab', { name: /Reviews/ }).click();
	await settle(page, 800);
	const filters = (await page.getByRole('group', { name: 'Filter reviews' }).getByRole('radio').allInnerTexts()).map((t) => t.trim().replace(/ · \d+$/, ''));
	check(filters.join(' | ') === 'All | Flagged | Negative | Mixed or unclear | Positive', `review filters: ${filters.join(' | ')}`);
	await axe(page, 'report, Reviews tab');

	// A product whose collection was not by star level: "N of M". Opened in another account, so this account's Home
	// only holds the products it is meant to (since the re-check of 18 Oct 2026 this one carries a safety mention).
	{
		const other = await open();
		await openReport(other.page, FEW);
		text = await pageText(other.page);
		check(/We read 15 of this listing's 377 reviews\./.test(text), 'a partly read listing says "We read 15 of this listing\'s 377 reviews."');
		const fewDate = await other.page.evaluate(() => [...document.querySelectorAll('dl > div')].find((el) => el.querySelector('dt')?.textContent.trim() === 'Report date')?.querySelector('dd')?.textContent.trim() ?? '');
		check(/^[A-Z][a-z]{2} \d{1,2}, \d{4}$/.test(fewDate), `a re-checked product shows its date too (${fewDate})`);
		errors.push(...other.errors);
		await other.context.close();
	}

	// ---- C. Home after checking one product with no warnings ----
	await page.goto(base + '/app/home', { waitUntil: 'networkidle' });
	await settle(page, 1500);
	// One report was opened: the clean one. It has no warning.
	check(await page.getByText('Nothing needs a look right now.').isVisible(), `Home, no warnings among the checked products: "Nothing needs a look right now." (${(await page.locator('[aria-labelledby="attention-title"]').innerText()).replace(/\s+/g, ' ').slice(0, 160)})`);
	check(await page.getByText('No warning is not proof that a product is safe.').isVisible(), 'and it adds that no warning is not proof of safety');
	check((await page.getByRole('heading', { name: 'How it works' }).count()) === 0 && (await page.getByRole('heading', { name: 'Shopping safety tips' }).count()) === 0, 'Home, once something is checked: the explainers give way to the results');

	// ---- C. Home after checking a product with a warning ----
	await openReport(page, CAUTION);
	await page.goto(base + '/app/home', { waitUntil: 'networkidle' });
	await settle(page, 1800);
	const look = page.locator('[aria-labelledby="attention-title"]');
	const names = await look.locator('article a[title]').evaluateAll((els) => els.map((el) => el.getAttribute('title')));
	check(names.length === 1 && names[0] === CAUTION.name, `"Needs a look" lists the product with a warning (${names.join(' | ')})`);
	check(await look.getByText('1 of the 2 products you checked has a warning. Most serious first.').isVisible(), `it says how many of the checked products have a warning (${(await look.locator('p').first().textContent())?.trim()})`);
	check((await look.getByRole('link', { name: 'Caution · 1' }).getAttribute('href')) === '/app/history?filter=caution', 'its "See all" link opens History on that group');
	const order = await page.evaluate(() => {
		const top = (selector) => document.querySelector(selector)?.getBoundingClientRect().top ?? -1;
		return { input: top('[data-scan-input]'), stats: top('dl[aria-label="Your activity in numbers"]'), look: top('[aria-labelledby="attention-title"]'), overview: top('[aria-label="Overview of your checked products"]'), recent: top('section[aria-labelledby="recent-title"]') };
	});
	check(order.input < order.stats && order.stats < order.look && Math.abs(order.look - order.overview) < 4 && order.look < order.recent, 'Home order: link box, numbers, "Needs a look" beside the overview, then recently checked');
	await page.screenshot({ path: 'tests/e2e/shots/round10_home.png', fullPage: true });
	await axe(page, 'Home as a dashboard');

	// ---- A. History counts products, not scans ----
	await page.goto(base + '/app/history', { waitUntil: 'networkidle' });
	await settle(page, 1500);
	text = await pageText(page);
	check(text.includes('Products checked') && !text.includes('Total scans'), 'History: the first number is "Products checked"');
	check(/\b2 products\b/.test(text) && text.includes('Showing 2 of 2 products · Your 100 most recent are kept'), 'History: the day and the footer count products');

	// ---- A. The check page ----
	await page.goto(base + '/app/analyze', { waitUntil: 'networkidle' });
	await settle(page, 1000);
	await page.locator('#search-query').fill(CLEAN.link);
	await page.waitForTimeout(400);
	check((await page.getByRole('button', { name: 'Open report' }).isVisible()) && (await page.getByRole('button', { name: 'Check again for new reviews' }).isVisible()), 'check page, a known link: "Open report" and "Check again for new reviews"');
	check((await page.getByText('View saved report').count()) === 0 && (await page.getByText('Refresh with new reviews').count()) === 0, 'the old button names are gone');

	// ---- D. Signed in, the landing page still stops on the check page (it also offers to check again) ----
	await page.goto(base + '/', { waitUntil: 'networkidle' });
	await settle(page, 1200);
	await page.getByPlaceholder('Paste a Lazada PH link...').fill(CLEAN.link);
	await page.getByRole('button', { name: 'Check', exact: true }).click();
	await page.waitForURL(/\/app\/analyze\?q=/, { timeout: 10000 });
	await settle(page, 700);
	check(await page.getByRole('button', { name: 'Check again for new reviews' }).isVisible(), 'signed in, a known link pasted on the landing page opens the check page with both choices');
	check(errors.length === 0, `no browser errors signed in${errors.length ? ': ' + errors[0] : ''}`);
	await context.close();
}

// ---- Guest: sign-up wording, the guest screen's button, the guest report ---------------------------------
{
	const { context, page, errors } = await open({ signedIn: false });
	await page.goto(base + '/', { waitUntil: 'networkidle' });
	await settle(page, 1200);
	check((await pageText(page)).includes('sorts each review as positive, negative, or mixed or unclear.'), 'landing: the sentiment line says "mixed or unclear", not "neutral"');
	await page.getByRole('button', { name: 'Create account' }).first().click();
	await page.getByRole('dialog').waitFor();
	check(await page.getByRole('dialog').getByText('Free account: unlimited scans, saved history, a wishlist.').isVisible(), 'sign-up pop-up says what an account gives');
	await page.keyboard.press('Escape');
	await page.goto(base + '/scan', { waitUntil: 'networkidle' });
	await settle(page, 900);
	await page.locator('#guest-query').fill(CLEAN.link);
	await page.waitForTimeout(400);
	check(await page.getByRole('button', { name: 'Open report' }).isVisible(), 'guest screen, a known link: the button says "Open report"');
	await openReport(page, CLEAN, true);
	check(await page.getByRole('link', { name: /View on Lazada/ }).first().isVisible(), 'guest report: "View on Lazada"');
	check(errors.length === 0, `no browser errors as a guest${errors.length ? ': ' + errors[0] : ''}`);
	await context.close();
}

// ---- Dark, and a phone ----
{
	const { context, page } = await open({ scheme: 'dark' });
	await openReport(page, CAUTION);
	await page.goto(base + '/app/home', { waitUntil: 'networkidle' });
	await settle(page, 1800);
	await axe(page, 'Home as a dashboard, dark');
	await context.close();
}
{
	const { context, page } = await open({ width: 390, height: 844 });
	await openReport(page, CAUTION);
	check((await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)) <= 1, 'phone: the report does not scroll sideways');
	await page.goto(base + '/app/home', { waitUntil: 'networkidle' });
	await settle(page, 1800);
	const stacked = await page.evaluate(() => {
		const top = (selector) => document.querySelector(selector)?.getBoundingClientRect().top ?? -1;
		return top('[aria-labelledby="attention-title"]') < top('[aria-label="Overview of your checked products"]');
	});
	check(stacked && (await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)) <= 1, 'phone: "Needs a look" sits above the overview, and Home does not scroll sideways');
	await page.screenshot({ path: 'tests/e2e/shots/round10_home_phone.png', fullPage: true });
	await context.close();
}

await browser.close();
console.log(failures ? `\n${failures} check(s) FAILED` : '\nAll checks passed.');
process.exit(failures ? 1 : 0);
