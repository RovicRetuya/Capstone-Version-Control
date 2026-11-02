// Walks every page of the app at phone, tablet and desktop widths and reports what breaks the layout:
// the page scrolling sideways and elements sticking out past the screen edge.
// With SHOTS=1 it also saves a screenshot of each page at 390 and 768 wide in tests/e2e/shots/responsive.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import { signUp } from './_signin.mjs';

const base = process.env.BASE || 'http://localhost:5173';
const shots = process.env.SHOTS === '1';
const out = 'tests/e2e/shots/responsive';
if (shots) fs.mkdirSync(out, { recursive: true });

// Small phone, phone, large phone, tablet, small laptop, laptop, wide desktop.
const WIDTHS = [
	[320, 640],
	[360, 740],
	[414, 896],
	[768, 1024],
	[667, 375],
	[844, 390],
	[1024, 768],
	[1280, 800],
	[1536, 864],
	[1920, 1080],
	[2560, 1440]
];
// Pages anyone can open without an account.
const PUBLIC_PATHS = ['/', '/enter', '/extension', '/scan'];
const FIXED_PATHS = [
	'/',
	'/enter',
	'/extension',
	'/app/home',
	'/app/analyze',
	'/app/products',
	'/app/history',
	'/app/wishlist',
	'/app/settings',
	'/app/faq',
	'/app/about',
	'/app/extension'
];

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
await signUp(context, base, 'Responsive Check');

// A saved product to open a report with, if the server has one.
let paths = [...FIXED_PATHS];
try {
	const saved = await (await context.request.get(base + '/api/saved/products')).json();
	const first = (saved.products || saved)?.[0];
	if (first?.link) paths.push('/app/report?link=' + encodeURIComponent(first.link));
} catch {
	/* no report page to check */
}
const only = process.env.ONLY ? process.env.ONLY.split(',') : null;
if (process.env.GUEST_ONLY === '1') paths = [];
if (only) paths = paths.filter((p) => only.some((o) => p.startsWith(o)));

const page = await context.newPage();
// Entrance animations slide content in; measure the page where it comes to rest.
await page.emulateMedia({ reducedMotion: 'reduce' });
page.on('pageerror', (error) => console.log(`  [pageerror] ${error.message.split('\n')[0]}`));

async function settle() {
	await page.waitForLoadState('networkidle').catch(() => {});
	// A new account's welcome tour opens over the page; close it so the page underneath is what gets measured.
	const tour = page.locator('[data-tour]');
	if (await tour.count()) {
		await tour.getByRole('button', { name: 'Skip' }).click().catch(() => {});
		await tour.waitFor({ state: 'detached', timeout: 3000 }).catch(() => {});
	}
	await page.waitForTimeout(1500);
}

