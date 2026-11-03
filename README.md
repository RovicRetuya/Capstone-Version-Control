# DeFaketive (shadcn version)

A second face for DeFaketive, built with [shadcn-svelte](https://shadcn-svelte.com) (SvelteKit, Tailwind v4,
Lucide icons, the plain **neutral** look with brand colours, deep navy blue and burnt mustard yellow). The original app in
`../Capstone-Version-Control-Version-1.1` is not touched.

This app only draws the screens. Everything real still happens in the original Flask app: accounts, guest
scan limits, live scans, the review checker, and the exact wording of every result. The new app asks it
for data through `/api`, so both always agree.

## Run it on another PC

This repo holds everything the app needs: the screens, and in `backend/` a copy of the original app's server, review
checker, review model and Lazada scanner, plus your saved reports as a starter set (reviewer names removed).

You need, once per PC:

1. **Windows**, with **Google Chrome**.
2. **Python 3.11** from <https://www.python.org/downloads/>. Tick **"Add python.exe to PATH"** in the installer.
3. **Node.js LTS** from <https://nodejs.org>.

Then:

1. Download this repo (green **Code** button, **Download ZIP**, and unzip it; or `git clone`).
2. Double-click **`setup.cmd`**. The first time it takes a few minutes and needs the internet: it installs the Python
   and app packages, fetches a small word list, and loads the starter reports (about 180 products).
3. Double-click **`start.cmd`**. The app opens in the browser at <http://localhost:5173>. Keep its windows open.

The first Lazada check on a new PC opens a Chrome window: log in to Lazada there once, and later checks run with no
window. If Lazada asks for a check (a puzzle), the window comes back and the app says "This scan needs you".

What is not included, on purpose: accounts, history and wishlists (each PC starts with none), your Lazada login, and
the research files (they stay in the original app's repo). The starter reports have no reviewer names or seller
replies.

For whoever keeps this repo up to date: `backend/` is a copy, made by `scripts/sync_backend.py` from the original
app beside this folder; change the original app, then run that script again. `scripts/make_starter_data.py` remakes
the starter reports from the original app's database (reading every report again with the current checker, about
70 to 90 minutes). On the developer's PC, with the original app beside this folder, `start.cmd` keeps using the
original app and its real database; `backend/` is only used where the original app is not there.

## How it is connected

```
browser  ->  Vite (localhost:5173)  --/api-->  server.py (127.0.0.1:5000)  ->  defaketive.db
                                                 = the original Flask app          instance/accounts.db
                                                 + a few read-only routes
```

- **Backend.** In development Vite passes every `/api` call straight to port 5000 (`vite.config.ts`).
- **Databases.** Nothing here has a database of its own. The original app keeps using the same two SQLite files,
  so an account made in either version works in both:
  - `defaketive.db` in the original folder: analyzed products and their reviews.
  - `instance/accounts.db` in the original folder: accounts, scan history, wishlists, guest scan counts.
- **`server.py`.** The original only lists and opens products from the visitor's own session, so a product that is
  only in `defaketive.db` (for example one somebody else scanned) could not be browsed or opened. `server.py` imports
  the original app (it is not edited) and adds two read-only routes that read the same database:
  `GET /api/saved/products` (every analyzed listing, as cards), `GET /api/saved/detail?link=` (one product with
  all its reviews and its similar products) and `GET /api/saved/popular` (products saved by two or more accounts). The Products page, Ctrl+K search, name and link lookups on Analyze
  all use them.
- **`saved_pool.py`.** Every list, report and set of similar products is built from all the saved products, and
  reading them from the database means parsing each one with all its reviews. With 27 products nobody noticed; with
  168 products and 20,609 reviews it took 2.1 seconds on every request, and more when a page asked for three things
  at once (13 Oct 2026). So `server.py` keeps them in memory, about 150 MB, and looks at the database file before
  each use: nothing changed means nothing is read, and after a scan only the product that was saved is read again.
  Measured after: the product list 0.3 seconds (was 2.9), a report 0.1 seconds (was 2.5). The original app's own
  `/api/picks`, `/api/products/detail` and `/api/wishlist/popular` are given the same kept products while they run
  inside `server.py`. The kept products are shared by all requests, so nothing in `server.py` may alter one.
