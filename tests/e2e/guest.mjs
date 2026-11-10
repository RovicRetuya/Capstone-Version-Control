// The guest screen: a guest checks a product without ever entering the main app.
// The live scan is pretended; nothing touches a marketplace.
import { chromium } from 'playwright-core';
import { closeTour } from './_signin.mjs';
import fs from 'node:fs';

const base = process.env.BASE || 'http://localhost:5173';
fs.mkdirSync('tests/e2e/shots', { recursive: true });
const axeSource = fs.readFileSync('node_modules/axe-core/axe.min.js', 'utf8');
let failures = 0;
const check = (ok, what) => {
	console.log(`${ok ? 'PASS' : 'FAIL'}  ${what}`);
	if (!ok) failures += 1;
};
const pool = await (await fetch(`${base}/api/saved/products`)).json();
const SAVED = pool.products.find((p) => /Type C Fast Charging/i.test(p.name)) ?? pool.products[0];
const NEW_LINK = 'https://www.lazada.com.ph/products/pdp-i424242-s313131.html';
const detail = await (await fetch(`${base}/api/saved/detail?link=${encodeURIComponent(SAVED.link)}`)).json();
const fresh = { ...detail.product, link: NEW_LINK, name: 'Guest scanned this (pretend)' };
const { comments: _c, ...freshCard } = fresh;

const browser = await chromium.launch({ channel: 'chrome', headless: true });
async function open({ width = 1280, height = 900, limit = false, scheme = 'light' } = {}) {
	const context = await browser.newContext({ viewport: { width, height }, colorScheme: scheme });
	const page = await context.newPage();
	const errors = [];
	page.on('pageerror', (e) => errors.push(e.message));
	let polls = 0;
	let finished = false;
	await page.route('**/api/search', (route) => {
		const body = JSON.parse(route.request().postData() || '{}');
		if (!body.live) return route.continue();
		if (limit) return route.fulfill({ status: 429, json: { error: "You've used your 3 free scans today. Sign in or create a free account for unlimited scans.", limit_reached: true, guest: { limit: 3, left: 0 } } });
		return route.fulfill({ status: 202, json: { job: { id: 'jobG', state: 'running', stage: 1, stage_label: 'Collect reviews', progress: 18, message: 'Collecting…', platform: 'lazada', query: body.query, created_at: new Date().toISOString() }, guest: { limit: 3, left: 2 } } });
	});
	await page.route('**/api/jobs/jobG', (route) => {
		polls += 1;
		const done = polls >= 3;
		if (done) finished = true;
		return route.fulfill({ json: { id: 'jobG', state: done ? 'complete' : 'running', stage: Math.min(3, polls), stage_label: 'x', progress: done ? 100 : [18, 68, 92][Math.min(2, polls - 1)], message: 'Working…', platform: 'lazada', query: NEW_LINK, created_at: new Date().toISOString() } });
	});
	await page.route('**/api/products', (route) => (finished ? route.fulfill({ json: { products: [freshCard], count: 1 } }) : route.continue()));
	for (const pattern of ['**/api/products/detail**', '**/api/saved/detail**']) {
		await page.route(pattern, (route) => (new URL(route.request().url()).searchParams.get('link') === NEW_LINK ? route.fulfill({ json: { product: fresh, recommendations: [] } }) : route.continue()));
	}
	return { context, page, errors };
}
const inApp = (page) => page.locator('[data-slot="sidebar"]').count();
async function axe(page, label) {
	await page.waitForTimeout(1600);
	await page.evaluate(axeSource);
	const result = await page.evaluate(() => axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } }));
	check(result.violations.length === 0, `accessibility: ${label}${result.violations.length ? ' -> ' + result.violations.map((v) => v.id + ' ' + v.nodes[0].target.join(' ')).join('; ') : ''}`);
}

