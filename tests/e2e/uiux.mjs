// The UI/UX pass of 18 Oct 2026, part by part. Part 1: the small fixes.
// Scans are pretend (no marketplace is touched); every other call goes to the real server.
import { chromium } from 'playwright-core';
import { signUp } from './_signin.mjs';
import fs from 'node:fs';

const base = process.env.BASE || 'http://localhost:5173';
const out = 'tests/e2e/shots';
const axeSource = fs.readFileSync('node_modules/axe-core/axe.min.js', 'utf8');
fs.mkdirSync(out, { recursive: true });
// A saved Lazada report with flagged reviews and similar products (the Type C cable).
const SAVED = 'https://www.lazada.com.ph/products/pdp-i5246060610-s31099995054.html';
const NEW_LINK = 'https://www.lazada.com.ph/products/pdp-i999999-s888888.html';
const reportUrl = (link) => `${base}/app/report?link=${encodeURIComponent(link)}`;

let failures = 0;
const check = (ok, what) => {
	console.log(`${ok ? 'PASS' : 'FAIL'}  ${what}`);
	if (!ok) failures += 1;
};
const errors = [];

const real = await (await fetch(`${base}/api/saved/detail?link=${encodeURIComponent(SAVED)}`)).json();
const fresh = { ...real.product, link: NEW_LINK, name: 'Fresh scanned cable (pretend)' };
const { comments, ...freshCard } = fresh;

const browser = await chromium.launch({ channel: 'chrome', headless: true });

async function newPage({ width = 1280, height = 900, scheme = 'light' } = {}) {
	const context = await browser.newContext({ viewport: { width, height }, colorScheme: scheme });
	// The first-visit intro screen would cover the page: say it has been seen (as responsive.mjs does).
	await context.addInitScript(() => sessionStorage.setItem('splash-seen', '1'));
	await signUp(context, base);
	const page = await context.newPage();
	page.on('pageerror', (error) => errors.push(error.message));
	return { context, page };
}

/** A pretend live scan: four polls, then done. `hold` keeps it running until `release()` is called. */
async function pretendScan(page, { hold = false } = {}) {
	let polls = 0;
	let finished = false;
	let held = hold;
	await page.route('**/api/search', (route) => {
		const body = JSON.parse(route.request().postData() || '{}');
		return route.fulfill({
			status: 202,
			json: { job: { id: 'job1', state: 'running', stage: 1, stage_label: 'Collect reviews', progress: 18, message: 'Collecting…', platform: 'lazada', query: body.query, created_at: new Date().toISOString() } }
		});
	});
	await page.route('**/api/jobs/job1', (route) => {
		if (!held) polls += 1;
		const done = polls >= 4;
		if (done) finished = true;
		const stage = Math.min(3, polls + 1);
		return route.fulfill({ json: { id: 'job1', state: done ? 'complete' : 'running', stage, stage_label: 'x', progress: done ? 100 : [18, 68, 92][stage - 1], message: done ? 'Analysis complete — 1 product(s) found.' : 'Collecting…', platform: 'lazada', query: NEW_LINK, created_at: new Date().toISOString() } });
	});
	await page.route('**/api/products', (route) => (finished ? route.fulfill({ json: { products: [freshCard], count: 1 } }) : route.continue()));
	await page.route('**/api/saved/detail**', (route) =>
		new URL(route.request().url()).searchParams.get('link') === NEW_LINK ? route.fulfill({ json: { product: fresh, recommendations: [] } }) : route.continue()
	);
	return { release: () => (held = false) };
}

// The app's own header (pages have <header> elements of their own).
const appHeader = (page) => page.locator('header.sticky');
const pill = (page) => appHeader(page).getByRole('button', { name: /Scanning…|Report ready|Scan stopped|needs you|Waiting for our team|Check progress/ });

