// The four "fix first" items: red only for serious safety reports, one word for the action ("Check"),
// one name per result group, and an honest landing headline. Uses a made-up catalog in the browser only.
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

const LABELS = [
	{ category: 'safety', label: 'Safety problem', helper: 'Overheating, smoke, sparks or shocks', informs_only: false },
	{ category: 'defect', label: 'Faulty or broken', helper: "Doesn't work or stops working", informs_only: false },
	{ category: 'quality', label: 'Poor quality', helper: 'Weak, flimsy or scratched', informs_only: true },
	{ category: 'counterfeit', label: 'Possible fake', helper: 'A copy, not the original brand', informs_only: false },
	{ category: 'not_as_described', label: 'Not as advertised', helper: 'Differs from the listing', informs_only: true }
];
const QUOTES = {
	safety: { text: 'There is a smell on it like a burn wire.', rating: 1, hazard: 'smoke or a burning smell', highlights: [[30, 34]] },
	defect: { text: 'It stopped working after a week.', rating: 2, highlights: [[3, 18]] },
	counterfeit: { text: 'Peke, not the original brand.', rating: 1, highlights: [[0, 4]] }
};
const badge = (category, mentions) => {
	const label = LABELS.find((l) => l.category === category);
	return { ...label, mentions, reviews_analyzed: 40, phrase: 'x', summary: mentions ? `${mentions} review${mentions === 1 ? ' reports' : 's report'} this` : 'No reviews report this', more_evidence: 0, evidence: mentions && QUOTES[category] ? [QUOTES[category]] : [] };
};
const mk = (i, name, state, tone, headline, counts, detail) => ({
	name: `${name} power bank`, link: `https://shopee.ph/w-${i}`, price: '₱499.00', rating: 4.2, platform: 'shopee', reviews_collected: 40, img: '',
	analysis_date: new Date(Date.now() - i * 3600000).toISOString(),
	badge_view: state === 'not_analyzed'
		? { available: false, state, tone: 'unknown', headline: 'Not analyzed yet', detail: 'This product has not been checked with the current review model.', reviews_analyzed: 0, counts: { safety: 0, counterfeit: 0, defect: 0 }, badges: [], labels: LABELS }
		: { available: true, state, tone, headline, detail, reviews_analyzed: 40, counts: { safety: 0, defect: 0, counterfeit: 0, ...counts }, labels: LABELS, badges: ['safety', 'defect', 'counterfeit'].map((c) => badge(c, counts[c] ?? 0)) }
});
const fake = [
	mk(0, 'Alpha serious', 'safety_warning', 'high', 'Reviewers report safety problems', { safety: 4 }, 'Of 40 reviews, 4 mention fire. Read them below and judge for yourself.'),
	mk(1, 'Bravo mild', 'possible_safety_issue', 'moderate', 'Some reviewers mention safety concerns', { safety: 1, defect: 6 }, 'Of 40 reviews, 1 mentions smoke or a burning smell; 6 say it is faulty. Read them below and judge for yourself.'),
	mk(2, 'Charlie fakes', 'possible_counterfeit_or_defect', 'moderate', 'Reviewers report fakes or defects', { defect: 6, counterfeit: 3 }, 'Of 40 reviews, 6 say it is faulty; 3 say it may not be genuine.'),
	mk(3, 'Delta clean', 'no_warning_signs', 'low', 'No warning signs found', { defect: 2 }, 'No problem reaches a warning level in 40 reviews, but 2 reviews say it is faulty. Read them below. This is not proof that a product is safe.'),
	mk(4, 'Echo lifted', 'no_warning_signs', 'low', 'No warning signs found', { safety: 1 }, 'No problem reaches a warning level in 40 reviews, but 1 review mentions smoke or a burning smell. Read it below. This is not proof that a product is safe.'),
	mk(5, 'Foxtrot few', 'insufficient_evidence', 'unknown', 'Not enough reviews to judge', { safety: 1 }, 'Only 4 usable reviews; at least 20 are needed. Even so, 1 review mentions smoke or a burning smell. Read it below.'),
	mk(6, 'Golf few', 'insufficient_evidence', 'unknown', 'Not enough reviews to judge', {}, 'Only 4 usable reviews; at least 20 are needed.'),
	mk(7, 'Hotel unreliable', 'reviews_may_be_unreliable', 'unknown', 'These reviews may not be trustworthy', {}, 'Many reviews look duplicated or generic.'),
	mk(8, 'India old', 'not_analyzed')
];
const EXPECT = { 'Alpha serious': 'safety', 'Bravo mild': 'caution', 'Charlie fakes': 'caution', 'Delta clean': 'clear', 'Echo lifted': 'caution', 'Foxtrot few': 'caution', 'Golf few': 'unknown', 'Hotel unreliable': 'unknown', 'India old': 'unknown' };
const NAMES = { safety: 'Safety reports', caution: 'Caution', clear: 'No warnings', unknown: 'No result yet' };
const detailFor = (p) => ({
	product: {
		...p, category: 'Power banks', sentiment_summary: { sentiment_counts: { positive: 20, uncertain: 8, negative: 12 }, coverage: { reviews_listed: 40 } },
		comments: [
			...(p.badge_view.counts.safety ? [{ author: 'a', rating: 1, time: '2026-09-30', content: QUOTES.safety.text, sentiment_analysis: { label: 'negative', review_tags: ['safety'], sentences: [{ text_raw: QUOTES.safety.text, tags: ['safety'], terms: [{ span: [30, 34], ngram: 'burn', category: 'safety' }] }] } }] : []),
			...(p.badge_view.counts.defect ? [{ author: 'b', rating: 2, time: '2026-09-28', content: QUOTES.defect.text, sentiment_analysis: { label: 'negative', review_tags: ['defect'], sentences: [{ text_raw: QUOTES.defect.text, tags: ['defect'], terms: [{ span: [3, 18], ngram: 'stopped working', category: 'defect' }] }] } }] : []),
			{ author: 'c', rating: 5, time: '2026-09-20', content: 'Great, charges fast.', sentiment_analysis: { label: 'positive', review_tags: [], sentences: [] } }
		]
	},
	recommendations: []
});

