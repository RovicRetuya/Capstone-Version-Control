// The admin side (src/routes/admin, admin_api.py): the /admin page of the app, reached by signing in on the same
// sign-in page as everyone, for the one admin account only. There is exactly one admin, Admin@defake.com (the server makes it). It lists the accounts with names and emails,
// adds shopper accounts (it cannot delete any) and changes the daily limits. The admin account is admin-only: the shopping app
// refuses it, and nobody else can open the admin page.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import { closeTour, PASSWORD, signUp } from './_signin.mjs';

const base = process.env.BASE || 'http://localhost:5173';
fs.mkdirSync('tests/e2e/shots', { recursive: true });
const axeSource = fs.readFileSync('node_modules/axe-core/axe.min.js', 'utf8');

let failures = 0;
const check = (ok, what) => {
	console.log(`${ok ? 'PASS' : 'FAIL'}  ${what}`);
	if (!ok) failures += 1;
};
const axeCheck = async (page, what) => {
	await page.evaluate(axeSource);
	const result = await page.evaluate(() => axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } }));
	check(result.violations.length === 0, `accessibility: ${what}${result.violations.length ? ' -> ' + result.violations.map((v) => `${v.id} (${v.nodes[0]?.target.join(' ')})`).join(', ') : ''}`);
};
// Against the phone's own width: a phone page can widen itself to fit what spills over, and then innerWidth grows too.
const noSideways = (page, width = 390) => page.evaluate((w) => document.documentElement.scrollWidth <= w + 1 && [...document.querySelectorAll('main *')].every((el) => el.getBoundingClientRect().right <= w + 1), width);

const ADMIN_EMAIL = 'Admin@defake.com';
const ADMIN_PASSWORD = 'Admin@defake.com';

const browser = await chromium.launch({ channel: 'chrome', headless: true });
async function open(options = {}) {
	const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, ...options });
	// The first-visit intro screen would cover the page: say it has been seen (as responsive.mjs does).
	await context.addInitScript(() => sessionStorage.setItem('splash-seen', '1'));
	const page = await context.newPage();
	const errors = [];
	page.on('pageerror', (error) => errors.push(error.message));
	return { context, page, errors };
}
const rowOf = (page, email) => page.locator(`tr[data-account="${email}"]`);
// The app's one sign-in page: the admin account lands on /admin, anyone else in the app.
async function signIn(page, email, password) {
	await page.goto(base + '/enter', { waitUntil: 'networkidle' });
	await page.locator('#enter-email').waitFor({ timeout: 15000 });
	await page.locator('#enter-email').fill(email);
	await page.locator('#enter-password').fill(password);
	await page.getByRole('main').getByRole('button', { name: 'Sign in', exact: true }).click();
}

// ---- 1. The shopping app has no way in -------------------------------------------------------------------------
const shopper = await open();
const shopperWho = await signUp(shopper.context, base, 'Plain Shopper');
{
	const { page } = shopper;
	await page.goto(base + '/app/home', { waitUntil: 'networkidle' });
	await page.locator('[data-sidebar="menu-button"][href="/app/home"]').waitFor({ timeout: 20000 });
	check((await page.locator('[data-sidebar="sidebar"]').getByText(/admin/i).count()) === 0, 'shopping app: no admin item in the menu');
	await page.keyboard.press('Control+k');
	const palette = page.getByRole('dialog');
	await palette.getByRole('option', { name: 'Home', exact: true }).waitFor({ timeout: 5000 });
	await page.keyboard.type('admin');
	await page.waitForTimeout(300);
	check((await palette.getByRole('option', { name: /admin/i }).count()) === 0, 'shopping app: Ctrl+K finds no admin page');
	await page.keyboard.press('Escape');
	const old = await shopper.context.request.get(base + '/api/agency/me');
	check(old.status() === 404, `the old /api/agency routes are gone (${old.status()})`);
}

// ---- 2. The admin app's sign-in -----------------------------------------------------------------------------------
const { context, page, errors } = await open();

await page.goto(base + '/admin', { waitUntil: 'networkidle' });
await page.waitForURL('**/enter', { timeout: 15000 });
check((await page.locator('table').count()) === 0, 'admin page: nobody signed in is sent to the sign-in page, no accounts shown');
await page.screenshot({ path: 'tests/e2e/shots/admin_signin.png' });