// ---- 1. Report: tab labels in one piece, the result's first line, the numbers under it ----
{
	const { context, page } = await newPage();
	await page.goto(reportUrl(SAVED), { waitUntil: 'networkidle' });
	await page.locator('[aria-label="Result"]').waitFor({ timeout: 15000 });
	await page.waitForTimeout(1500);
	const gaps = await page.evaluate(() =>
		[...document.querySelectorAll('[data-slot="tabs-trigger"]')].slice(1).map((tab) => {
			const label = tab.textContent.replace(/\s+/g, ' ').trim();
			const inner = tab.querySelector('span span');
			const text = [...(tab.querySelector('span')?.childNodes ?? [])].find((node) => node.nodeType === 3);
			if (!inner || !text) return { label, gap: 99 };
			const range = document.createRange();
			range.selectNodeContents(text);
			return { label, gap: Math.round(inner.getBoundingClientRect().left - range.getBoundingClientRect().right) };
		})
	);
	check(gaps.length === 2 && gaps.every((tab) => tab.gap >= 0 && tab.gap <= 6), `tab labels read in one piece (${gaps.map((tab) => `"${tab.label}" gap ${tab.gap}px`).join(', ')})`);
	check(/^Reviews · \d+ flagged$/.test(gaps[0]?.label ?? '') && /^Similar products( · \d+)?$/.test(gaps[1]?.label ?? ''), 'tab labels say "Reviews · N flagged" and "Similar products · N"');
	check(!(await page.getByText(/^Report ready ·/).count()), 'no "Report ready · N reviews analyzed" line above the report');
	const terms = await page.locator('dl', { hasText: 'Report date' }).first().locator('dt').allInnerTexts();
	check(terms.includes('Flagged reviews') && !terms.includes('Category'), `"Flagged reviews" replaces "Category" (${terms.slice(0, 4).join(', ')})`);
	check(!(await page.getByRole('button', { name: /No scans running/ }).count()), 'no greyed-out bell in the header');
	check(!(await pill(page).count()), 'no scan pill when there is no scan');
	await page.screenshot({ path: `${out}/uiux_report_top.png` });
	await context.close();
}
{
	const { context, page } = await newPage({ width: 390, height: 844 });
	await page.goto(reportUrl(SAVED), { waitUntil: 'networkidle' });
	await page.locator('[aria-label="Result"]').waitFor({ timeout: 15000 });
	await page.waitForTimeout(1500);
	const line = await page.locator('[aria-label="Result"] .verdict-step').first().evaluate((el) => el.getBoundingClientRect().height);
	check(line < 32, `phone: the result's first line stays on one line (${Math.round(line)}px)`);
	check((await page.locator('[aria-label="Result"]').textContent()).includes('What reviewers report'), 'phone: "What reviewers report" is still there for screen readers');
	check((await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)) <= 1, 'phone: the report does not scroll sideways');
	await page.screenshot({ path: `${out}/uiux_report_phone.png` });
	await context.close();
}

