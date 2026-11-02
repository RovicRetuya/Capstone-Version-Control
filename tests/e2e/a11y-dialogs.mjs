// axe on the pop-ups, the phone menu and the signed-in screens (the account is pretended in the browser only).
import { chromium } from 'playwright-core';
import { signUp } from './_signin.mjs';
import fs from 'node:fs';

const base = process.env.BASE || 'http://localhost:5173';
const axeSource = fs.readFileSync('node_modules/axe-core/axe.min.js', 'utf8');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
let WARNCOUNT = 0; const WARNS = new Map();
const __warn = (m) => { if (m.type() === 'warning' && /svelte/i.test(m.text())) { WARNCOUNT++; const t = m.text().split(String.fromCharCode(10))[0].slice(0, 80); WARNS.set(t, (WARNS.get(t) || 0) + 1); } };
let total = 0;

async function scan(page, label) {
	await page.waitForTimeout(1500);
	await page.evaluate(axeSource);
	const result = await page.evaluate(() => axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } }));
	total += result.violations.length;
	console.log(`${label.padEnd(44)} ${result.violations.length ? result.violations.length + ' problem(s)' : 'ok'}`);
	for (const v of result.violations) {
		console.log(`    - [${v.impact}] ${v.id}: ${v.help}`);
		for (const n of v.nodes.slice(0, 3)) console.log(`        ${n.target.join(' ')}  ${(n.failureSummary || '').split('\n').slice(1, 2).join(' ').trim()}`);
	}
}

for (const scheme of ['light', 'dark']) {
	// Guest pop-ups.
	{
		const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: scheme });
context.on('console', __warn);
		const page = await context.newPage();
		await page.goto(base + '/', { waitUntil: 'networkidle' });
		await page.getByRole('button', { name: /Sign in/ }).first().click();
		await scan(page, `${scheme}: sign-in pop-up`);
		await page.getByRole('button', { name: /Sign up/ }).click();
		await page.getByRole('button', { name: 'Create account' }).last().click();
		await scan(page, `${scheme}: sign-up pop-up with errors`);
		await page.getByRole('button', { name: 'Terms of Service' }).click();
		await scan(page, `${scheme}: terms pop-up on top of sign-up`);
		await context.close();
	}
	// Signed-in screens and dialogs (account pretended).
	{
		const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: scheme });
context.on('console', __warn);
		const page = await context.newPage();
		await page.route('**/api/auth/me', (r) => r.fulfill({ json: { user: { name: 'Test Shopper', email: 'tester@example.com' }, guest: null } }));
		await page.route('**/api/me/library', (r) => r.fulfill({ json: { activity: {}, wishlist: [], clearedAt: 0 } }));
		await page.goto(base + '/app/settings', { waitUntil: 'networkidle' });
		await scan(page, `${scheme}: settings, signed in`);
		await page.getByRole('button', { name: 'Edit' }).click();
		await scan(page, `${scheme}: edit-account pop-up`);
		await page.keyboard.press('Escape');
		await page.getByRole('button', { name: 'Clear scan history' }).click();
		await scan(page, `${scheme}: clear-history confirmation`);
		await page.keyboard.press('Escape');
		await page.getByRole('button', { name: 'Delete account' }).click();
		await scan(page, `${scheme}: delete-account pop-up`);
		await page.keyboard.press('Escape');
		await page.getByRole('button', { name: /Test Shopper/ }).click();
		await scan(page, `${scheme}: account menu open`);
		await context.close();
	}
	// Phone: menu sheet.
	{
		const context = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: scheme });
context.on('console', __warn);
		await signUp(context, base);
		const page = await context.newPage();
		await page.goto(base + '/app/home', { waitUntil: 'networkidle' });
		await scan(page, `${scheme}: phone menu`);
		await page.screenshot({ path: `tests/e2e/shots/phone_menu_${scheme}.png` });
		await context.close();
	}
}
await browser.close();
console.log(total ? `\n${total} kind(s) of problem found` : '\nNo accessibility problems found by axe.');
console.log('svelte warnings:', WARNCOUNT, [...WARNS.entries()]);