{
	const plain = await open();
	await signIn(plain.page, shopperWho.email, PASSWORD);
	await plain.page.waitForURL('**/app/home', { timeout: 15000 });
	check(true, 'sign-in: a shopper account goes to the shopping app');
	await plain.page.goto(base + '/admin', { waitUntil: 'networkidle' });
	await plain.page.waitForURL('**/enter', { timeout: 15000 });
	check(true, 'admin page: a signed-in shopper is sent away from it');
	await plain.context.close();
}
await signIn(page, ADMIN_EMAIL, 'not the password at all');
await page.getByText('Email or password is incorrect.', { exact: true }).waitFor({ timeout: 10000 });
check(true, 'sign-in: a wrong password is refused');
await signIn(page, ADMIN_EMAIL, ADMIN_PASSWORD);
await page.waitForURL('**/admin', { timeout: 15000 });
await page.getByRole('heading', { name: 'Admin', exact: true }).waitFor({ timeout: 15000 });
check(true, 'sign-in: Admin@defake.com lands on the admin page');
const shopSide = await (await context.request.get(base + '/api/auth/me')).json();
check(!shopSide.user, 'signing in as the admin does not sign in to the shopping app');

// The admin account is admin-only.
{
	const tryShop = await open();
	const answer = await tryShop.context.request.post(base + '/api/auth/login', { data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD } });
	check(answer.status() === 403, `shopping app: refuses the admin account (${answer.status()})`);
	await tryShop.page.goto(base + '/', { waitUntil: 'networkidle' });
	await tryShop.page.getByRole('button', { name: 'Sign in' }).first().click();
	const dialog = tryShop.page.getByRole('dialog');
	await dialog.getByLabel('Email').fill(ADMIN_EMAIL);
	await dialog.getByLabel('Password', { exact: true }).fill(ADMIN_PASSWORD);
	await dialog.getByRole('button', { name: 'Sign in' }).last().click();
	await tryShop.page.waitForURL('**/admin', { timeout: 10000 });
	check(true, 'the sign-in pop-up takes the admin to the admin page');
	await tryShop.context.close();
}

// ---- 3. Accounts --------------------------------------------------------------------------------------------------
await rowOf(page, shopperWho.email).waitFor({ timeout: 10000 });
const shopperRow = rowOf(page, shopperWho.email);
check((await shopperRow.innerText()).includes('Plain Shopper'), 'accounts: the shopper is listed with their name and email');
check((await shopperRow.getByText('Shopper', { exact: true }).count()) === 1, 'accounts: the shopper is labelled Shopper');
check((await shopperRow.getByRole('button', { name: /admin/i }).count()) === 0, 'accounts: no button makes an admin');
const meRow = rowOf(page, 'admin@defake.com');
check((await meRow.getByText('Admin', { exact: true }).count()) === 1 && (await meRow.getByText('This is you').count()) === 1, 'accounts: the admin row says Admin and "This is you"');
check((await meRow.getByRole('button').count()) === 0, 'accounts: the admin cannot be deleted');
await axeCheck(page, 'the Accounts tab (light)');
await page.screenshot({ path: 'tests/e2e/shots/admin_accounts.png' });

await page.getByLabel('Search accounts').fill(shopperWho.email);
await page.waitForFunction((email) => document.querySelectorAll('tr[data-account]').length === 1 && document.querySelector(`tr[data-account="${email}"]`), shopperWho.email, { timeout: 10000 });
check(true, 'search: an email finds just that account');
await page.getByLabel('Search accounts').fill('no-such-person-anywhere');
await page.getByText('No accounts match', { exact: true }).waitFor({ timeout: 10000 });
check(true, 'search: nothing found says so');
await page.getByRole('button', { name: 'Clear the search' }).click();
await rowOf(page, 'admin@defake.com').waitFor({ timeout: 10000 });