// ---- 2. The scan pill: there while a scan runs, "Report ready" after, gone once the report is opened ----
{
	const { context, page } = await newPage();
	const scan = await pretendScan(page, { hold: true });
	await page.goto(base + '/app/analyze', { waitUntil: 'networkidle' });
	await page.locator('#search-query').fill(NEW_LINK);
	await page.getByRole('button', { name: /Check this Lazada PH product/ }).click();
	await page.getByRole('link', { name: 'Home' }).first().click();
	await page.waitForURL(/\/app\/home/);
	await pill(page).filter({ hasText: /Scanning… \d+:\d\d/ }).waitFor({ timeout: 10000 });
	check(true, 'while a scan runs the header says "Scanning… m:ss"');
	await appHeader(page).screenshot({ path: `${out}/uiux_pill_running.png` });
	scan.release();
	await pill(page).filter({ hasText: 'Report ready' }).waitFor({ timeout: 30000 });
	check(true, 'when it finishes the header says "Report ready"');
	await appHeader(page).screenshot({ path: `${out}/uiux_pill_ready.png` });
	await page.waitForTimeout(500);
	await page.evaluate(axeSource);
	const result = await page.evaluate(() => axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } }));
	check(result.violations.length === 0, `accessibility: Home with the "Report ready" pill${result.violations.length ? ' -> ' + result.violations.map((v) => v.id + ' ' + v.nodes[0].target.join(' ')).join('; ') : ''}`);
	await pill(page).click();
	await page.waitForURL(/\/app\/report\?link=/, { timeout: 10000 });
	await page.getByRole('heading', { level: 1, name: /Fresh scanned cable/ }).waitFor({ timeout: 10000 });
	check(true, 'pressing it opens the report');
	await page.waitForTimeout(300);
	check(!(await pill(page).count()), 'once the report is open the pill goes away');
	await page.goto(base + '/app/home', { waitUntil: 'networkidle' });
	check(!(await pill(page).count()) && (await page.getByRole('heading', { name: 'Your report is ready' }).isVisible()), 'and stays away; Home still shows the finished scan card');
	await context.close();
}
{
	// Staying on Check a product: the report opens by itself, so the pill never says "Report ready".
	const { context, page } = await newPage({ width: 390, height: 844 });
	const scan = await pretendScan(page, { hold: true });
	await page.goto(base + '/app/analyze', { waitUntil: 'networkidle' });
	await page.locator('#search-query').fill(NEW_LINK);
	await page.getByRole('button', { name: /Check this Lazada PH product/ }).click();
	await pill(page).waitFor({ timeout: 10000 });
	// What shows is the short text; the full words are there for screen readers only.
	const shown = await pill(page).evaluate((button) =>
		[...button.querySelectorAll('span')].filter((span) => span.getBoundingClientRect().width > 1).map((span) => span.textContent.trim()).join(' | ')
	);
	check(/^\d+:\d\d$/.test(shown), `phone: the pill shows only the time (${shown})`);
	check(/^Scanning… \d+:\d\d/.test((await pill(page).getAttribute('title')) ?? '') && (await pill(page).textContent()).includes('Scanning…'), 'phone: the full words are still there for screen readers');
	check((await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)) <= 1, 'phone: the header with the pill does not scroll sideways');
	await appHeader(page).screenshot({ path: `${out}/uiux_pill_phone.png` });
	scan.release();
	await page.waitForURL(/\/app\/report\?link=/, { timeout: 30000 });
	await page.getByRole('heading', { level: 1, name: /Fresh scanned cable/ }).waitFor({ timeout: 10000 });
	await page.waitForTimeout(300);
	check(!(await pill(page).count()), 'a report that opened by itself leaves no pill behind');
	await context.close();
}

// ---- 3. One name per page, and the slim footer on a phone ----
{
	const { context, page } = await newPage({ width: 390, height: 844 });
	await page.goto(base + '/app/history', { waitUntil: 'networkidle' });
	check((await page.locator('h1').innerText()).trim() === 'History' && (await page.title()).startsWith('History'), 'History is called "History" (menu, title and heading)');
	await page.goto(base + '/app/settings', { waitUntil: 'networkidle' });
	await page.waitForTimeout(600);
	const footer = await page.locator('footer').evaluate((el) => el.getBoundingClientRect().height);
	check(footer < 140, `phone: the footer under Settings is short (${Math.round(footer)}px)`);
	await page.screenshot({ path: `${out}/uiux_settings_phone.png`, fullPage: true });
	await context.close();
}

// ======== Part 2: checking a product, and the extension ========

async function axe(page, label) {
	await page.waitForTimeout(1300);
	await page.evaluate(axeSource);
	const result = await page.evaluate(() => axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } }));
	check(result.violations.length === 0, `accessibility: ${label}${result.violations.length ? ' -> ' + result.violations.map((v) => v.id + ' ' + v.nodes[0].target.join(' ')).join('; ') : ''}`);
}
const ZIP = '**/downloads/defaketive-extension.zip';
const offerZip = (page) => page.route(ZIP, (route) => route.fulfill({ status: 200, contentType: 'application/zip', body: 'PK' }));

async function guestPage({ width = 1280, height = 900, scheme = 'light' } = {}) {
	const context = await browser.newContext({ viewport: { width, height }, colorScheme: scheme });
	// The first-visit intro screen would cover the page: say it has been seen (as responsive.mjs does).
	await context.addInitScript(() => sessionStorage.setItem('splash-seen', '1'));
	const page = await context.newPage();
	page.on('pageerror', (error) => errors.push(error.message));
	return { context, page };
}

