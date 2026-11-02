// Tap targets: on a touch screen every control must be at least 40px wide and tall.
// The one exception is a link or button inside a sentence (also exempt in the accessibility guidelines),
// which this check recognises by itself. Run with LIST=1 to print every small control instead of failing fast.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import { signUp } from './_signin.mjs';

const base = process.env.BASE || 'http://localhost:5173';
fs.mkdirSync('tests/e2e/shots', { recursive: true });
const MIN = 40;
let failures = 0;
const check = (ok, what) => {
	console.log(`${ok ? 'PASS' : 'FAIL'}  ${what}`);
	if (!ok) failures += 1;
};
const pool = await (await fetch(`${base}/api/saved/products`)).json();
const SAVED = pool.products.find((p) => /Type C Fast Charging/i.test(p.name)) ?? pool.products[0];
const report = (prefix) => `${prefix}/report?link=${encodeURIComponent(SAVED.link)}`;

// Runs in the page: every visible control smaller than `min` on either side.
const AUDIT = (min) => {
	const shown = (el) => {
		const box = el.getBoundingClientRect();
		const style = getComputedStyle(el);
		if (box.width <= 0 || box.height <= 0) return false;
		if (style.visibility === 'hidden' || style.display === 'none' || style.pointerEvents === 'none') return false;
		if (el.closest('[aria-hidden="true"], [inert], [hidden]')) return false;
		// Only what can be reached by scrolling the page: skip things clipped away for good.
		return box.bottom > -5000 && box.right > 0 && box.left < innerWidth + 4000;
	};
	// A link or button that sits inside running text.
	const inSentence = (el) => {
		if (!/^inline/.test(getComputedStyle(el).display) && el.tagName !== 'A') return false;
		const parent = el.parentElement;
		if (!parent) return false;
		return [...parent.childNodes].some((node) => node.nodeType === 3 && node.textContent.trim().length > 1);
	};
	// The box a finger can actually hit: the control, grown by a pseudo-element that stretches it, or by its label.
	const hitBox = (el) => {
		let { left, top, right, bottom } = el.getBoundingClientRect();
		const grow = (box) => {
			left = Math.min(left, box.left);
			top = Math.min(top, box.top);
			right = Math.max(right, box.right);
			bottom = Math.max(bottom, box.bottom);
		};
		for (const pseudo of ['::before', '::after']) {
			const style = getComputedStyle(el, pseudo);
			if (style.content === 'none' || style.position !== 'absolute') continue;
			// Find the box the pseudo-element is positioned against.
			let anchor = el;
			while (anchor && getComputedStyle(anchor).position === 'static') anchor = anchor.parentElement;
			if (!anchor) continue;
			const box = anchor.getBoundingClientRect();
			const inset = ['left', 'top', 'right', 'bottom'].map((side) => parseFloat(style[side]));
			if (inset.some(Number.isNaN)) continue;
			grow({ left: box.left + inset[0], top: box.top + inset[1], right: box.right - inset[2], bottom: box.bottom - inset[3] });
		}
		const label = (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)) || el.closest('label');
		if (label && /^(checkbox|radio|switch)$/.test(el.getAttribute('role') || el.type || '')) grow(label.getBoundingClientRect());
		return { width: right - left, height: bottom - top };
	};
	const found = [];
	const selector = 'a[href], button, [role="button"], [role="tab"], [role="radio"], [role="switch"], [role="checkbox"], [role="menuitem"], [role="option"], input:not([type="hidden"]), select, textarea, summary';
	for (const el of document.querySelectorAll(selector)) {
		if (!shown(el) || el.disabled || el.getAttribute('aria-disabled') === 'true') continue;
		if (inSentence(el)) continue;
		const box = hitBox(el);
		if (box.width >= min - 0.5 && box.height >= min - 0.5) continue;
		const name = (el.getAttribute('aria-label') || el.innerText || el.getAttribute('placeholder') || el.getAttribute('title') || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 40);
		found.push(`${el.tagName.toLowerCase()}${el.getAttribute('data-slot') ? '[' + el.getAttribute('data-slot') + ']' : ''}${el.getAttribute('role') ? '{' + el.getAttribute('role') + '}' : ''} "${name}" ${Math.round(box.width)}x${Math.round(box.height)}`);
	}
	return [...new Set(found)];
};

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const PHONE = { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 };
const settle = (page, ms = 1100) => page.waitForTimeout(ms);
async function audit(page, scene) {
	await settle(page, 600);
	const small = await page.evaluate(AUDIT, MIN);
	const wide = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
	check(small.length === 0, `${scene}: every control is at least ${MIN}px${small.length ? ` (${small.length} too small)` : ''}`);
	if (small.length) for (const line of small.slice(0, process.env.LIST ? 200 : 12)) console.log(`        ${line}`);
	check(wide <= 1, `${scene}: no sideways scroll`);
}