// Add an account: it appears in the list and can sign in to the shopping app.
const addedEmail = `added${Date.now()}@example.com`;
await page.getByRole('button', { name: 'Add account' }).click();
const addDialog = page.getByRole('dialog');
await addDialog.getByLabel('Full name').fill('Added By Admin');
await addDialog.getByLabel('Email').fill('not an email');
await addDialog.getByLabel('Password', { exact: true }).fill('short');
await addDialog.getByRole('button', { name: 'Add account' }).click();
await addDialog.getByText('Use at least 8 characters.').waitFor({ timeout: 5000 });
check(true, 'add account: a short password is refused in the pop-up');
await addDialog.getByLabel('Password', { exact: true }).fill(PASSWORD);
await addDialog.getByRole('button', { name: 'Add account' }).click();
await addDialog.getByText('Enter a valid email address', { exact: false }).waitFor({ timeout: 10000 });
check(true, 'add account: a bad email is refused by the server');
await addDialog.getByLabel('Email').fill(shopperWho.email);
await addDialog.getByRole('button', { name: 'Add account' }).click();
await addDialog.getByText('already exists', { exact: false }).waitFor({ timeout: 10000 });
check(true, 'add account: an email already in use is refused');
await axeCheck(page, 'the add-account pop-up');
await addDialog.getByLabel('Email').fill(addedEmail);
await addDialog.getByRole('button', { name: 'Add account' }).click();
await rowOf(page, addedEmail).waitFor({ timeout: 10000 });
check(true, 'add account: the new account is in the list');
const addedShopper = await open();
const signedIn = await addedShopper.context.request.post(base + '/api/auth/login', { data: { email: addedEmail, password: PASSWORD } });
check(signedIn.ok(), 'add account: the new account signs in to the shopping app with the password given');
await addedShopper.context.close();

// The admin cannot delete accounts: no Delete button anywhere, and the server refuses a request for it.
const kept = await open();
const keptWho = await signUp(kept.context, base, 'Keep Me');
await page.reload({ waitUntil: 'networkidle' });
await rowOf(page, keptWho.email).waitFor({ timeout: 10000 });
check((await page.getByRole('button', { name: /delete/i }).count()) === 0, 'delete: the Accounts tab has no Delete button');
const keptId = (await (await page.request.get(`${base}/api/admin/accounts?q=${encodeURIComponent(keptWho.email)}`)).json()).accounts[0].id;
const refusedDelete = await page.request.delete(`${base}/api/admin/accounts/${keptId}`);
check(refusedDelete.status() === 403, 'delete: the server refuses to delete an account');
check(!!(await (await kept.context.request.get(base + '/api/auth/me')).json()).user, 'delete: the account is still signed in and still there');
await kept.context.close();

await page.emulateMedia({ colorScheme: 'dark' });
await page.evaluate(() => document.documentElement.classList.add('dark'));
await axeCheck(page, 'the Accounts tab (dark)');
await page.evaluate(() => document.documentElement.classList.remove('dark'));
await page.emulateMedia({ colorScheme: 'light' });

// ---- 4. Daily limits ----------------------------------------------------------------------------------------------
const before = (await (await context.request.get(base + '/api/admin/limits')).json()).limits;
await page.getByRole('tab', { name: 'Daily limits' }).click();
await page.getByLabel('Whole site').waitFor({ timeout: 10000 });
check(page.url().endsWith('/admin?tab=limits'), 'limits: the tab is in the address');
check((await page.getByLabel('Whole site').inputValue()) === String(before.site), `limits: shows the site limit (${before.site})`);
const save = page.getByRole('button', { name: 'Save limits' });
check(await save.isDisabled(), 'limits: Save waits for a change');
await page.getByLabel('Each account').fill('abc');
check((await page.getByText(/Use a whole number from 0 to/).count()) === 1 && (await save.isDisabled()), 'limits: a word is refused before saving');
await page.getByLabel('Each account').fill(String(before.account + 7));
await save.click();
await page.getByText('Daily limits saved.', { exact: false }).waitFor({ timeout: 10000 });
check(true, 'limits: saving says so');
await page.reload({ waitUntil: 'networkidle' });
await page.getByLabel('Each account').waitFor({ timeout: 10000 });
check((await page.getByLabel('Each account').inputValue()) === String(before.account + 7), 'limits: a reload opens the same tab and keeps the new number');
await axeCheck(page, 'the Daily limits tab');
await page.screenshot({ path: 'tests/e2e/shots/admin_limits.png' });
await context.request.put(base + '/api/admin/limits', { data: before });