// ---- 4. Check a product takes a link, with one main button ----
{
	const { context, page } = await newPage();
	await page.goto(base + '/app/analyze', { waitUntil: 'networkidle' });
	await page.waitForTimeout(800);
	const main = page.getByRole('button', { name: /^Check this/ });
	check(await main.isDisabled(), 'empty: one main button, "Check this product", switched off');
	const text = await page.evaluate(() => document.body.innerText);
	check(!/Fresh collection settings|Search saved reports|Collect fresh reviews|CAPTCHA/.test(text), 'no settings line, no second button, no CAPTCHA paragraph');
	await page.locator('#search-query').fill(NEW_LINK);
	await page.waitForTimeout(300);
	check((await page.getByRole('button', { name: 'Check this Lazada PH product' }).isEnabled()) && (await page.getByText('We read up to 200 reviews from each star level.').isVisible()), 'a new Lazada link: "Check this Lazada PH product", and how many reviews are read');
	check(!(await page.getByRole('button', { name: 'Check again for new reviews' }).isVisible()), 'a new link: nothing to check again');
	await page.screenshot({ path: `${out}/uiux_check_new.png` });
	await page.locator('#search-query').fill(SAVED);
	await page.waitForTimeout(300);
	check((await page.getByRole('button', { name: 'Open report' }).isVisible()) && (await page.getByRole('button', { name: 'Check again for new reviews' }).isVisible()), 'a known link: "Open report", and "Check again for new reviews" beside it');
	await page.locator('#search-query').fill('power bank');
	await page.waitForTimeout(300);
	const hint = page.getByRole('link', { name: /Search Products for “power bank”/ });
	check((await hint.isVisible()) && (await main.isDisabled()), 'a name: the button stays off and points to "Search Products for “power bank”"');
	await page.screenshot({ path: `${out}/uiux_check_name.png` });
	await axe(page, 'Check a product with a name typed');
	await page.locator('#search-query').press('Enter');
	await page.waitForURL(/\/app\/products\?q=power(\+|%20)bank/, { timeout: 10000 });
	await page.waitForTimeout(600);
	const shown = await page.locator('#product-search').inputValue();
	const names = await page.locator('[data-slot="card"] a[title]').evaluateAll((links) => links.map((a) => a.getAttribute('title').toLowerCase()));
	check(shown === 'power bank' && names.length > 0 && names.every((name) => name.includes('power') && name.includes('bank')), `Enter opens Products searched by that name (${names.length} found, all with both words)`);
	await page.screenshot({ path: `${out}/uiux_products_search.png` });
	// Typing and clearing keep the page answering, and the address follows the search (it froze once: 18 Oct 2026).
	const answers = () => Promise.race([page.evaluate(() => document.querySelectorAll('[data-slot="card"]').length), new Promise((r) => setTimeout(() => r(-1), 8000))]);
	await page.locator('#product-search').fill('cable');
	await page.waitForTimeout(400);
	const narrowed = await answers();
	check(narrowed > 0 && new URL(page.url()).searchParams.get('q') === 'cable', `typing "cable" narrows the list and the address follows (${narrowed} cards)`);
	await page.locator('#product-search').fill('');
	await page.waitForTimeout(400);
	const widened = await answers();
	check(widened > narrowed && !new URL(page.url()).searchParams.has('q'), `clearing it shows everything again and leaves the address (${widened} cards)`);
	await page.goto(base + '/app/analyze', { waitUntil: 'networkidle' });
	check(
		(await page.getByRole('heading', { name: 'What happens next?' }).count()) === 0,
		'Check a product has no side cards beside the link box'
	);
	// What sits below the link box: the extension, with its download and a link to the whole guide.
	const extensionCard = page.locator('section[aria-labelledby="extension-card-title"]');
	check(
		(await extensionCard.isVisible()) &&
			(await extensionCard.getByRole('link', { name: 'Read the step-by-step guide' }).getAttribute('href')) === '/app/extension',
		'Check a product shows the extension card with a link to the guide'
	);
	await context.close();
}