const measureOn = (target) =>
	target.evaluate(() => {
		const vw = document.documentElement.clientWidth;
		const describe = (el) => {
			const cls = typeof el.className === 'string' ? el.className.trim().split(/\s+/).slice(0, 6).join('.') : '';
			const text = (el.innerText || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim().slice(0, 40);
			return `${el.tagName.toLowerCase()}${cls ? '.' + cls : ''}${text ? ` "${text}"` : ''}`;
		};
		// An element inside something that scrolls or clips sideways on purpose is not a problem.
		const clipped = (el) => {
			for (let parent = el.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
				const style = getComputedStyle(parent);
				if (/(auto|scroll|hidden|clip)/.test(style.overflowX) && parent.getBoundingClientRect().right <= vw + 1) return true;
			}
			return false;
		};
		const wide = [];
		for (const el of document.querySelectorAll('body *')) {
			const style = getComputedStyle(el);
			if (style.display === 'none' || style.visibility === 'hidden' || style.position === 'fixed') continue;
			const rect = el.getBoundingClientRect();
			if (!rect.width || !rect.height) continue;
			if ((rect.right > vw + 1 || rect.left < -1) && !clipped(el)) wide.push(`${describe(el)} [${Math.round(rect.left)}..${Math.round(rect.right)}]`);
		}
		// Text that spills out of its own box without being cut off on purpose (a "...", a scroll area).
		const spill = [];
		for (const el of document.querySelectorAll('body *')) {
			const style = getComputedStyle(el);
			if (style.display === 'none' || style.position === 'fixed' || el.clientWidth < 8) continue;
			if (el.scrollWidth <= el.clientWidth + 1 || style.textOverflow === 'ellipsis' || /(auto|scroll|hidden|clip)/.test(style.overflowX)) continue;
			if (!['block', 'flex', 'grid', 'inline-block', 'list-item', 'table-cell'].includes(style.display) && !el.matches('p, h1, h2, h3, h4, dd, dt, li, b, span')) continue;
			if (clipped(el)) continue;
			const box = el.getBoundingClientRect();
			const culprit = [...el.querySelectorAll('*')].find((child) => child.getBoundingClientRect().right > box.right + 1 && child.getBoundingClientRect().width);
			spill.push(`${describe(el)} ${el.scrollWidth}>${el.clientWidth}${culprit ? `  <- ${describe(culprit)}` : ''}`);
		}
		return {
			spill: [...new Set(spill)].slice(0, 5),
			over: document.documentElement.scrollWidth - vw,
			wide: [...new Set(wide)].slice(0, 6)
		};
	});

const measure = () => measureOn(page);
let problems = 0;
for (const path of paths) {
	console.log(path.slice(0, 40));
	for (const [width, height] of WIDTHS) {
		await page.setViewportSize({ width, height });
		await page.goto(base + path);
		await settle();
		if (new URL(page.url()).pathname !== path.split('?')[0]) {
			console.log(`  ${width}: redirected to ${new URL(page.url()).pathname}`);
			break;
		}
		const found = await measure();
		const bad = found.over > 1 || found.wide.length || found.spill.length;
		if (bad) problems += 1;
		console.log(`  ${String(width).padStart(4)}  ${bad ? '!!' : 'ok'}${found.over > 1 ? `  sideways +${found.over}px` : ''}`);
		for (const line of found.wide) console.log(`          wide  ${line}`);
		for (const line of found.spill) console.log(`          spill ${line}`);
		if (shots && (width === 390 || width === 414 || width === 768)) {
			const name = (path.replace(/[^a-z0-9]+/gi, '_').replace(/^_|_$/g, '') || 'home') + `_${width}.png`;
			await page.screenshot({ path: `${out}/${name}`, fullPage: true });
		}
	}
}

if (process.env.SIGNED_IN_ONLY === '1') PUBLIC_PATHS.length = 0;
// The same walk as a visitor with no account: the public header and the landing page look different.
const guest = await (await browser.newContext({ viewport: { width: 1280, height: 800 } })).newPage();
await guest.emulateMedia({ reducedMotion: 'reduce' });
await guest.addInitScript(() => sessionStorage.setItem('splash-seen', '1'));
for (const path of PUBLIC_PATHS) {
	console.log(`${path} (signed out)`);
	for (const [width, height] of WIDTHS) {
		await guest.setViewportSize({ width, height });
		await guest.goto(base + path);
		await guest.waitForLoadState('networkidle').catch(() => {});
		await guest.waitForTimeout(1500);
		const found = await measureOn(guest);
		const bad = found.over > 1 || found.wide.length || found.spill.length;
		if (bad) problems += 1;
		console.log(`  ${String(width).padStart(4)}  ${bad ? '!!' : 'ok'}${found.over > 1 ? `  sideways +${found.over}px` : ''}`);
		for (const line of found.wide) console.log(`          wide  ${line}`);
		for (const line of found.spill) console.log(`          spill ${line}`);
	}
}
await browser.close();
console.log(problems ? `\n${problems} page/width combinations need attention.` : '\nNo layout problems found.');