- **Who sees what.** There are two kinds of data, kept apart on purpose:

  | | Where it lives | Who sees it |
  | --- | --- | --- |
  | **The shared pool**: every product anyone has analyzed, with its reviews | `products` and `reviews` tables in `defaketive.db` | Everyone. The Products page, search, and the "similar products" suggestions are all picked from it. |
  | **A person's own library**: what they scanned, opened or saved | `user_activity` and `user_wishlist` in `accounts.db`, one set of rows per account (a guest's stays in their browser) | Only that person. Home, History and Wishlist show nothing else. |

  A product enters someone's library only when they scan it, open its report or save it. A finished scan is written
  to the shared pool (so it can be recommended to others) and to the library of whoever ran it. Signing out clears
  that account's history, wishlist and last-scan card from the screen, so the next person on the same browser starts
  empty. (The original app mixes this browser's session catalog into every history; this version does not.)
- **Without `server.py`** (the plain original app on port 5000) everything still works from the session catalog;
  Products just lists fewer products and a database-only report says it could not be opened.
- **Lazada PH only** (the owner's decision, 14 Oct 2026). Every page says Lazada PH, and only a Lazada PH link can be
  checked (`SCAN_MARKETPLACES` and `scannable` in `src/lib/product.ts`; the server refuses the rest too). A Shopee or
  Temu link gets "DeFaketive checks Lazada PH products only"; if a report was saved from it before, that report still
  opens, with no "Check again". Products has no marketplace filter (22 Oct 2026): the app is Lazada only, and
  older Shopee or Temu reports simply stay in the list.
- **One listing, one entry.** Shopee and Lazada links are matched by host and path. Temu gives every product the same
  path (`/goods.html`), so its `goods_id` is part of the match. (The original's own matching ignores it, which makes
  every Temu listing look like the same product.)

## Run it

**To use it or show it: double-click `start.cmd`.** It

1. prepares the app (a build, about half a minute) only when the code changed since the last time;
2. starts `server.py` in its own window (port 5000), serves the finished build (port 5173), whose admin side is the `/admin` page (see below);
3. opens <http://localhost:5173> by itself once both answer. If the app is already running, it just opens it.

Keep both windows open while you use the app. Close them to stop it.

**To change the code: `dev.cmd`.** It starts the same server and the developer server, which updates the page as
you type. It is slower on first load, and it shows developer error pages (also Flask's own, through
`DEFAKETIVE_DEBUG=1`), which is why it is not what `start.cmd` uses.

By hand, the same thing is: `npm install` (first time only), then `npm run build` and `npm run preview -- --port 5173`
(or `npm run dev -- --port 5173`), and in another window
`..\Capstone-Version-Control-Version-1.1\.venv\Scripts\python.exe server.py`.

If the server runs somewhere else, set `DEFAKETIVE_API` first, for example
`set DEFAKETIVE_API=http://127.0.0.1:8000`. If the original app lives somewhere else, set `DEFAKETIVE_ORIGINAL`
to its folder.

## Putting it online

**For the public: `public.cmd`** (not `start.cmd`). It builds the app when needed and starts `serve.py` on
<http://127.0.0.1:8080>: one proper web server (Waitress) that serves the screens and `/api` from the same address.
Keep its window open. The admin side (`/admin`) is on the same address as everything else, so it is on the public
internet too; only the one admin account gets in, so **change its password first** (see "The admin side"). Cloudflare Tunnel then points the public web address at port 8080:

1. Make a free Cloudflare account and add the project's domain to it (Cloudflare must answer for the domain).
2. Install `cloudflared` on this PC and create a tunnel that sends the domain to `http://127.0.0.1:8080`
   (Cloudflare's dashboard: Zero Trust, Networks, Tunnels). Install it as a Windows service so it starts by itself.
3. Set the PC to never sleep, and make `public.cmd` start when Windows starts.
4. Check from a phone on mobile data, then share the address.

Without a domain, `cloudflared tunnel --url http://127.0.0.1:8080` gives a free random address that changes on
every restart: good enough for one demo day, not for a link in a paper or a survey.

`public.cmd` runs `serve.py --https --proxy cloudflare`: sign-in cookies only travel over https, and the visitor's
address is read from Cloudflare's header (only on requests that come from this PC, where `cloudflared` runs). The
app must stay ONE process: the progress of running scans lives in its memory.

**What protects the app** (`protections.py`, part of `server.py`, so it is on for `start.cmd` and the tests too):

- **Old routes closed.** `/api/upload`, `/api/evaluation`, `/api/survey`, the original's `/api/admin/overview`, `database`, `lexicons` and `logs`, and `/api/export/*`
  answered anyone without signing in; the new screens never use them. They answer 404 now
  (`DEFAKETIVE_OLD_ROUTES=1` opens them again, for the original's own page on port 5000).
- **Daily limits on new checks** (looking up a saved report is never counted). Guests: 3 per browser, as before,
  and 10 per internet connection (`DEFAKETIVE_NETWORK_DAILY_SCANS`; phone networks put many people behind one
  address). Accounts: 10 each (`DEFAKETIVE_ACCOUNT_DAILY_SCANS`). The whole site: 100
  (`DEFAKETIVE_SITE_DAILY_SCANS`). The admin can change the last three on the admin page. Counts live in the accounts database; a connection is stored only as a scrambled
  code, and counts older than a week are deleted.
- **One Chrome at a time.** Checks wait their turn and say how many are ahead. With 6 running or waiting
  (`DEFAKETIVE_MAX_ACTIVE_SCANS`), a new one is told to try again in a few minutes.
- **No copy per visitor.** A new browser session starts empty (every saved report comes from the shared pool), and
  idle sessions are forgotten. Before, every new visitor, crawlers included, got and kept a copy of the newest scan
  and saved it into the database again.
- **No reviewer names** in any report the server sends. The database keeps them; no screen ever showed them.
- **For the public only** (`serve.py`): when Lazada asks the scanner for a login or a check, the visitor is told a
  team member has to clear it at the scanning PC (the screens say "Waiting for our team").

**Backups.** `serve.py` copies both databases to `backups/daily/<date>/` a minute after it starts and then once a
day, keeping the newest seven days. By hand: `scripts\backup_databases.py`. To restore, close the app and copy a
day's two files back over the originals.

**Search engines** may list the landing page only (`static/robots.txt`): reports name real products.

### The browser extension: each shopper collects their own reviews

`extension/` is a Chrome/Edge extension that adds **Check with DeFaketive** to Lazada PH product pages. It reads the
reviews in the shopper's own browser, the same way the scanner reads them, and opens the report here
(`/check-from-extension`). The server checks that the numbers add up (`extension_api.py`, `POST
/api/extension/check`, signed-in accounts only, counted against the daily limits) and analyses them like a scan. So
the site can run on a rented server with no Chrome, no team PC and no team Lazada login; phones (no extensions) can
still open every saved report. How to install, build and publish it: `extension/README.md`.

**A recent report is not replaced.** Reviews a browser sends can be made to add up but cannot be proven real, and a
saved report is what everybody sees and what "Similar products" is picked from. So when a listing's report is less
than 30 days old (`DEFAKETIVE_EXTENSION_RECHECK_DAYS`, 0 turns the rule off), `/api/extension/check` keeps it: it
answers with that report, analyses and saves nothing, and does not count the check against the daily limits; the
page opens the saved report and says how old it is. A listing nobody has checked yet is taken on trust, so a false
first report would hold the listing for 30 days; the team can delete it, or set the variable to 0 to re-check.

With the extension doing the collecting, the server does the analysing: measured on 15 Oct 2026, `serve.py` uses
about 0.5 GB at rest and 0.62 GB at its peak with 182 reports, before the review model loads (about 0.15 GB more),
so a rented server needs 2 GB.

## Screens

| Address | Screen |
| --- | --- |
| `/` | Landing page, with a scan box, FAQ and team |
| `/scan` | **Guest screen**: check one product link without an account, with its own progress view |
| `/scan/report?link=…` | The same report as the app's, on the guest screen (no menu, no account features) |
| `/app/home` | Home, a dashboard: link box, latest scan, your numbers, **what needs a look** beside the overview, then recently checked |
| `/app/analyze` | "Check a product": paste a link or search by name, start a live scan |
| `/app/products` | Every product anyone has checked, with filters |
| `/app/report?link=…` | One product's report: result, checks, quotes, every review |
| `/app/history` | Scan history, grouped by day; filter by result and by date (any time, today, last 7 or 30 days, or a chosen range) |
| `/app/wishlist` | Saved products |
| `/app/settings` | Account, scan alerts, dark mode, clipboard fill, clear history, delete account |
| `/app/about`, `/app/faq` | About the project, questions, how results work |

Sign-in and sign-up are pop-ups that open from anywhere.

**Guests and the main app.** A guest who pastes a link on the landing page, presses "Try it free" or chooses
"Continue as guest" goes to the guest screen (`/scan`), not into the main app. The scan runs there and the report opens
there. One shortcut: a link that was already checked opens its guest report straight from the landing page, with no
second press and no free scan used (a new link still stops on the guest screen, which asks first). Creating an account
from the guest report opens the same report in the app, and the guest's scans move into the
new account. A signed-in person who opens `/scan` is sent to the app. The public header (How it works, FAQ, About) and
the public footer only link to sections of the landing page and to the guest screen.

**The app is for signed-in people only.** Every `/app/...` page is locked (`src/routes/app/+layout.svelte`): nothing of
the app is drawn until the server says who is there, and a guest who types an app address, or follows an old link, is
sent to the public screen that does the same job (`guestDestination` in `src/lib/nav.ts`):

| A guest asks for | They get |
| --- | --- |
| `/app/report?link=…` | the same report on the guest screen |
| `/app/analyze` | the guest screen, with the link kept if there was one |
| `/app/about`, `/app/faq` | that section of the landing page |
| anything else (Home, Products, History, Wishlist, Settings) | the landing page with the sign-in pop-up; after signing in they land on the page they asked for |

Signing out or deleting the account goes to the landing page without that pop-up. For a guest, Ctrl+K lists only the
public pages and "/" jumps to the guest scan box. This lock is in the browser; what protects the data is still the
server, which only ever returns an account's history and wishlist to that account. The shared pool routes
(`/api/saved/...`) are open on purpose: they hold no personal data, and the guest screen needs them to recognise a
product that was already checked and to show its report.

### The admin side: for the one admin who runs the site

The `/admin` page of the app itself (`src/routes/admin`, `src/lib/components/admin`). There is no separate app and no
extra address: the admin signs in on the same sign-in page as everyone (the landing page's *Sign in* pop-up or
`/enter`) and lands on `/admin`. It replaced the DTI agency view on 26 Oct 2026 (that view's watch list, charts,
evidence sheets and guide are gone; their tables stay in `accounts.db`, untouched).

**Its own sign-in, the admin account only** (`admin_api.py`, `/api/admin/*`). It is kept in the session as `admin_id`,
never as the shopping app's `user_id`, so the admin is not signed in to the shopping app. Any other account that signs
in goes to the shopping app, and `/admin` sends anyone who is not the admin to the sign-in page. **The admin account
is admin-only:** the shopping app's own sign-in route refuses it, and a shopping-app session of it ends on its next
request. **The main admin is `Admin@defake.com`** (password `Admin@defake.com` until the admin
changes it). **Only an admin can make another admin**, by adding an account with *Make this account an admin* ticked;
nobody becomes an admin by signing up, and no existing account is promoted. While the admin is signed in, the landing
page's header shows an **Admin** button. The admin changes their own password on the admin page ("Change
password").

**Accounts.** Every account, newest first, with its name, email, when it joined, how many products are in its History
and Wishlist, and how many checks it started today; a search by name or email. Never a password, and never which
products. Each account is labelled **Admin** or **Shopper**:

- *Add account*: the admin types a name, email and password and picks shopper or admin (the same rules as
  signing up: a real-looking email, 8+ characters). The admin hands the password over.
- No delete: the admin cannot delete accounts (the server refuses `DELETE /api/admin/accounts/<id>` with 403). A
  person deletes their own account from Settings in the shopping app.

**Daily limits.** Today's use of the site limit, and the three limits `protections.py` counts: the whole site, each
account and each internet connection guests use (0 to 10,000; 0 stops new checks). A change counts at once and is kept
in `site_settings` in `accounts.db`, so it outlives a restart; until one is saved, the numbers come from the
environment (`DEFAKETIVE_*_DAILY_SCANS`). The 3 free checks per guest browser are the original app's and stay fixed.

**The admin account** is made by the server when it starts (`admin_api.ensure_admin`): `Admin@defake.com` with the
password `Admin@defake.com`, kept in `agency_members` (the old view's table). A password the admin changed is kept across restarts. The password is in the source, so **change it in
"Change password" before the site is opened to the public.** **Privacy:** the privacy notice says DTI admins can
see account names and emails; the adviser should confirm that wording.

## Wording rules (kept from the original)

- The server words every result and label. This app never writes its own result.
- A result says what reviewers **report**. It never says a product is safe or unsafe, and there is no score.
- **Three words, one meaning each.** You **check** a product (every button, menu item and page title says "Check").
  A **scan** is the work a check starts when the product is new: it collects fresh reviews, it is what runs, and it is
  what is counted ("3 free scans"). What you get is a **report**. The app does not say "analyze" for what a person
  does. (The original app's own progress messages and its "Not analyzed yet" headline still do; they are shown as sent.)
- **A running scan says how long it usually takes**, on the guest screen and on Check a product when the scan is of
  one link: "1 to 2 minutes" for Lazada (the only marketplace scanned since 14 Oct 2026). The figures are in `typicalScanTime`
  in `src/lib/product.ts`. Lazada is read in the background from its review feed and was timed on 12 Oct 2026 (63
  seconds for a listing with 145 reviews, 134 for one with 298). Shopee and Temu have not been timed: theirs is the
  earlier figure from one Lazada listing read off the page (195 seconds).
- **A scan that needs the person says so.** Lazada scans open no window. When Lazada asks for a login or a check,
  the original app's scraper puts a Chrome window on screen and the job's `needs_you` flag turns on; the running
  panel, the Home card and a notice then say "This scan needs you" with the server's instructions, and go back to
  normal when the scan moves on. Checked in `tests/e2e/scan-flow.mjs`, in light and in dark.
- **Four groups, one name each**, used everywhere a group is named: chips on cards, filters, numbers, charts and the
  legend. The names live in one place, `GROUP_NAMES` in `src/lib/product.ts`. The sentence under a chip (the result
  headline, such as "No warning signs found") is the server's and says why.
- Colour is never the only signal: every result chip also has an icon (a different shape for each group) and a word.
- **One brand colour, purple, and it never means a result.** It is on the logo dot, the main buttons, links, switches,
  the scan progress and the focus ring, and nowhere else. Anything that counts reviews (the bars on a report) or shows
  a result keeps its own colour. It is defined once, as `--brand` in `src/routes/layout.css` (a lighter purple in
  dark mode), and `--primary` points at it. Purple was chosen by test, not by taste: `npm run check:colors` checks
  that it reads 4.5:1 or better as a button and as a link on every background, and that it stays clearly apart from
  each of the four result colours, also for colour blindness. Bright blue failed that test (too close to teal).
- Everything else is plain black and white on purpose, so colour always means something. Four result colours, used the
  same way in chips, banners, charts and dots:

  | Group | Colour | Icon | When |
  | --- | --- | --- | --- |
  | Safety reports | red | triangle with !  | The checker's serious level only: serious or repeated reports of fire, smoke, shocks or overheating |
  | Caution | orange | circle with !  | Fakes or defects reported more than usual, a milder safety result, **or any other safety mention, even one** |
  | No warnings | teal | tick in a circle | Enough reviews, no safety mention, nothing else at a warning level |
  | No result yet | grey | circle with ? | Too few reviews, reviews that may not be trustworthy, or not analyzed yet |

  The colour follows the level the checker decided (`chipFor` in `src/lib/product.ts`). Red is never used for a single
  or mild safety mention: that product is orange, its "Safety problem · 1" count is orange, and the report says in one
  line why it is shown as Caution. A safety mention is never hidden either: it always lifts a product out of
  "No warnings" and "No result yet". The words the check matched are highlighted in amber, not red. (The original app
  still shows any safety mention in red; the two versions differ here on purpose.)

  "No warnings" is teal, not bright green, so it never reads as an approval stamp. Words on a coloured tint are always
  the normal text colour (17:1), so nothing is brown or hard to read; the colour sits in the icon, the border, the tint
  and the charts. The colours are defined once, in `src/routes/layout.css` (`--destructive`, `--warning`, `--success`,
  `--unknown` and their `-soft` tints, plus the `.tone-*` classes). To change one, edit the token and run
  `npm run check:colors`: it tests contrast (3:1 or better for the strong colour, 7:1 for text on a tint) and that the
  four stay clearly apart for protan, deutan and tritan colour blindness.

## The report

One component draws it for the app and for the guest screen (`src/lib/components/report/report-view.svelte`).

The order is: which product, the answer, what to do about it, then the proof.

1. **Which product:** a small photo, the name, its stars, marketplace and price. Kept short on purpose, so that the
   result is on the first screen of a phone even under a long name.
2. **The result**, biggest thing on the page: the label, a headline, and one short line about the most serious thing
   reviewers reported (the server words it; every kind of problem has its own card on the first tab). If a product is
   orange only because one review mentions a safety concern, a one-line note right under the result says so.
3. **One next step** under it, chosen by the result: for Caution and Safety reports, see similar products with no
   warnings first (when there are any, as the main button), then read the flagged reviews; read the flagged, negative or all reviews for
   No warnings; read the flagged reviews, or the reviews we have, for No result yet. "What do these labels mean?"
   jumps to the legend.
4. **The numbers behind it**, in the same card but below the result: positive and negative reviews, category, report
   date and the sentence about how many reviews were read. On the guest screen, the note about what an account adds
   comes after this card, never above the result.
5. **First tab:** the sentiment chart and, beside it, the short legend of the four groups (with one line on how
   accurate the check was in testing), then the reviewers' own words ("What reviewers reported", one block per kind of
   problem). The kinds of problem are in two groups,
   most serious first: "Can change the result" (Safety problem, Faulty or broken, Possible fake), then "Doesn't
   change the result" (Poor quality, Not as advertised). The order lives in `CATEGORY_ORDER` in `src/lib/product.ts`.
6. The tabs are **Summary**, **Reviews** (every review, with filters) and **Similar products** (the count shows only
   when there are some). The list of reviews uses the same order, so a safety report is at the top and not under
   seventy other reviews; the line above the list then says "most serious first".

Small wording rules on a report: sentiment is "Positive", "Negative" or "Mixed or unclear"; the labels that are
counted but do not affect the result sit under one heading, "Doesn't change the result"; the button that leaves for the listing names where
it goes ("View on Lazada"); the line about the sample is a sentence ("We read 15 of this listing's 4,048 reviews.");
and when extra low-star reviews were read on purpose, the percentages are called "adjusted", with one sentence saying
why. The report date comes from when the report was last saved (`server.py` passes it along).

## When something fails

A failed load never looks like an empty list.

- **The server cannot be reached:** a grey banner at the top of every page says so and offers **Try again**
  (`components/app/offline-banner.svelte`). Nobody is sent to the sign-in pop-up because of it: not knowing who is
  here is not the same as being a guest (`auth.unreachable`).
- **Your history or wishlist did not load:** Home, History and Wishlist say "couldn't be loaded" with **Try again**
  (`library.error`).
- **The product list did not load:** Products says so, with **Try again** (`catalog.error`).
- **A report did not load:** "This report couldn't be loaded" with **Try again**. A report that simply does not exist
  says "We don't have a report for this product yet" and offers **Check this product**, with the link carried over.

`src/lib/boot.ts` is the start-up load. The first page load runs it once, and "Try again" runs it again.

## Touch screens

On a touch screen (`@media (pointer: coarse)`, at the end of `src/routes/layout.css`) every control is at least 40px
wide and tall: buttons, tabs, filter chips, select boxes, inputs, menu rows, and a larger invisible area around
checkboxes and switches. A mouse keeps the compact shadcn sizes. No shadcn component file is edited
for this; the rules go by each component's `data-slot`. Give a plain link or button of your own the class `tap` to
include it. The one exception is a link inside a sentence.

## Re-checking products saved by an older checker

A saved report is shown as it was stored: it does not change when the checker does. Two kinds fall behind. A report
in a format the app no longer reads shows "Not analyzed yet". A report in today's format made by an earlier version
of the checker is still shown, with one grey line under the result ("This report was made with an earlier version of
the checker", `behindChecker` in `src/lib/product.ts`; `server.py` adds `checked_with_current` to what it sends), and
`start.cmd` says so when it starts. Run the re-check after any change to the checker.

`scripts/recheck_products.py` re-reads the reviews already stored for both kinds and saves a result from the current
checker. It asks the original app what "current" means (`analysis_is_current`), uses the original app's own
functions, edits none of its code, and contacts no marketplace. Close both apps first, then run it with the
original's Python from this folder:

```
..\Capstone-Version-Control-Version-1.1\.venv\Scripts\python.exe scripts\recheck_products.py
..\Capstone-Version-Control-Version-1.1\.venv\Scripts\python.exe scripts\recheck_products.py --apply
```

- Without `--apply` it is a **dry run**: it lists what it would re-check and writes nothing.
- With `--apply` it first copies `defaketive.db` into `backups/` here and checks the copy, then analyses and saves.
  If the review model cannot load, it stops before writing anything.
- Products with no stored reviews are left as they are: there is nothing to re-read.
- **To undo:** close both apps and copy the backup file (its full path is printed at the end) back over
  `defaketive.db` in the original folder.

`scripts/remove_error_pages.py` works the same way (dry run by default, `--apply` backs up first). It removes saved
rows that are really a browser error page, such as "This site can't be reached", which a failed scrape once saved as
if it were a product. It only touches rows with that title and no reviews.

`scripts/rescan_products.py` is for when the reader changed, not the checker. It scans the saved **Lazada** products
again with the original app's own steps (no Chrome window, about a minute or two each) and replaces each report, where
a re-check could only re-read the old reader's text. Same habits: dry run by default, `--apply` backs up first and
refuses while the app is running. A report is replaced only if the fresh scan read Lazada's review feed and finished
every star level; otherwise the old report stays and the reason is printed. It never waits for or answers a login or
verification, and two failures in a row stop it. The scan files go to `backups/rescan-<date>/`. When a report is
replaced, that product's old review rows are removed too, so the database's review count stays the number of reviews
the reports hold. Temu and Shopee products are not scanned. `--database <copy>` and `--limit 1` try it on a copy.

`scripts/scan_more_products.py` and `scripts/add_scanned_products.py` give "Similar products" more to choose from. A
report can only be offered products the app has a report for, and only those with no warning signs and not one
safety mention, so a small pool means most reports show nothing.

- `scan_more_products.py` collects. `--known` takes the listings in the original app's own lists that are neither
  saved nor scanned; `--search "wireless earbuds" "power bank"` takes the first listings Lazada returns for each
  search. A listing with fewer than 100 ratings is looked at once and passed over. It scans as the app does (no
  Chrome window, the review feed, 60 reviews per star level) into `backups/pool-scans/`, never waits for or answers
  a login or verification, and stops everything if a run reads nothing from the feed. Without `--scan` it only
  lists what it would do and contacts nobody.
- `add_scanned_products.py` adds what was scanned but never saved: those pool scans, and the listings the original
  app scanned to measure what is typical (its `research/data/reference_scans/feed/`). Each one not already saved
  (same Lazada item) is read by the app's own checker and saved the way the app saves a scan. No marketplace is
  contacted, a product already saved is left as it is, and nobody's History changes.

The pool has a running cost: every saved report has to be re-checked after a change to the checker
(`recheck_products.py`), at about a fifth of a second a review. Same habits: dry run by default, `--apply` backs up first and refuses
while the app is running, `--database <copy>` and `--limit 2` for a trial. Reading the reviews takes about half an
hour, so `--prepare` does that part ahead with the app still open (it writes nothing to the database, and keeps its
results in `backups/add-products-prepared/`); `--apply` then only has to save them.

## Where this differs from stock shadcn-svelte

Only to keep text readable (WCAG AA, checked with axe on every page, in light and dark, plus the pop-ups):

- `--muted-foreground` is `oklch(0.5 0 0)` instead of `0.556` (4.3:1 on `muted` was just under AA).
- Red text on a pale red tint read 4.0:1, so `--destructive-ink` and `--destructive-soft` are used for the
  destructive Button, Badge and Alert and for the safety chips.
- `--warning`, `--success`, `--unknown` (and their `-soft` tints) are new, for the result colours above, and `--destructive` is a little darker than stock so red text on white passes with room to spare.

And one change for looks: `--brand` (purple) is new, and `--primary`, `--sidebar-primary` and `--ring` use it instead of
stock black and grey. The two Progress bars that count reviews are given `bg-foreground`, so they stay plain.

The dark theme, radius, Inter font and every other token are the shadcn-svelte defaults.

## Charts and motion

- Charts use shadcn-svelte's chart component (layerchart): the sentiment donut on a report, the result-group donut
  on Home, and products checked per day on History (from the day the account was created: at least 14 slots, so a new account
  gets thin bars that fill in day by day, and at most the last 30 days). Each has a text version for screen readers. (Home used to compare
  marketplaces too. That chart is gone: a handful of checked products cannot support such a comparison.)
- Loading shows skeletons shaped like the real thing (cards, rows, number tiles, a whole report).
- Empty screens share one look (`empty-state.svelte` with a small line drawing from `empty-art.svelte`).
- Motion (all in `src/routes/layout.css`, all switched off for people who ask their device for less motion):
  cards rise in one after another (`.reveal`), numbers count up (`count-up.svelte`), page changes cross-fade
  (View Transitions, set up in `src/routes/+layout.svelte`), the live scan shows a stepper and a bar with a light sweep
  (`scan-progress.svelte`), and a report's result settles in step by step (`verdict-block.svelte`).

## Shortcuts, previews and phone touches

- **Ctrl+K** (Cmd+K on a Mac) opens a search pop-up from anywhere: jump to a page, open a product you checked, switch theme, sign in or out.
- **/** jumps to the link box (and opens "Check a product" first if the page has none).
- Resting the mouse on a product shows a short preview (result, counts, strongest quote). It is only an extra: the link works without it.
- Home rows are carousels with arrows (drag or swipe also works).
- On phones, filters on Products and on a report's Reviews tab open from the bottom.
- Saving or unsaving a product shows an **Undo** toast.
- Photos fade in over a soft colour wash, fall back to a calm "No photo" tile, and a report photo opens larger.

## How it is built

```
src/lib/api.ts                  fetch wrapper that keeps the server's own error messages
src/lib/boot.ts                 the start-up load; "Try again" buttons run it again
src/lib/product.ts              pure helpers: chips, filters, sentiment, highlighted quotes
src/lib/stores/*.svelte.ts      auth, saved history + wishlist, catalog, live scan, preferences, pop-ups
src/lib/components/ui/          shadcn-svelte components (added with the CLI, yours to edit)
src/lib/components/app/         DeFaketive pieces: sidebar, product card, scan form, sign-in pop-up
src/lib/components/report/      the parts of a product report
src/routes/                     pages
```

Add more shadcn components with `npx shadcn-svelte@latest add <name>`.

> **Careful with `--overwrite`:** it replaces the shadcn files you edited. DeFaketive edits to re-check afterwards: `ui/button`, `ui/badge`, `ui/alert` (the destructive look) and `ui/hover-card/hover-card-trigger.svelte` (keeps the link a link).

> SvelteKit 3 keeps its TypeScript settings out of `tsconfig.json`, and the shadcn-svelte CLI cannot read
> them. If `add` fails with `File '$app/tsconfig' not found`, temporarily replace `tsconfig.json` with
> `{ "compilerOptions": { "strict": true, "paths": { "#lib": ["./src/lib/index.js"], "#lib/*": ["./src/lib/*"] } }, "include": ["src", "vite.config.ts"] }`,
> run the command, then put the original back. Imports use the `#lib/…` alias **with** a file extension
> (`#lib/product.js`, `#lib/stores/auth.svelte.js`).

## Checks

```
npm run check         types and Svelte checks
npm run check:colors  result colours and the brand colour: contrast and colour-blind safety
npm run build         static build into build/ (start.cmd serves it)
npm run test:e2e      the end-to-end tests, see below
```

`saved_pool.py` has tests of its own, run with the original app's Python. They work on a database in a temporary
folder, never the real one:

```
..\Capstone-Version-Control-Version-1.1\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

## Tests

`tests/e2e/` holds 22 test files, over 500 checks (two of them for the browser extension, see `extension/README.md`). They drive the Chrome that is already installed and walk the
app the way a person would: signing up and in, a pretend live scan, the guest screen, the lock on the app, every
result group and its colour, the brand colour, the wording, error screens, tap targets on a phone, the report, the
admin app (`admin.mjs` signs in as `Admin@defake.com` on the scratch accounts database and uses the `/admin` page), and accessibility (axe, WCAG 2.1 AA, light and dark).

```
npm run test:e2e                     every file, against a fresh build
npm run test:e2e -- wording errors   only those files
npm run test:e2e -- --dev            against the developer server instead of the build
```

Close the app first: the command starts its own servers and refuses to run if ports 5000 or 5173 are busy, so
it can never stop an app you are using. It prints passed and failed for each file, then stops its servers. Logs and
the scratch accounts database are in `tests/.tmp/`, screenshots in `tests/e2e/shots/` (neither is kept in git).

What the tests touch:

- **Accounts:** they create test accounts in a scratch database (`tests/.tmp/accounts-test.db`), never in the
  real `instance/accounts.db`.
- **Products:** they read the saved products in the original's `defaketive.db` and add or remove none. Several
  checks use products that are saved there by name ("Type C Fast Charging…", "DoubleShock…", "U19 Macaron…"); if
  those are ever removed, those checks need another product.
- **Marketplaces:** none is contacted. Live scans are pretended inside the test browser.

The server's own tests (`tests/test_*.py`: the saved-products pool, `protections.py`, `serve.py`, the backups, the
extension route and the admin API)
run with the original app's Python, from this folder:

```
..\Capstone-Version-Control-Version-1.1\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

They use a temporary accounts database and never start a real scan.

## Version control

This folder is its own git repository, local only: nothing is uploaded anywhere unless you add a remote and push.
`backups/` (copies of the real database) is deliberately left out of it.