// ---- 5. The extension guide, public and in the app ----
{
	const { context, page } = await guestPage();
	await offerZip(page);
	await page.goto(base + '/extension', { waitUntil: 'networkidle' });
	await page.waitForTimeout(800);
	check(await page.getByRole('heading', { level: 1, name: 'How to check a Lazada or Shopee product' }).isVisible(), 'guest: /extension opens the guide');
	const download = page.getByRole('link', { name: /Download the extension/ });
	check((await download.isVisible()) && (await download.getAttribute('href')) === '/downloads/defaketive-extension.zip', 'with a .zip on the site: a download button');
	check((await page.locator('[data-slot="card"]', { hasText: 'Part 1. Install it' }).locator('ol > li').count()) === 6, 'six install steps');
	check((await page.getByText('What it reads').isVisible()) && (await page.getByText('What it never reads').isVisible()), 'what it reads and what it never reads');
	check((await page.getByRole('link', { name: 'Paste a link instead' }).getAttribute('href')) === '/scan', 'guest: "Paste a link instead" goes to the guest check');
	await page.screenshot({ path: `${out}/uiux_extension.png`, fullPage: true });
	await page.getByRole('button', { name: /chrome:\/\/extensions/ }).click();
	await page.locator('[data-sonner-toast]').filter({ hasText: 'chrome://extensions' }).first().waitFor({ timeout: 5000 });
	check(true, 'the chrome://extensions button copies it (or says to type it)');
	await axe(page, 'extension guide, light');
	await context.close();
}
{
	const { context, page } = await guestPage({ scheme: 'dark' });
	await page.goto(base + '/extension', { waitUntil: 'networkidle' });
	await page.waitForTimeout(800);
	check(!(await page.getByRole('link', { name: /Download the extension/ }).count()) && (await page.getByText('Not in the Chrome Web Store yet').isVisible()), 'without a .zip on the site: no download button, a way to ask the team instead');
	await page.screenshot({ path: `${out}/uiux_extension_none_dark.png` });
	await axe(page, 'extension guide without a download, dark');
	await context.close();
}
{
	const { context, page } = await guestPage({ width: 390, height: 844 });
	await page.goto(base + '/extension', { waitUntil: 'networkidle' });
	await page.waitForTimeout(800);
	check(await page.getByText('On a phone?').isVisible(), 'phone: the guide says first that phones cannot add extensions');
	check((await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)) <= 1, 'phone: the guide does not scroll sideways');
	await page.screenshot({ path: `${out}/uiux_extension_phone.png`, fullPage: true });
	await page.goto(base + '/app/extension', { waitUntil: 'networkidle' });
	await page.waitForURL((url) => url.pathname === '/extension', { timeout: 10000 });
	check(true, 'guest: /app/extension leads to the public guide');
	await context.close();
}
{
	const { context, page } = await newPage();
	await page.goto(base + '/extension', { waitUntil: 'networkidle' });
	await page.waitForURL(/\/app\/extension$/, { timeout: 10000 });
	await page.getByRole('heading', { level: 1, name: 'How to check a Lazada or Shopee product' }).waitFor({ timeout: 10000 });
	check(true, 'signed in: /extension opens the guide inside the app');
	check((await page.getByRole('link', { name: 'Paste a link instead' }).getAttribute('href')) === '/app/analyze', 'signed in: "Paste a link instead" goes to Check a product');
	const menu = page.locator('[data-slot="sidebar"]').getByRole('link', { name: 'Get the extension' });
	check((await menu.getAttribute('href')) === '/app/extension' && (await menu.getAttribute('data-active')) === 'true', 'the menu has "Get the extension", marked as the open page');
	check((await appHeader(page).getByText('Get the extension').count()) > 0, 'the header names the page');
	await axe(page, 'extension guide in the app');
	await context.close();
}