const SEED = (items) => { try { if (!localStorage.getItem('defaketive-activity')) localStorage.setItem('defaketive-activity', JSON.stringify(Object.fromEntries(items.map((p, i) => [p.link, { product: p, openedAt: Date.now() - i * 3600000 }])))); } catch {} };
const browser = await chromium.launch({ channel: 'chrome', headless: true });
async function open({ width = 1280, height = 900, signedIn = true, scheme = 'light' } = {}) {
	const context = await browser.newContext({ viewport: { width, height }, colorScheme: scheme });
	if (signedIn) {
		await signUp(context, base);
		await context.addInitScript(SEED, fake);
	}
	const page = await context.newPage();
	const errors = [];
	page.on('pageerror', (e) => errors.push(e.message));
	await page.route('**/api/products', (r) => r.fulfill({ json: { products: fake, count: fake.length } }));
	await page.route('**/api/saved/products', (r) => r.fulfill({ json: { products: fake, count: fake.length } }));
	for (const pattern of ['**/api/products/detail**', '**/api/saved/detail**']) {
		await page.route(pattern, (r) => {
			const p = fake.find((x) => x.link === new URL(r.request().url()).searchParams.get('link'));
			return p ? r.fulfill({ json: detailFor(p) }) : r.continue();
		});
	}
	await page.route('**/api/picks', (r) => r.fulfill({ json: { products: [] } }));
	await page.route('**/api/saved/popular', (r) => r.fulfill({ json: { products: [] } }));
	await page.route('**/api/wishlist/popular', (r) => r.fulfill({ json: { products: [] } }));
	return { context, page, errors };
}
const settle = (page, ms = 1200) => page.waitForTimeout(ms);
const toneOf = (cls) => (String(cls).match(/tone-(safety|caution|clear|unknown)/) ?? [])[1];
const reportUrl = (i, guest = false) => `${base}${guest ? '/scan' : '/app'}/report?link=${encodeURIComponent(fake[i].link)}`;
async function axe(page, label) {
	await page.waitForTimeout(1500);
	await page.evaluate(axeSource);
	const result = await page.evaluate(() => axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } }));
	check(result.violations.length === 0, `accessibility: ${label}${result.violations.length ? ' -> ' + result.violations.map((v) => v.id + ' ' + v.nodes[0].target.join(' ')).join('; ') : ''}`);
}
// What a report page shows about its group.
async function reportFacts(page) {
	await page.getByRole('group', { name: 'Result' }).waitFor({ timeout: 15000 });
	await settle(page, 1500);
	return page.evaluate(() => {
		const box = document.querySelector('[aria-label="Result"]');
		const tagged = [...document.querySelectorAll('p')].filter((p) => p.querySelector('[data-slot="badge"]')?.textContent.trim() === 'This product').map((p) => p.textContent.replace('This product', '').trim());
		const safetyBar = [...document.querySelectorAll('[data-slot="progress"]')].find((el) => /bg-(destructive|warning)/.test(el.className));
		return {
			boxClass: box.className,
			boxLabel: box.querySelector('span > span:not([class])')?.textContent ?? box.textContent,
			boxText: box.textContent,
			tagged,
			// The note for this product only ("This product is shown as…"), not the general line under the table.
			lifted: [...document.querySelectorAll('p')].find((p) => p.textContent.includes('This product is shown as'))?.textContent.replace(/\s+/g, ' ').trim() ?? '',
			safetyBar: safetyBar ? (safetyBar.className.includes('bg-destructive') ? 'red' : 'orange') : 'none',
			marks: [...document.querySelectorAll('mark')].map((m) => m.className)
		};
	});
}

