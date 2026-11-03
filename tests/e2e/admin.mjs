// The admin side (src/routes/admin, admin_api.py): the /admin page of the app, reached by signing in on the same
// sign-in page as everyone, for the one admin account only. There is exactly one admin, Admin@defake.com (the server makes it). It lists the accounts with names and emails,
// adds shopper accounts (it cannot delete any) and changes the daily limits. The admin account is admin-only: the shopping app
// refuses it, and nobody else can open the admin page.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import { PASSWORD, signUp } from './_signin.mjs';

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
	const phonePage = await phone.newPage();
	await phonePage.goto(base + '/admin', { waitUntil: 'networkidle' });
	await phonePage.locator(`li[data-account="admin@defake.com"]`).waitFor({ timeout: 15000 });
	check((await phonePage.locator('table').isVisible()) === false, 'phone: accounts are cards, not the table');
	check(await noSideways(phonePage), 'phone: the Accounts tab does not scroll sideways');
	await phonePage.screenshot({ path: 'tests/e2e/shots/admin_phone.png' });
	await phonePage.getByRole('tab', { name: 'Daily limits' }).click();
	await phonePage.getByLabel('Whole site').waitFor({ timeout: 10000 });
	check(await noSideways(phonePage), 'phone: the Daily limits tab does not scroll sideways');
	await phone.close();
}

check(errors.length === 0, `no page errors${errors.length ? ': ' + errors.join(' | ') : ''}`);
await shopper.context.close();
await browser.close();
console.log(failures ? `\n${failures} check(s) failed` : '\nAll admin checks passed.');
process.exit(failures ? 1 : 0);