// ---- 1. Landing -> guest screen -> saved report, never the main app ---------------------------------
{
	const { context, page, errors } = await open();
	await page.goto(base + '/', { waitUntil: 'networkidle' });
	await page.waitForTimeout(1200);
	await page.getByPlaceholder('Paste a Lazada PH link...').fill(SAVED.link);
	await page.getByRole('button', { name: 'Check', exact: true }).click();
	await page.waitForURL(/\/scan\/report\?link=/);
	check((await inApp(page)) === 0, 'landing page: a link that was already checked opens its report straight away, on the guest screen');
	// A link nobody has checked yet stops on the guest screen, which asks before it uses a free scan.
	await page.goto(base + '/', { waitUntil: 'networkidle' });
	await page.waitForTimeout(1200);
	await page.getByPlaceholder('Paste a Lazada PH link...').fill(NEW_LINK);
	await page.getByRole('button', { name: 'Check', exact: true }).click();
	await page.waitForURL(/\/scan\?q=/);
	await page.waitForTimeout(800);
	check((await inApp(page)) === 0 && (await page.locator('#guest-query').inputValue()) === NEW_LINK && (await page.getByRole('button', { name: /Check this Lazada PH product/ }).isVisible()), 'landing page: a new link opens the guest screen with the link filled in, and waits for a press');
	// Typed on the guest screen itself, a product that was already checked is recognised.
	await page.locator('#guest-query').fill(SAVED.link);
	await page.waitForTimeout(400);
	check(await page.getByText(/Already checked/).isVisible(), 'a product already checked is recognised and does not use a free scan');
	await page.screenshot({ path: 'tests/e2e/shots/guest_scan.png', fullPage: true });
	await page.getByRole('button', { name: 'Open report' }).click();
	await page.waitForURL(/\/scan\/report\?link=/);
	// Wait for the report itself: the address changes before the new page is drawn, and the guest screen's own
	// heading is a level-1 heading too.
	await page.locator('[aria-label="Result"]').waitFor({ timeout: 15000 });
	check((await inApp(page)) === 0, 'the report opens on the guest screen (no app menu)');
	check(await page.getByText("You're viewing this as a guest").isVisible(), 'the guest report says what an account adds');
	const noteAfterVerdict = await page.evaluate(() => {
		const box = document.querySelector('[aria-label="Result"]');
		const note = [...document.querySelectorAll('[data-slot="alert-title"]')].find((el) => el.textContent.includes("You're viewing this as a guest"));
		return Boolean(box && note) && Boolean(box.compareDocumentPosition(note) & Node.DOCUMENT_POSITION_FOLLOWING);
	});
	check(noteAfterVerdict, 'the note about an account comes after the result, not before it');
	await page.waitForTimeout(1200);
	await page.screenshot({ path: 'tests/e2e/shots/guest_report.png' });
	await axe(page, 'guest report');
	await page.getByRole('button', { name: /^Save$/ }).click();
	await page.getByRole('dialog').getByText('Create a free account to save products').waitFor({ timeout: 5000 });
	check(true, 'Save on the guest report asks to create an account');
	await page.keyboard.press('Escape');
	await page.getByRole('button', { name: /Check another product/ }).click();
	await page.waitForURL(/\/scan$/);
	check(true, '"Check another product" returns to the guest screen');
	check(errors.length === 0, `no browser errors${errors.length ? ': ' + errors[0] : ''}`);
	await context.close();
}