// ---- 4b. The Products page's choices ------------------------------------------------------------------------------
{
	// Before the admin changes anything, the page names its lists in plain words and offers every choice.
	// The Products page is for signed-in accounts, so the visitor is a shopper (the welcome tour is skipped).
	const visitor = await open();
	await signUp(visitor.context, base, 'Filter Viewer');
	await visitor.page.goto(base + '/app/products', { waitUntil: 'networkidle' });
	await closeTour(visitor.page);
	const labelsOf = async (p) => (await p.locator('label').allInnerTexts()).map((t) => t.trim());
	let labels = await labelsOf(visitor.page);
	check(labels.includes('Filter by result') && labels.includes('Order by'), 'products: the lists are called "Filter by result" and "Order by"');
	check(!labels.includes('Show') && !labels.includes('Sort by'), 'products: the old "Show" and "Sort by" labels are gone');
	await visitor.page.getByLabel('Order by').first().click();
	check((await visitor.page.getByRole('option').count()) === 3, 'products: every order is offered at first');
	await visitor.page.keyboard.press('Escape');

	// The admin's tab.
	await page.goto(base + '/admin', { waitUntil: 'networkidle' });
	await page.getByRole('tab', { name: 'Products page' }).click();
	check(page.url().endsWith('/admin?tab=filters'), 'filters: the tab is in the address');
	await page.getByRole('checkbox', { name: 'Most reported problems' }).waitFor({ timeout: 10000 });
	check((await page.getByRole('button', { name: 'Save choices' }).isDisabled()), 'filters: Save is off until something changes');
	await page.waitForTimeout(600); // the tab fades in; axe would measure a half-faded text
	await axeCheck(page, 'the Products page tab (light)');
	await page.screenshot({ path: 'tests/e2e/shots/admin_filters.png' });

	// Turn "Most reported problems" off and start on "Most reviews analyzed". Leaving only one order hides that list.
	await page.getByRole('checkbox', { name: 'Most reported problems' }).click();
	await page.getByRole('checkbox', { name: 'Fewest reported problems' }).click();
	check(await page.getByRole('radio', { name: 'Most reviews analyzed: start on this choice' }).isChecked(), 'filters: turning off the starting order moves the start to one still offered');
	check((await page.getByText('With one choice left').count()) === 1, 'filters: one choice left says the list will be hidden');
	await page.getByRole('checkbox', { name: 'Fewest reported problems' }).click();
	check((await page.getByText('With one choice left').count()) === 0, 'filters: two choices left, the warning goes');
	await page.getByRole('checkbox', { name: 'No result yet' }).click();
	await page.getByRole('button', { name: 'Save choices' }).click();
	await page.getByText('Saved. The Products page shows these choices from now on.').waitFor({ timeout: 10000 });
	check(true, 'filters: the admin saves the choices');

	// Turning every choice off is refused on the page.
	for (const name of ['All products', 'Caution or safety reports', 'Safety reports', 'Caution', 'No warnings']) {
		await page.getByRole('checkbox', { name, exact: true }).click();
	}
	check((await page.getByText('Keep at least one choice on.').count()) === 1 && (await page.getByRole('button', { name: 'Save choices' }).isDisabled()), 'filters: no choice left is refused before it is sent');
	await page.getByRole('button', { name: 'Offer every choice' }).click();
	await page.getByRole('button', { name: 'Offer every choice' }).waitFor();
	// Put the saved choices back to what the visitor test below expects: reload shows what the server kept.
	await page.reload({ waitUntil: 'networkidle' });
	await page.getByRole('checkbox', { name: 'Most reported problems' }).waitFor({ timeout: 10000 });
	check(!(await page.getByRole('checkbox', { name: 'Most reported problems' }).isChecked()), 'filters: a reload shows the choices the server kept');

	// A visitor now sees only what the admin left on, and the page starts on the admin's order.
	await visitor.page.reload({ waitUntil: 'networkidle' });
	await closeTour(visitor.page);
	check((await visitor.page.getByLabel('Order by').count()) > 0, 'products: the list of orders shows while two are offered');
	labels = await labelsOf(visitor.page);
	check(labels.includes('Filter by result') && labels.includes('Order by'), 'products: both lists show after the change');
	check((await visitor.page.getByText('appear first.').innerText()).includes('most reviews analyzed'), 'products: the first line names the order the admin starts on');
	await visitor.page.getByLabel('Filter by result').first().click();
	const offered = await visitor.page.getByRole('option').allInnerTexts();
	check(!offered.includes('No result yet') && offered.includes('All products'), 'products: a result the admin turned off is not offered');
	await visitor.page.keyboard.press('Escape');

	// Back to every choice, so the next run starts the same way.
	const all = await context.request.get(base + '/api/admin/filters');
	const defaults = (await all.json()).defaults;
	const restored = await context.request.put(base + '/api/admin/filters', { data: defaults });
	check(restored.ok(), 'filters: every choice is offered again');
	await visitor.context.close();
}