// ---- Guest screens -----------------------------------------------------------------------------------
{
	const context = await browser.newContext(PHONE);
	const page = await context.newPage();
	await page.goto(base + '/', { waitUntil: 'networkidle' });
	await settle(page);
	check(await page.evaluate(() => matchMedia('(pointer: coarse)').matches), 'the test browser counts as a touch screen');
	await audit(page, 'landing');
	await page.getByRole('button', { name: 'Sign in' }).first().click();
	await page.getByRole('dialog').waitFor();
	await audit(page, 'sign-in pop-up');
	await page.getByRole('button', { name: /Sign up/ }).click();
	await audit(page, 'sign-up pop-up');
	await page.getByRole('button', { name: 'Terms of Service' }).click();
	await audit(page, 'terms pop-up');
	await page.keyboard.press('Escape');
	await page.keyboard.press('Escape');
	await page.goto(base + '/scan', { waitUntil: 'networkidle' });
	await settle(page);
	await audit(page, 'guest scan screen');
	await page.goto(base + report('/scan'), { waitUntil: 'networkidle' });
	await page.getByRole('heading', { level: 1 }).waitFor({ timeout: 15000 });
	await settle(page, 1500);
	await audit(page, 'guest report');
	await page.screenshot({ path: 'tests/e2e/shots/targets_guest_report.png', fullPage: true });
	await context.close();
}

// ---- Signed-in screens -------------------------------------------------------------------------------
{
	const context = await browser.newContext(PHONE);
	await signUp(context, base);
	const page = await context.newPage();
	// Open one report first, so Home and History have something in them.
	await page.goto(base + report('/app'), { waitUntil: 'networkidle' });
	await page.getByRole('heading', { level: 1 }).waitFor({ timeout: 15000 });
	await settle(page, 1500);
	await audit(page, 'report, first tab');
	await page.getByRole('tab', { name: /Reviews/ }).click();
	await audit(page, 'report, Reviews tab');
	await page.getByRole('button', { name: /^Filters/ }).click();
	await page.getByRole('dialog').waitFor();
	await audit(page, 'report, review filters sheet');
	await page.keyboard.press('Escape');
	await page.getByRole('tab', { name: /Similar/ }).click();
	await audit(page, 'report, Similar tab');
	await page.getByRole('button', { name: /^Save$/ }).click();
	await settle(page, 900);

	for (const [route, scene] of [['/app/home', 'Home'], ['/app/history', 'History'], ['/app/wishlist', 'Wishlist'], ['/app/about', 'About'], ['/app/faq', 'FAQ'], ['/app/settings', 'Settings']]) {
		await page.goto(base + route, { waitUntil: 'networkidle' });
		await settle(page, 1400);
		await audit(page, scene);
	}
	await page.screenshot({ path: 'tests/e2e/shots/targets_settings.png', fullPage: true });
	for (const [button, scene] of [['Edit', 'edit-account pop-up'], ['Clear scan history', 'clear-history pop-up'], ['Delete account', 'delete-account pop-up']]) {
		await page.getByRole('button', { name: button }).click();
		await settle(page, 500);
		await audit(page, scene);
		await page.keyboard.press('Escape');
		await settle(page, 400);
	}

	await page.goto(base + '/app/products', { waitUntil: 'networkidle' });
	await settle(page, 1500);
	await audit(page, 'Products');
	await page.getByRole('button', { name: /^Filters/ }).click();
	await page.getByRole('dialog').waitFor();
	await audit(page, 'Products filter sheet');
	await page.locator('#filter-risk-sheet').click();
	await settle(page, 400);
	await audit(page, 'Products filter list open');
	await page.keyboard.press('Escape');
	await page.keyboard.press('Escape');

	await page.goto(base + '/app/analyze', { waitUntil: 'networkidle' });
	await settle(page);
	await page.locator('#search-query').fill('power bank');
	await audit(page, 'Check a product, with a name typed');
	await page.screenshot({ path: 'tests/e2e/shots/targets_check.png', fullPage: true });

	await page.goto(base + '/app/home', { waitUntil: 'networkidle' });
	await settle(page);
	await audit(page, 'icon menu');
	await page.screenshot({ path: 'tests/e2e/shots/targets_menu.png' });
	await page.getByRole('button', { name: /Test Shopper/ }).click();
	await settle(page, 500);
	await audit(page, 'account menu open');
	await page.keyboard.press('Escape');
	await page.keyboard.press('Escape');
	await page.getByRole('button', { name: 'Search pages and products' }).click();
	await page.getByRole('dialog').waitFor();
	await audit(page, 'search pop-up');
	await context.close();
}

// ---- A mouse-and-keyboard screen must look exactly as before ------------------------------------------
{
	const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
	const page = await context.newPage();
	await page.goto(base + '/', { waitUntil: 'networkidle' });
	await settle(page);
	const height = await page.getByRole('button', { name: 'Sign in' }).first().evaluate((el) => el.getBoundingClientRect().height);
	check(!(await page.evaluate(() => matchMedia('(pointer: coarse)').matches)) && Math.round(height) === 32, `desktop: buttons keep their size (Sign in is ${Math.round(height)}px tall)`);
	await context.close();
}

await browser.close();
console.log(failures ? `\n${failures} check(s) FAILED` : '\nAll checks passed.');
process.exit(failures ? 1 : 0);
