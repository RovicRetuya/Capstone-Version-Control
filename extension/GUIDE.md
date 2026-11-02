# Checking Shopee PH products with DeFaketive

A step-by-step guide for shoppers. The same extension also checks Lazada PH.

Shopee products are checked with the DeFaketive browser extension. Pasting a Shopee link into the website does not
work, because the reviews have to be read in your own browser, where you are signed in to Shopee.

## What you need

- A computer with **Google Chrome** or **Microsoft Edge**. Phone browsers cannot add extensions.
- The extension file `defaketive-extension.zip`. Download it from the **Get the extension** page on the DeFaketive
  site, or ask the team for it.
- A free DeFaketive account. You are asked to sign in the first time you check a product.

## Install it (about 2 minutes)

1. **Unzip** `defaketive-extension.zip`. You get a folder with a file called `manifest.json` inside.
2. Open the extensions page. Type this into the address bar:
   - Chrome: `chrome://extensions`
   - Edge: `edge://extensions`
3. Switch on **Developer mode** (the switch at the top right).
4. Press **Load unpacked** and choose the unzipped folder (the one that has `manifest.json` in it).
5. DeFaketive now appears in your list of extensions. Do not delete or move the folder afterwards, or the extension
   stops working.

Tip: pin it. Click the puzzle-piece icon in the toolbar, then the pin next to DeFaketive.

## Check a Shopee product

1. Open any Shopee PH product page (`shopee.ph`). Log in to Shopee if it asks.
2. Press **Check with DeFaketive**, the button at the bottom left of the page.
3. **Keep the Shopee tab open** while it works. The panel shows its progress. It reads up to 60 written reviews from
   each star level, one request a second, so a product with many reviews takes a minute or two.
4. When it finishes, your report opens in DeFaketive. Sign in or create a free account if it asks. The report shows
   what reviewers say in their own words about fakes, defects and safety problems.

Shopee changes pages without reloading. If you move to another product, the button follows you. Press it again for
the new product.

## If something goes wrong

| What you see | What to do |
| --- | --- |
| No **Check with DeFaketive** button | Make sure you are on a product page (not search results or the home page). Reload the page. Check that the extension is switched on at `chrome://extensions`. |
| Shopee shows a login, "slide to verify" or other check | That is Shopee asking you. Complete it as you normally would, then press the button again. The extension never tries to get past a check. |
| "Not enough reviews" or an empty result | Some products have few or no written reviews. There is nothing to check. |
| The panel stops partway | Do not close the tab. Reload the page and press the button again. |
| You reach your daily limit | Each check counts against a daily limit. Try again tomorrow, or ask the team. |
| The extension disappears or turns off | You may have moved or deleted the folder. Put it back, or load it again with **Load unpacked**. |

## What the extension reads, and what it does not

**It reads:** the product's name, price, seller and photo; how many ratings it has at each star level; and up to 60
written reviews from each star level.

**It never reads:** reviewers' names, ids or photos; sellers' replies; your Shopee login, cart or orders; any other
website; or your browsing history.

It asks the browser for only two permissions: `storage`, to hold the reviews for a moment on their way to the site,
and access to the DeFaketive site itself.

## Remove it

Open `chrome://extensions` (or `edge://extensions`), find DeFaketive and press **Remove**.

DeFaketive is a student research project. It is not part of, or endorsed by, Shopee or Lazada.