// ---- 4c. Options the admin makes up -------------------------------------------------------------------------------
{
	const visitor = await open();
	await signUp(visitor.context, base, 'Option Viewer');
	const savedProducts = (await (await visitor.context.request.get(base + '/api/saved/products')).json()).products;
	const rating = (p) => (Number.isFinite(Number(p.rating)) && Number(p.rating) > 0 ? Number(p.rating) : null);
	const byLink = new Map(savedProducts.map((p) => [String(p.link), p])); // by the exact link: a few listings are saved under more than one address
	const shownLinks = async (p) => [...new Set(await p.locator('a[href^="/app/report?link="]').evaluateAll((links) => links.map((a) => new URL(a.href).searchParams.get('link'))))];
	const keyOf = (link) => String(link);

	await page.goto(base + '/admin?tab=filters', { waitUntil: 'networkidle' });
	await page.getByRole('checkbox', { name: 'Most reported problems' }).waitFor({ timeout: 10000 });
	const addButtons = page.getByRole('button', { name: 'Add your own option' });

	// A filter: the name starts as a suggestion from the number.
	await addButtons.nth(0).click();
	const form = page.getByRole('form', { name: 'Add your own option' });
	check((await form.getByLabel('Name visitors see').inputValue()) === 'Rated 4 stars or more', 'custom: the name starts as a suggestion ("Rated 4 stars or more")');
	// Mistakes are named before anything is sent.
	await form.getByLabel('Number').fill('9');
	await form.getByRole('button', { name: 'Add option' }).click();
	check((await form.getByRole('alert').innerText()).includes('from 1 to 5'), 'custom: a rating of 9 is refused with the range');
	await form.getByLabel('Number').fill('4');
	await form.getByLabel('Name visitors see').fill('');
	await form.getByRole('button', { name: 'Add option' }).click();
	check((await form.getByRole('alert').innerText()).includes('name'), 'custom: an empty name is refused');
	await form.getByLabel('Number').fill('4.5');
	await form.getByLabel('Name visitors see').fill('Rated 4.5 stars or more');
	await form.getByRole('button', { name: 'Add option' }).click();
	check((await page.getByText('Added by you').count()) === 1 && (await page.getByRole('checkbox', { name: 'Rated 4.5 stars or more' }).isChecked()), 'custom: the new filter is in the list and offered');

	// An order.
	await addButtons.nth(1).click();
	const orderForm = page.getByRole('form', { name: 'Add your own option' });
	check((await orderForm.getByLabel('Name visitors see').inputValue()) === 'Highest rated', 'custom: an order starts as "Highest rated"');
	await orderForm.getByRole('button', { name: 'Add option' }).click();
	check((await page.getByText('Added by you').count()) === 2, 'custom: the new order is in the list');

	// Edit: a name that is still the suggestion follows the number.
	await page.getByRole('button', { name: 'Edit Rated 4.5 stars or more' }).click();
	const editForm = page.getByRole('form', { name: 'Edit this option' });
	await editForm.getByLabel('Number').fill('4.8');
	check((await editForm.getByLabel('Name visitors see').inputValue()) === 'Rated 4.8 stars or more', 'custom: editing the number updates a name that was only a suggestion');
	await editForm.getByRole('button', { name: 'Update option' }).click();
	check((await page.getByRole('checkbox', { name: 'Rated 4.8 stars or more' }).count()) === 1, 'custom: the edit shows in the list');
	await page.getByRole('radio', { name: 'Highest rated: start on this choice' }).click();
	await page.getByRole('button', { name: 'Save choices' }).click();
	await page.getByText('Saved. The Products page shows these choices from now on.').waitFor({ timeout: 10000 });
	await page.reload({ waitUntil: 'networkidle' });
	await page.getByRole('checkbox', { name: 'Rated 4.8 stars or more' }).waitFor({ timeout: 10000 });
	check((await page.getByRole('radio', { name: 'Highest rated: start on this choice' }).isChecked()), 'custom: a reload keeps the options, and the start on the new order');

	// What a visitor gets: the filter keeps exactly the products with that rating, and the page starts on the new order.
	await visitor.page.goto(base + '/app/products', { waitUntil: 'networkidle' });
	await closeTour(visitor.page);
	await visitor.page.getByLabel('Filter by result').first().click();
	check((await visitor.page.getByRole('option', { name: 'Rated 4.8 stars or more' }).count()) === 1, 'products: the visitor is offered the admin-made filter');
	await visitor.page.getByRole('option', { name: 'Rated 4.8 stars or more' }).click();
	const expected = savedProducts.filter((p) => (rating(p) ?? 0) >= 4.8).length;
	await visitor.page.getByText(/products? shown/).waitFor({ timeout: 10000 });
	const shown = Number((await visitor.page.getByText(/products? shown/).innerText()).match(/\d+/)?.[0]);
	check(expected > 0 && shown === expected, `products: "Rated 4.8 stars or more" shows exactly the ${expected} products rated that high (page says ${shown})`);
	const links = await shownLinks(visitor.page);
	const ratings = links.map((link) => rating(byLink.get(keyOf(link)) ?? {}));
	check(ratings.length > 1 && ratings.every((r, i) => i === 0 || r === null || ratings[i - 1] === null || ratings[i - 1] >= r), 'products: the page started on "Highest rated" (ratings never go up down the page)');
	check(ratings.every((r) => r !== null && r >= 4.8), 'products: every product shown has a rating of 4.8 or more');

	// An order, applied: pick the other direction by removing the filter first.
	await visitor.page.getByLabel('Filter by result').first().click();
	await visitor.page.getByRole('option', { name: 'All products' }).click();
	await visitor.page.getByText(/products? shown/).waitFor();
	const allLinks = await shownLinks(visitor.page);
	const allRatings = allLinks.map((link) => rating(byLink.get(keyOf(link)) ?? {}));
	const firstUnrated = allRatings.findIndex((r) => r === null);
	const rated = firstUnrated === -1 ? allRatings : allRatings.slice(0, firstUnrated);
	check(rated.every((r, i) => i === 0 || rated[i - 1] >= r) && allRatings.slice(rated.length).every((r) => r === null), 'products: "Highest rated" puts the best first and the unrated last');
	await visitor.page.getByLabel('Order by').first().click();
	await visitor.page.getByRole('option', { name: 'Fewest reported problems' }).click();
	check((await visitor.page.getByText('appear first.').count()) === 1 || (await visitor.page.getByText(/ordered by|appear first/).count()) === 1, 'products: the line under the title follows the order');

	// Remove both: they are gone from the lists, and the page falls back to the built-in start.
	await page.getByRole('button', { name: 'Remove Rated 4.8 stars or more' }).click();
	await page.getByRole('button', { name: 'Remove Highest rated' }).click();
	check((await page.getByText('Added by you').count()) === 0 && (await page.getByRole('radio', { name: 'Fewest reported problems: start on this choice' }).isChecked()), 'custom: removing the options removes them and moves the start back to one that is left');
	await page.getByRole('button', { name: 'Save choices' }).click();
	await page.getByText('Saved. The Products page shows these choices from now on.').waitFor({ timeout: 10000 });
	await visitor.page.reload({ waitUntil: 'networkidle' });
	await closeTour(visitor.page);
	await visitor.page.getByLabel('Filter by result').first().click();
	check((await visitor.page.getByRole('option', { name: 'Rated 4.8 stars or more' }).count()) === 0, 'products: a removed option is no longer offered');
	await visitor.page.keyboard.press('Escape');

	// A marketplace option, and one more look at accessibility with a form open.
	await page.reload({ waitUntil: 'networkidle' });
	await page.getByRole('checkbox', { name: 'Most reported problems' }).waitFor({ timeout: 10000 });
	await addButtons.nth(0).click();
	await page.getByRole('form', { name: 'Add your own option' }).getByLabel('Filter by').click();
	await page.getByRole('option', { name: 'Marketplace' }).click();
	await page.getByRole('form', { name: 'Add your own option' }).getByLabel('Marketplace').click();
	await page.getByRole('option', { name: 'Shopee PH' }).click();
	check((await page.getByLabel('Name visitors see').inputValue()) === 'Shopee PH only', 'custom: a marketplace option is named from the marketplace');
	await page.waitForTimeout(600);
	await axeCheck(page, 'the Products page tab with the add form open');
	await page.getByRole('button', { name: 'Cancel' }).click();
	check((await page.getByText('Added by you').count()) === 0, 'custom: cancelling adds nothing');
	await visitor.context.close();
}

