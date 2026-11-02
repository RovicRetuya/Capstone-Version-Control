# DeFaketive browser extension

Adds a **Check with DeFaketive** button to Lazada PH and Shopee PH product pages (shopper guide: `GUIDE.md`). Pressing it reads the product's reviews in the
shopper's own browser and opens the DeFaketive report (in the DeFaketive tab already open, or a new one). Chrome and Edge on a computer; phone browsers
have no extensions.

## For testers: install it (2 minutes)

1. Get the folder: the team sends `dist-extension.zip` (unzip it), or use `dist-extension/` from this repo after
   `node scripts/build-extension.mjs --site <the site's address>`.
2. Open `chrome://extensions` (Edge: `edge://extensions`) and switch on **Developer mode** (top right).
3. Press **Load unpacked** and choose the unzipped folder (the one with `manifest.json` in it).
4. Open any Lazada PH product, press **Check with DeFaketive** at the bottom left, and sign in on the tab that
   opens (a free account).

If Lazada shows a "slide to verify" or similar check, that is Lazada asking the shopper; do it as you normally
would, then press the button again.

## How it works

| File | Runs | Does |
| --- | --- | --- |
| `collect.js` | inside the Lazada product page | Reads the review list exactly as DeFaketive's scanner does (`backend/lazada-scraper/src/lazada_scraper.py`, feed mode): star counts first, then up to 60 written reviews per star level in the order 3, 2, 4, 1, 5, 50 per request, one request a second, at most 300 entries deep. Never reads reviewers' names or sellers' replies. Stops if Lazada answers with a check; nothing is done to get past one. |
| `lazada-page.js` | inside the product page | Runs `collect.js` with the page's own `fetch`, as the scanner's requests were made. |
| `lazada.js` | beside the page (isolated) | The button and progress panel; reads the product's name, price, seller and photo with the scanner's selectors; hands everything to `background.js`. |
| `shopee-collect.js` | inside the Shopee product page | The same collection for Shopee PH, from the review list Shopee's own product page loads (`/api/v4/item/get_ratings`): star counts, then every written review of each star level in the order 3, 2, 4, 1, 5, 59 per request, one request a second, until the list runs out. Never reads reviewers' names, ids or photos, or sellers' replies. Stops if Shopee answers with a check or verification; nothing is done to get past one. |
| `shopee-page.js`, `shopee.js` | inside / beside the Shopee page | As `lazada-page.js` and `lazada.js`. Shopee changes page without reloading, so the button follows the address. |
| `background.js` | the extension's service worker | Keeps the collected reviews for up to an hour under a random id and opens `<site>/check-from-extension?handoff=<id>`, reusing the DeFaketive tab used last if one is open. Only a Lazada or Shopee product page may hand reviews over; only the DeFaketive site may take them. |
| `site.js` | on the DeFaketive site | Passes the reviews to the page that asks for them (`window.postMessage`, same origin only). |
| `config.js` | everywhere | The site's address. |

The page `/check-from-extension` asks a guest to sign in, then sends the reviews to `POST /api/extension/check`.
The server (`extension_api.py`) checks every field and that the numbers add up before anything is analysed, counts
the check against the daily limits, and analyses it like a scan; the report is the report a scan would make.

Permissions: `storage` (to hold the reviews for a moment) and the DeFaketive site itself (to find its open tab and
reuse it). No access to other sites, no browsing history.

## Building it for a site

```
node scripts/build-extension.mjs --site https://<public address>
```

writes `dist-extension/` and `dist-extension.zip` (both git-ignored). `extension/` itself is for
`http://localhost:5173` (start.cmd). A public site must use https.

Add `--download` to also copy the .zip to `static/downloads/defaketive-extension.zip` (git-ignored). After the next
build of the app, the site's **Get the extension** page (`/extension`, and `/app/extension` when signed in) shows a
download button for it; without that file the page asks visitors to contact the team for it.

## Chrome Web Store

One-time developer fee (US$5), then upload `dist-extension.zip`. Google reviews every extension and can say no; the
usual reasons, and how this one is set up for them:

- Ask for little: `storage` plus the DeFaketive site only; scripts only on Lazada PH product pages and the DeFaketive
  site.
- Say what it does with data: fill in the store's privacy form (it sends review text, ratings and the product's
  details to the DeFaketive site; nothing personal of the shopper) and link the site's Privacy Policy.
- Don't look like Lazada: the name is DeFaketive, the icon is DeFaketive's, the description says "not affiliated
  with Lazada".
- No code from the internet: everything is in the package.

A refusal says why; fix it and send it again. Testers can always use **Load unpacked** meanwhile.

## Tests

- `npm run test:extension` — `collect.js` against a pretend review list (`tests/extension/`).
- `npm run test:e2e -- extension extension-browser` — the site's hand-off page, and the real extension loaded into
  a throwaway headless Chrome with a pretend Lazada page and review list. No marketplace is contacted.
- `tests/test_extension_api.py` — the server's checks, including on what `collect.js` really produces.