// ---- 6. The landing page ----
{
	const { context, page } = await guestPage();
	await page.goto(base + '/', { waitUntil: 'networkidle' });
	await page.waitForTimeout(1500);
	const hero = page.locator('section[aria-labelledby="landing-title"]');
	check((await hero.getByRole('link', { name: 'Get the extension' }).getAttribute('href')) === '/extension', 'top of the page: "Get the extension"');
	const text = await page.evaluate(() => document.body.innerText);
	check(!text.includes('Try it free') && !text.includes('No sign up required'), 'no "Try it free" (the box beside it does that) and no "No sign up required"');
	const strip = page.locator('section[aria-label="DeFaketive in numbers"]');
	const numbers = await strip.locator('dt').allInnerTexts();
	check(numbers.join(' | ') === 'Products checked | Reviews analyzed | The marketplaces we check' && (await strip.innerText()).includes('Lazada PH'), `the numbers strip: two numbers and the marketplace by name (${numbers.join(' | ')})`);
	check(!text.includes('Supported marketplace') && (await page.getByRole('heading', { level: 2, name: 'Check right on Lazada' }).isVisible()), 'the one-pill section is gone; an extension section instead');
	await page.screenshot({ path: `${out}/uiux_landing.png` });
	await page.getByRole('heading', { level: 2, name: 'Check right on Lazada' }).scrollIntoViewIfNeeded();
	await page.waitForTimeout(400);
	await page.screenshot({ path: `${out}/uiux_landing_extension.png` });
	await page.keyboard.press('Control+k');
	await page.getByRole('dialog').waitFor();
	check(await page.getByRole('option', { name: /Get the extension/ }).isVisible(), 'Ctrl+K lists "Get the extension"');
	await page.keyboard.press('Escape');
	await context.close();
}
{
	const { context, page } = await guestPage({ width: 390, height: 844 });
	await page.goto(base + '/', { waitUntil: 'networkidle' });
	await page.waitForTimeout(1000);
	check(!(await page.locator('section[aria-labelledby="landing-title"]').getByRole('link', { name: 'Get the extension' }).isVisible()), 'phone: the top of the landing page does not offer the extension');
	check((await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)) <= 1, 'phone: the landing page does not scroll sideways');
	await context.close();
}

// ---- 7. The extension hand-off page points to the guide when the extension does not answer ----
{
	const { context, page } = await guestPage();
	await page.goto(`${base}/check-from-extension?handoff=00000000-0000-4000-8000-000000000000`, { waitUntil: 'networkidle' });
	await page.getByText("The DeFaketive extension didn't answer").waitFor({ timeout: 10000 });
	check((await page.getByRole('link', { name: 'How to install the extension' }).getAttribute('href')) === '/extension', '"didn\'t answer" links to how to install it');
	await context.close();
}