// ---- 4d. Problem reports: sent from the app, read on the admin page ---------------------------------------------
{
	const sender = await open();
	const who = await signUp(sender.context, base, 'Report Sender');
	const stamp = Date.now();
	const message = `The scan said it was done but no report opened (${stamp}).`;
	await sender.page.goto(base + '/app/home', { waitUntil: 'networkidle' });
	await closeTour(sender.page);

	// The button is in the header, and the pop-up checks the message before sending.
	await sender.page.getByRole('button', { name: 'Report a problem' }).first().click();
	const dialog = sender.page.getByRole('dialog', { name: 'Report a problem' });
	await dialog.waitFor({ timeout: 10000 });
	check((await dialog.getByLabel('Your email (optional)').inputValue()) === who.email, 'report: the account email is filled in');
	check((await dialog.getByText('/app/home').count()) === 1, 'report: the page the person is on goes with it');
	await dialog.getByLabel('What happened?').fill('too short');
	await dialog.getByRole('button', { name: 'Send report' }).click();
	check((await dialog.getByRole('alert').innerText()).includes('at least 10'), 'report: a message that is too short is refused before it is sent');
	await dialog.getByLabel('What is it about?').click();
	await sender.page.getByRole('option', { name: 'A scan failed or got stuck' }).click();
	await dialog.getByLabel('What happened?').fill(message);
	await sender.page.waitForTimeout(600); // the kind list is still animating away; axe would see it half-closed
	await axeCheck(sender.page, 'the Report a problem pop-up');
	await dialog.getByRole('button', { name: 'Send report' }).click();
	await sender.page.getByText('Thanks. Your report was sent.').waitFor({ timeout: 10000 });
	await dialog.waitFor({ state: 'detached', timeout: 10000 });
	check(true, 'report: it is sent, thanked, and the pop-up closes');

	// The same form opens from the user menu and from the FAQ page.
	await sender.page.getByRole('button', { name: new RegExp(who.name) }).click();
	await sender.page.getByRole('menuitem', { name: 'Report a problem' }).click();
	await sender.page.getByRole('dialog', { name: 'Report a problem' }).waitFor({ timeout: 10000 });
	check((await sender.page.getByRole('dialog').getByLabel('What happened?').inputValue()) === '', 'report: it opens clean from the user menu');
	await sender.page.keyboard.press('Escape');
	await sender.page.goto(base + '/app/faq', { waitUntil: 'networkidle' });
	await sender.page.getByRole('button', { name: 'Report a problem' }).last().click(); // the header's comes first, the page's last
	check(await sender.page.getByRole('dialog', { name: 'Report a problem' }).isVisible(), 'report: the FAQ page has the button too');
	await sender.context.close();

	// The admin side.
	await page.goto(base + '/admin?tab=reports', { waitUntil: 'networkidle' });
	check((await page.getByRole('tab', { name: /Reports/ }).innerText()).match(/\d/) !== null, 'admin: the Reports tab says how many are new');
	const card = page.locator('li[data-report]', { hasText: String(stamp) });
	await card.waitFor({ timeout: 10000 });
	const text = await card.innerText();
	check(text.includes('A scan failed or got stuck') && text.includes(message), 'admin: the report shows what it is about and what was written');
	check(text.includes('Report Sender') && text.includes(who.email), 'admin: it shows which account sent it');
	check(text.includes('/app/home') && /New/.test(text), 'admin: it shows the page, and that it is new');
	check((await card.getByRole('link', { name: who.email }).getAttribute('href')).startsWith(`mailto:${who.email}`), 'admin: the sender can be written back to');
	await page.waitForTimeout(600);
	await axeCheck(page, 'the Reports tab (light)');
	await page.screenshot({ path: 'tests/e2e/shots/admin_reports.png' });

	// Search, narrow, and mark it handled.
	await page.getByLabel('Search reports').fill(String(stamp));
	await page.waitForTimeout(700);
	check((await page.locator('li[data-report]').count()) === 1, 'admin: searching for words in the message finds just that report');
	await page.getByLabel('Search reports').fill('nothing of the sort xyzzy');
	await page.getByText('No reports match').waitFor({ timeout: 10000 });
	check(true, 'admin: a search with no match says so');
	await page.getByLabel('Search reports').fill(String(stamp));
	await card.waitFor({ timeout: 10000 });
	await card.getByRole('button', { name: 'Mark as handled' }).click();
	await card.waitFor({ state: 'detached', timeout: 10000 });
	check(true, 'admin: marking it handled takes it off the list of reports that need a look');
	await page.getByLabel('Show', { exact: true }).click();
	await page.getByRole('option', { name: 'Handled' }).click();
	await card.waitFor({ timeout: 10000 });
	check((await card.getByRole('button', { name: 'Open again' }).count()) === 1, 'admin: it is under Handled, with Open again');
	await card.getByRole('button', { name: 'Open again' }).click();
	await card.waitFor({ state: 'detached', timeout: 10000 });
	await page.getByLabel('Show', { exact: true }).click();
	await page.getByRole('option', { name: 'All reports' }).click();
	await card.waitFor({ timeout: 10000 });
	check(/New/.test(await card.innerText()), 'admin: opened again, it is new');
	await page.getByLabel('Kind', { exact: true }).click();
	await page.getByRole('option', { name: 'Sign in or account' }).click();
	await page.getByText('No reports match').waitFor({ timeout: 10000 });
	check(true, 'admin: narrowing to another kind hides it');
	await page.getByLabel('Kind', { exact: true }).click();
	await page.getByRole('option', { name: 'Any kind' }).click();
	await card.waitFor({ timeout: 10000 });
	check((await page.getByLabel('Search reports').inputValue()) === String(stamp), 'admin: the search is kept while the kind changes');
}