// ---- 1 + 3. Colours and group names, signed in ------------------------------------------------------
{
	const { context, page, errors } = await open();

	// Products: every card's chip.
	await page.goto(base + '/app/products', { waitUntil: 'networkidle' });
	await settle(page, 1800);
	const cards = await page.evaluate(() =>
		[...document.querySelectorAll('[data-slot="card"]')].map((card) => {
			const chip = [...card.querySelectorAll('[data-slot="badge"]')].find((b) => b.querySelector('svg'));
			const safety = [...card.querySelectorAll('[data-slot="badge"]')].find((b) => /^Safety problem/.test(b.textContent.trim()));
			return { name: card.querySelector('a[title]')?.getAttribute('title') ?? '', label: chip?.textContent.trim(), cls: chip?.className ?? '', safetyCls: safety?.className ?? '' };
		})
	);
	for (const [name, kind] of Object.entries(EXPECT)) {
		const card = cards.find((c) => c.name.startsWith(name));
		check(Boolean(card) && card.label === NAMES[kind] && toneOf(card.cls) === kind, `card "${name}" is ${NAMES[kind]} (${card?.label}, ${toneOf(card?.cls)})`);
	}
	const alpha = cards.find((c) => c.name.startsWith('Alpha'));
	const bravo = cards.find((c) => c.name.startsWith('Bravo'));
	check(toneOf(alpha.safetyCls) === 'safety' && toneOf(bravo.safetyCls) === 'caution', 'the "Safety problem" count is red only on the serious product, orange on the mild one');
	check(cards.filter((c) => toneOf(c.cls) === 'safety').length === 1, 'exactly one product is red: the one with serious reports');
	await page.screenshot({ path: 'tests/e2e/shots/wording_products.png', fullPage: true });

	// Products: the filter uses the same four names.
	await page.locator('#filter-risk').click();
	const options = (await page.getByRole('option').allInnerTexts()).map((t) => t.trim());
	check(options.join(' | ') === 'All products | Caution or safety reports | Safety reports | Caution | No warnings | No result yet', `Products filter names: ${options.join(' | ')}`);
	await page.keyboard.press('Escape');
	for (const [option, count] of [['Safety reports', 1], ['Caution', 4], ['No warnings', 1], ['No result yet', 3], ['Caution or safety reports', 5], ['All products', 9]]) {
		await page.locator('#filter-risk').click();
		await page.getByRole('option', { name: option, exact: true }).click();
		await page.waitForTimeout(400);
		check(await page.getByText(new RegExp(`^${count} products? shown`)).isVisible(), `Products filter "${option}" shows ${count}`);
	}

	// History: same names, same counts.
	await page.goto(base + '/app/history', { waitUntil: 'networkidle' });
	await settle(page, 1500);
	const toggles = (await page.getByRole('group', { name: 'Filter scans' }).getByRole('radio').allInnerTexts()).map((t) => t.trim());
	check(toggles.join(' | ') === 'All | No warnings | Caution | Safety reports | No result yet', `History filter names: ${toggles.join(' | ')}`);
	const stats = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('dl[aria-label="Your scan history in numbers"] > *')].map((el) => [el.querySelector('dt').textContent.trim(), el.querySelector('dd').textContent.trim()])));
	check(stats['No warnings'] === '1' && stats['Caution'] === '4' && stats['Safety reports'] === '1', `History numbers: ${JSON.stringify(stats)}`);
	await page.getByRole('radio', { name: 'Safety reports' }).click();
	await page.waitForTimeout(400);
	check(await page.getByText('1 result', { exact: true }).isVisible(), 'History "Safety reports" lists only the serious product');
	await page.getByRole('radio', { name: 'No result yet' }).click();
	await page.waitForTimeout(400);
	check(await page.getByText('3 results', { exact: true }).isVisible(), 'History "No result yet" lists the three without a result');

	// Home: the overview, the alert and the rows.
	await page.goto(base + '/app/home', { waitUntil: 'networkidle' });
	await settle(page, 1800);
	const overview = await page.locator('[aria-label="Overview of your checked products"]').innerText();
	check(/No warnings · 1 product/.test(overview) && /Caution · 4 products/.test(overview) && /Safety reports · 1 product/.test(overview) && /No result yet · 3 products/.test(overview), 'Home overview uses the four group names with the right counts');
	const look = page.locator('[aria-labelledby="attention-title"]');
	const lookNames = await look.locator('article a[title]').evaluateAll((els) => els.map((el) => el.getAttribute('title')));
	check(lookNames.length === 5 && lookNames[0].startsWith('Alpha serious'), `Home "Needs a look" lists the 5 products with warnings, the serious one first (${lookNames[0]})`);
	check((await look.getByRole('link', { name: 'Safety reports · 1' }).getAttribute('href')) === '/app/history?filter=safety' && (await look.getByRole('link', { name: 'Caution · 4' }).getAttribute('href')) === '/app/history?filter=caution', 'its links use the group names and open History on that group');
	check(await page.getByText('Recently checked').isVisible() && (await page.getByText('Products checked').isVisible()), 'Home says "Recently checked" and "Products checked"');
	check((await page.getByText('Warnings by marketplace').count()) === 0, 'the marketplace comparison chart is gone');
	await page.screenshot({ path: 'tests/e2e/shots/wording_home.png', fullPage: true });
	await axe(page, 'Home');

	// Reports.
	await page.goto(reportUrl(1), { waitUntil: 'networkidle' });
	let facts = await reportFacts(page);
	check(toneOf(facts.boxClass) === 'caution' && /^\s*Caution/.test(facts.boxText), 'mild safety mention: the result box is orange and says Caution');
	check(facts.tagged.length === 1 && facts.tagged[0] === 'Caution', `mild safety mention: the legend tags Caution as "This product" (${facts.tagged.join(', ')})`);
	check(facts.lifted === '', 'mild safety mention (the checker\'s own caution level): no extra note');
	check(facts.safetyBar === 'orange', 'mild safety mention: the safety bar is orange');
	check(facts.marks.length > 0 && facts.marks.every((c) => c.includes('bg-warning') && !c.includes('destructive')), 'highlighted words are amber, not red');
	await page.screenshot({ path: 'tests/e2e/shots/wording_report_mild.png', fullPage: true });
	await axe(page, 'report with a mild safety mention');
	// The labels card is short: four labels, no table. (The table lives on the FAQ page, checked below.)
	check((await page.getByRole('button', { name: 'View full detail' }).count()) === 0 && (await page.locator('#report-guide [data-slot="table"]').count()) === 0, 'the labels card on a report has no full-detail table');
	await page.getByRole('tab', { name: /Reviews/ }).click();
	await page.waitForTimeout(700);
	let tag = await page.evaluate(() => [...document.querySelectorAll('#report-evidence article [data-slot="badge"]')].find((b) => b.textContent.trim() === 'Safety problem')?.className ?? '');
	check(toneOf(tag) === 'caution', 'mild safety mention: the review\'s "Safety problem" tag is orange');

	await page.goto(reportUrl(0), { waitUntil: 'networkidle' });
	facts = await reportFacts(page);
	check(toneOf(facts.boxClass) === 'safety' && /^\s*Safety reports/.test(facts.boxText) && facts.tagged[0] === 'Safety reports' && facts.safetyBar === 'red', 'serious reports: red box, "Safety reports", legend tag and red bar');
	await page.getByRole('tab', { name: /Reviews/ }).click();
	await page.waitForTimeout(700);
	tag = await page.evaluate(() => [...document.querySelectorAll('#report-evidence article [data-slot="badge"]')].find((b) => b.textContent.trim() === 'Safety problem')?.className ?? '');
	check(toneOf(tag) === 'safety', 'serious reports: the review\'s "Safety problem" tag is red');
	await page.screenshot({ path: 'tests/e2e/shots/wording_report_serious.png' });

	for (const [i, why] of [[4, 'result is "No warning signs found"'], [5, 'too few reviews for a result']]) {
		await page.goto(reportUrl(i), { waitUntil: 'networkidle' });
		facts = await reportFacts(page);
		check(toneOf(facts.boxClass) === 'caution' && facts.tagged[0] === 'Caution' && /is shown as Caution because 1 review mentions a safety concern/.test(facts.lifted), `one safety mention while the ${why}: orange, with a note saying why`);
	}
	await page.screenshot({ path: 'tests/e2e/shots/wording_report_lifted.png', fullPage: true });
	for (const [i, kind] of [[3, 'clear'], [6, 'unknown'], [7, 'unknown'], [8, 'unknown']]) {
		await page.goto(reportUrl(i), { waitUntil: 'networkidle' });
		facts = await reportFacts(page);
		check(toneOf(facts.boxClass) === kind && facts.tagged[0] === NAMES[kind] && facts.lifted === '', `report "${fake[i].name.replace(' power bank', '')}": ${NAMES[kind]}, tagged in the legend`);
	}
	await axe(page, 'report with no result yet');

	// FAQ: the same table.
	await page.goto(base + '/app/faq', { waitUntil: 'networkidle' });
	await settle(page, 800);
	const faq = await page.evaluate(() => [...document.querySelectorAll('[data-slot="table"] tbody tr')].map((tr) => [...tr.children].map((td) => td.textContent.trim())));
	check(faq.length === 6 && faq.every((row) => row.length === 3 && ['Safety reports', 'Caution', 'No warnings', 'No result yet'].includes(row[1])), 'FAQ: every result lists the group it is shown as');
	await axe(page, 'FAQ');
	await page.screenshot({ path: 'tests/e2e/shots/wording_faq.png', fullPage: true });

	// ---- 2. One word for the action -----------------------------------------------------------------
	const BANNED = [
		[/\banalyze\b/i, '"Analyze"'],
		[/scan a product/i, '"Scan a product"'],
		[/saved analys[ie]s/i, '"saved analysis"'],
		[/no warning signs(?! found)/i, '"No warning signs"'],
		[/not enough reviews(?! to judge)/i, '"Not enough reviews"'],
		[/Safety report(?!s)/, '"Safety report" (singular chip)'],
		[/spot fakes/i, '"Spot fakes"'],
		[/a safer you/i, '"A safer you"'],
		[/scan bar/i, '"scan bar"']
	];
	const sweep = async (label, routes) => {
		const hits = [];
		for (const route of routes) {
			await page.goto(base + route, { waitUntil: 'networkidle' });
			await settle(page, 900);
			const text = await page.evaluate(() => document.body.innerText + ' ' + [...document.querySelectorAll('[aria-label],[title],[placeholder]')].map((el) => `${el.getAttribute('aria-label') ?? ''} ${el.getAttribute('title') ?? ''} ${el.getAttribute('placeholder') ?? ''}`).join(' '));
			for (const [pattern, name] of BANNED) if (pattern.test(text)) hits.push(`${route.slice(0, 22)}: ${name}`);
		}
		check(hits.length === 0, `${label}: none of the old words are left${hits.length ? ' -> ' + hits.join('; ') : ''}`);
	};
	await sweep('signed-in screens', ['/', '/app/home', '/app/analyze', '/app/products', '/app/history', '/app/wishlist', '/app/settings', '/app/about', '/app/faq', '/app/extension', `/app/report?link=${encodeURIComponent(fake[1].link)}`]);

	await page.goto(base + '/app/analyze', { waitUntil: 'networkidle' });
	await settle(page, 800);
	check(await page.getByRole('heading', { level: 1, name: 'Check a product' }).isVisible(), 'the page is called "Check a product"');
	check(await page.getByRole('button', { name: 'Check this product', exact: true }).isVisible(), 'its main button says "Check this product"');
	check(await page.getByRole('link', { name: 'Check a product' }).first().isVisible(), 'the side menu says "Check a product"');
	await page.locator('#search-query').fill('https://www.lazada.com.ph/products/brand-new-thing-i123456789.html');
	check(await page.getByRole('button', { name: 'Check this Lazada PH product' }).isVisible(), 'a new link offers "Check this Lazada PH product"');
	await page.locator('#search-query').fill('https://shopee.ph/brand-new-thing-i.1.2');
	check(await page.getByText(/Shopee PH products are checked with the DeFaketive extension/).first().isVisible(), 'a Shopee link is not scanned here: it points to the extension');
	await page.keyboard.press('Control+k');
	await page.getByRole('dialog').getByRole('option', { name: 'Check a product' }).waitFor({ timeout: 5000 });
	check(true, 'Ctrl+K lists "Check a product"');
	await page.keyboard.type('analyze');
	await page.waitForTimeout(300);
	check(await page.getByRole('dialog').getByRole('option', { name: 'Check a product' }).isVisible(), 'typing the old word "analyze" in Ctrl+K still finds it');
	await page.keyboard.press('Escape');
	check(errors.length === 0, `no browser errors signed in${errors.length ? ': ' + errors[0] : ''}`);
	await context.close();
}