// ======== The welcome tour for new accounts (20 Oct 2026) ========
async function signUpInTheDialog(page) {
	await page.goto(base + '/', { waitUntil: 'networkidle' });
	await page.waitForTimeout(800);
	await page.getByRole('button', { name: 'Create account' }).first().click();
	const form = page.getByRole('dialog');
	await form.getByLabel('Full name').fill('Tour Tester');
	await form.getByLabel('Email').fill(`tour${Date.now()}${Math.random().toString(36).slice(2, 6)}@example.com`);
	await form.getByLabel('Password', { exact: true }).fill('correct horse battery');
	await form.getByLabel('Confirm password').fill('correct horse battery');
	await form.getByRole('checkbox').check();
	await form.getByRole('button', { name: 'Create account' }).click();
}
const tour = (page) => page.locator('[data-tour]');
// Closed means gone, after the closing fade.
const tourGone = async (page) => (await tour(page).waitFor({ state: 'detached', timeout: 5000 }).then(() => true).catch(() => false));
{
	const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
	// The first-visit intro screen would cover the page: say it has been seen (as responsive.mjs does).
	await context.addInitScript(() => sessionStorage.setItem('splash-seen', '1'));
	const page = await context.newPage();
	page.on('pageerror', (error) => errors.push(error.message));
	await signUpInTheDialog(page);
	await page.waitForURL(/\/app\/home/, { timeout: 15000 });
	await tour(page).getByRole('heading', { name: 'Welcome to DeFaketive, Tour' }).waitFor({ timeout: 10000 });
	check(true, 'a new account gets the welcome tour, greeted by first name');
	check(await tour(page).getByText('Step 1 of 4').isVisible(), 'it says "Step 1 of 4"');
	await page.waitForTimeout(400);
	await page.screenshot({ path: `${out}/uiux_tour_1.png` });
	await axe(page, 'welcome tour, page 1');
	const next = tour(page).getByRole('button', { name: /^Next/ });
	const titles = [];
	for (let i = 0; i < 3; i += 1) {
		await next.click();
		await page.waitForTimeout(350);
		titles.push((await tour(page).getByRole('heading').first().innerText()).trim());
		await page.screenshot({ path: `${out}/uiux_tour_${i + 2}.png` });
	}
	check(titles.join(' | ') === 'Check a product | Read the result | Keep track of what you check', `Next walks through the pages (${titles.join(' | ')})`);
	await tour(page).getByRole('button', { name: /Back/ }).click();
	await page.waitForTimeout(350);
	const labels = await tour(page).locator('[data-slot="badge"]').allInnerTexts();
	check(labels.map((t) => t.trim()).join(' | ') === 'No warnings | Caution | Safety reports | No result yet', `Back works; the labels page shows the four labels (${labels.join(' | ')})`);
	await axe(page, 'welcome tour, the labels page');
	await next.click();
	await tour(page).getByRole('button', { name: 'Check my first product' }).click();
	await page.waitForURL(/\/app\/analyze/, { timeout: 10000 });
	check(await tourGone(page), 'the last button closes the tour and opens Check a product');
	// Shown again on request: Settings and Ctrl+K.
	await page.goto(base + '/app/settings', { waitUntil: 'networkidle' });
	await page.getByRole('button', { name: 'Show the welcome tour' }).click();
	await tour(page).getByText('Step 1 of 4').waitFor({ timeout: 5000 });
	check(true, 'Settings shows the tour again, from the first page');
	await tour(page).getByRole('button', { name: 'Skip' }).click();
	await page.waitForTimeout(300);
	check(await tourGone(page), 'Skip closes it');
	await page.keyboard.press('Control+k');
	await page.getByRole('dialog').getByRole('option', { name: /Show the welcome tour/ }).click();
	await tour(page).getByText('Step 1 of 4').waitFor({ timeout: 5000 });
	check(true, 'Ctrl+K shows it too');
	await page.keyboard.press('Escape');
	await page.waitForTimeout(300);
	check(await tourGone(page), 'Esc closes it');
	// Signing in again (not a new account) does not show it.
	await context.close();
}
{
	const context = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: 'dark' });
	// The first-visit intro screen would cover the page: say it has been seen (as responsive.mjs does).
	await context.addInitScript(() => sessionStorage.setItem('splash-seen', '1'));
	const page = await context.newPage();
	page.on('pageerror', (error) => errors.push(error.message));
	await signUpInTheDialog(page);
	await tour(page).getByText('Step 1 of 4').waitFor({ timeout: 15000 });
	for (let i = 0; i < 2; i += 1) await tour(page).getByRole('button', { name: /^Next/ }).click();
	await page.waitForTimeout(400);
	const box = await tour(page).evaluate((el) => ({ width: el.getBoundingClientRect().width, scroll: el.scrollWidth - el.clientWidth }));
	check(box.width <= 390 && box.scroll <= 1, `phone: the tour fits the screen (${Math.round(box.width)}px wide)`);
	await page.screenshot({ path: `${out}/uiux_tour_phone_dark.png` });
	await axe(page, 'welcome tour on a phone, dark');
	await context.close();
}
{
	// An existing account signing in gets no tour.
	const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
	// The first-visit intro screen would cover the page: say it has been seen (as responsive.mjs does).
	await context.addInitScript(() => sessionStorage.setItem('splash-seen', '1'));
	const { email, password } = await signUp(context, base);
	await context.clearCookies();
	const page = await context.newPage();
	await page.goto(base + '/', { waitUntil: 'networkidle' });
	await page.waitForTimeout(800);
	await page.getByRole('button', { name: 'Sign in' }).first().click();
	const form = page.getByRole('dialog');
	await form.getByLabel('Email').fill(email);
	await form.getByLabel('Password', { exact: true }).fill(password);
	await form.getByRole('button', { name: 'Sign in' }).click();
	await page.waitForURL(/\/app\/home/, { timeout: 15000 });
	await page.waitForTimeout(1200);
	check(!(await tour(page).count()), 'signing in to an existing account shows no tour');
	await context.close();
}

check(errors.length === 0, `no browser errors${errors.length ? ': ' + errors[0] : ''}`);
await browser.close();
console.log(failures ? `\n${failures} check(s) FAILED` : '\nAll checks passed.');
process.exit(failures ? 1 : 0);