// ---- 5. Own password ----------------------------------------------------------------------------------------------
const NEW_PASSWORD = 'a brand new password';
await page.getByRole('button', { name: 'Change password' }).click();
const pw = page.getByRole('dialog');
await pw.getByLabel('Current password').fill(ADMIN_PASSWORD);
await pw.getByLabel('New password', { exact: true }).fill(NEW_PASSWORD);
await pw.getByLabel('New password again').fill(NEW_PASSWORD);
await axeCheck(page, 'the change-password pop-up');
await pw.getByRole('button', { name: 'Change password' }).click();
await page.getByText('Your password was changed.', { exact: true }).waitFor({ timeout: 10000 });
await page.getByRole('button', { name: 'Sign out' }).click();
await page.waitForURL(base + '/', { timeout: 10000 });
await signIn(page, ADMIN_EMAIL, NEW_PASSWORD);
await page.waitForURL('**/admin', { timeout: 15000 });
check(true, 'password: changed, signed out, and back in with the new one');
// Put it back, so the next run (on the same scratch database) can sign in.
await context.request.put(base + '/api/admin/password', { data: { current_password: NEW_PASSWORD, new_password: ADMIN_PASSWORD } });

// ---- 6. Phone width -----------------------------------------------------------------------------------------------
{
	const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, storageState: await context.storageState() });
	await phone.addInitScript(() => sessionStorage.setItem('splash-seen', '1'));
	const phonePage = await phone.newPage();
	await phonePage.goto(base + '/admin', { waitUntil: 'networkidle' });
	await phonePage.locator(`li[data-account="admin@defake.com"]`).waitFor({ timeout: 15000 });
	check((await phonePage.locator('table').isVisible()) === false, 'phone: accounts are cards, not the table');
	check(await noSideways(phonePage), 'phone: the Accounts tab does not scroll sideways');
	await phonePage.screenshot({ path: 'tests/e2e/shots/admin_phone.png' });
	await phonePage.getByRole('tab', { name: 'Daily limits' }).click();
	await phonePage.getByLabel('Whole site').waitFor({ timeout: 10000 });
	check(await noSideways(phonePage), 'phone: the Daily limits tab does not scroll sideways');
	await phonePage.getByRole('tab', { name: 'Products page' }).click();
	await phonePage.getByRole('checkbox', { name: 'Most reported problems' }).waitFor({ timeout: 10000 });
	check(await noSideways(phonePage), 'phone: the Products page tab does not scroll sideways');
	await phonePage.getByRole('tab', { name: /Reports/ }).click();
	await phonePage.locator('li[data-report]').first().waitFor({ timeout: 10000 }).catch(() => {});
	check(await noSideways(phonePage), 'phone: the Reports tab does not scroll sideways');
	await phone.close();
}

check(errors.length === 0, `no page errors${errors.length ? ': ' + errors.join(' | ') : ''}`);
await shopper.context.close();
await browser.close();
console.log(failures ? `\n${failures} check(s) failed` : '\nAll admin checks passed.');
process.exit(failures ? 1 : 0);