// ---- 4 (+2). The landing page and the guest screens ----------------------------------------------------
{
	const { context, page, errors } = await open({ signedIn: false });
	await page.goto(base + '/', { waitUntil: 'networkidle' });
	await settle(page, 1200);
	check(await page.getByRole('heading', { level: 1, name: 'See what buyers report before you buy' }).isVisible(), 'landing headline: "See what buyers report before you buy"');
	check(await page.getByText('Real reviews · Real buyers · Their own words').isVisible(), 'landing line above it: "Real reviews · Real buyers · Their own words"');
	check((await page.title()) === 'DeFaketive · See what buyers report before you buy', 'the browser tab says the same');
	check(await page.getByRole('heading', { name: 'Check a product' }).isVisible() && (await page.getByRole('button', { name: 'Check', exact: true }).isVisible()), 'landing box: "Check a product" with a "Check" button');
	await page.screenshot({ path: 'tests/e2e/shots/wording_landing.png' });
	await axe(page, 'landing');
	const BANNED = [[/\banalyze\b/i, '"Analyze"'], [/scan a product/i, '"Scan a product"'], [/no warning signs(?! found)/i, '"No warning signs"'], [/spot fakes/i, '"Spot fakes"'], [/a safer you/i, '"A safer you"'], [/Safety report(?!s)/, '"Safety report"']];
	const hits = [];
	for (const route of ['/', '/scan', '/extension', `/scan/report?link=${encodeURIComponent(fake[1].link)}`]) {
		await page.goto(base + route, { waitUntil: 'networkidle' });
		await settle(page, 1200);
		const text = await page.evaluate(() => document.body.innerText + ' ' + [...document.querySelectorAll('[aria-label],[title],[placeholder]')].map((el) => `${el.getAttribute('aria-label') ?? ''} ${el.getAttribute('title') ?? ''}`).join(' '));
		for (const [pattern, name] of BANNED) if (pattern.test(text)) hits.push(`${route.slice(0, 14)}: ${name}`);
	}
	check(hits.length === 0, `guest screens: none of the old words are left${hits.length ? ' -> ' + hits.join('; ') : ''}`);
	const facts = await reportFacts(page);
	check(toneOf(facts.boxClass) === 'caution' && facts.tagged[0] === 'Caution', 'guest report: the mild safety mention is orange there too');
	check(errors.length === 0, `no browser errors as a guest${errors.length ? ': ' + errors[0] : ''}`);
	await context.close();
}

// ---- Dark mode and phone -----------------------------------------------------------------------------
{
	const { context, page } = await open({ scheme: 'dark' });
	await page.goto(reportUrl(1), { waitUntil: 'networkidle' });
	await reportFacts(page);
	await axe(page, 'report with a mild safety mention, dark');
	await page.screenshot({ path: 'tests/e2e/shots/wording_report_mild_dark.png' });
	await page.goto(base + '/app/faq', { waitUntil: 'networkidle' });
	await axe(page, 'FAQ, dark');
	await context.close();
}
{
	const { context, page } = await open({ width: 390, height: 844 });
	for (const route of ['/app/faq', '/app/products', '/app/analyze', `/app/report?link=${encodeURIComponent(fake[4].link)}`]) {
		await page.goto(base + route, { waitUntil: 'networkidle' });
		await settle(page, 1200);
		const wide = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
		check(wide <= 1, `phone: ${route.slice(0, 16)} does not scroll sideways`);
	}
	await page.screenshot({ path: 'tests/e2e/shots/wording_phone_report.png', fullPage: true });
	await context.close();
}

await browser.close();
console.log(failures ? `\n${failures} check(s) FAILED` : '\nAll checks passed.');
process.exit(failures ? 1 : 0);