// ---- 2. A new link: progress on the guest screen, then the guest report -----------------------------
{
	const { context, page } = await open();
	await page.goto(base + '/scan', { waitUntil: 'networkidle' });
	await page.waitForTimeout(1000);
	await axe(page, 'guest scan screen');
	await page.locator('#guest-query').fill('hello there');
	check(await page.getByText('That is not a link.').isVisible(), 'plain text is refused with a clear message');
	await page.locator('#guest-query').fill('https://example.com/x');
	check(await page.getByText('This website is not supported').isVisible(), 'an unsupported site is refused');
	await page.locator('#guest-query').fill(NEW_LINK);
	await page.getByRole('button', { name: /Check this Lazada PH product/ }).click();
	await page.getByText('Lazada PH live scan').waitFor({ timeout: 10000 });
	check((await inApp(page)) === 0 && page.url().endsWith('/scan'), 'the scan runs on the guest screen');
	check(await page.getByText('A scan usually takes 1 to 2 minutes.').isVisible(), 'the running scan says how long a Lazada scan usually takes');
	await page.screenshot({ path: 'tests/e2e/shots/guest_running.png' });
	await page.waitForURL(/\/scan\/report\?link=/, { timeout: 40000 });
	await page.getByRole('heading', { level: 1, name: /Guest scanned this/ }).waitFor({ timeout: 15000 });
	check((await inApp(page)) === 0, 'when it finishes, the report opens on the guest screen');

	// Signing up from the guest report lands in the app on the same report, with the scan in the new account.
	await page.getByRole('button', { name: 'Create free account' }).click();
	const dialog = page.getByRole('dialog');
	const email = `guest${Date.now()}@example.com`;
	await dialog.getByLabel('Full name').fill('Gina Guest');
	await dialog.getByLabel('Email').fill(email);
	await dialog.getByLabel('Password', { exact: true }).fill('correct horse battery');
	await dialog.getByLabel('Confirm password').fill('correct horse battery');
	await dialog.getByRole('checkbox').click();
	await dialog.getByRole('button', { name: 'Create account' }).click();
	await page.waitForURL(/\/app\/report\?link=/, { timeout: 20000 });
	// The address changes a moment before the new page is drawn (pages cross-fade), so wait for the app itself.
	await page.locator('[data-slot="sidebar"]').first().waitFor({ state: 'attached', timeout: 10000 }).catch(() => {});
	check((await inApp(page)) > 0, 'after creating an account from the guest report, the same report opens in the app');
	await closeTour(page);
	await page.waitForTimeout(1200);
	const lib = await page.evaluate(() => fetch('/api/me/library').then((r) => r.json()));
	check(Boolean(lib.activity[NEW_LINK]), 'the guest scan moved into the new account\'s history');
	await page.goto(base + '/scan', { waitUntil: 'networkidle' });
	await page.waitForURL(/\/app\/analyze/, { timeout: 10000 });
	check(true, 'a signed-in person who opens the guest screen is sent to the app');
	await context.close();
}

// ---- 3. Out of free scans, and the phone -------------------------------------------------------------
{
	const { context, page } = await open({ limit: true });
	await page.goto(base + '/scan', { waitUntil: 'networkidle' });
	await page.waitForTimeout(800);
	await page.locator('#guest-query').fill(NEW_LINK);
	await page.getByRole('button', { name: /Check this Lazada PH product/ }).click();
	await page.getByRole('dialog').getByText(/used your 3 free scans today/).waitFor({ timeout: 10000 });
	await page.keyboard.press('Escape');
	await page.waitForTimeout(500);
	check(await page.getByText("You've used today's free scans").isVisible(), 'out of free scans: the guest screen explains and offers an account');
	check(await page.getByText('No free scans left today').first().isVisible(), 'the scans-left badge updates');
	await context.close();
}
{
	const { context, page } = await open({ width: 390, height: 844 });
	for (const route of ['/scan', `/scan/report?link=${encodeURIComponent(SAVED.link)}`]) {
		await page.goto(base + route, { waitUntil: 'networkidle' });
		await page.waitForTimeout(1200);
		const wide = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
		check(wide <= 1, `phone: ${route.slice(0, 14)} does not scroll sideways`);
	}
	await page.screenshot({ path: 'tests/e2e/shots/guest_phone.png' });
	await context.close();
}
{
	const { context, page } = await open({ scheme: 'dark' });
	await page.goto(base + '/scan', { waitUntil: 'networkidle' });
	await axe(page, 'guest scan screen, dark');
	await page.goto(`${base}/scan/report?link=${encodeURIComponent(SAVED.link)}`, { waitUntil: 'networkidle' });
	await axe(page, 'guest report, dark');
	await context.close();
}

await browser.close();
console.log(failures ? `\n${failures} check(s) FAILED` : '\nAll checks passed.');
process.exit(failures ? 1 : 0);
