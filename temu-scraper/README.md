# Temu Philippines Product and Review Scraper

This visible-browser scraper collects public Temu product metadata and written
reviews into the same JSON schema used by the Shopee and Lazada projects. Its
output can be analyzed directly by the standalone DeFaketive sentiment model.

Temu is JavaScript-heavy and changes generated class names frequently. The
scraper prefers canonical product IDs, JSON-LD, accessible labels, and semantic
attributes. If real products or reviews cannot be identified, it saves HTML and
a screenshot under `debug/` instead of creating sample data.

Temu may require an account before it displays search results or product pages.
When this happens, complete the sign-in manually in the opened Chrome window
and press Enter in PowerShell. A login page is never saved as a product.

## Responsible use

The scraper does not solve CAPTCHAs, automate logins, or bypass verification.
Complete any challenge manually, use conservative limits, and follow Temu's
terms and applicable privacy and research requirements.

## Installation

```powershell
cd E:\school\SCRAPPERS\shopee-scraper\temu-scraper
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Close other Chrome windows before the first run if Chrome reports a profile or
driver lock.

## Keyword search

Scrape up to five products and 100 written reviews per product:

```powershell
python -m src.temu_scraper "laptop stand" --num 5 --pages 2 --review-limit 100
```

Only keep products with at least 4.0 stars and 100 displayed reviews:

```powershell
python -m src.temu_scraper "electronic gadgets" --num 20 --pages 3 `
  --min-rating 4.0 --min-reviews 100 --review-limit 100
```

`--pages` controls groups of infinite-scroll loads because Temu does not always
expose conventional numbered search pages.

## Direct product URL

Both Temu URL forms are accepted and normalized to a canonical `goods_id` URL:

```powershell
python -m src.temu_scraper `
  --product-url "https://www.temu.com/product-name-g-601099588578152.html" `
  --review-limit 100 `
  --output temu_ph_product.json
```

`--product-url` can be repeated for several known products.

## Collect every review exposed by Temu

```powershell
python -m src.temu_scraper `
  --product-url "PASTE_TEMU_PRODUCT_URL" `
  --all-reviews --max-review-batches 200
```

This continues until no new unique reviews are exposed or the safety cap is
reached. Temu may display a larger total than it makes available in the current
browser session. In that case, the product receives `review_collection_warning`
instead of the scraper claiming that the collection is complete.

The scraper attempts Temu's visible rating filters from 1-star through 5-star,
so low-rated feedback is collected first. If the rendered Temu layout does not
expose identifiable star controls, it falls back to the normal review feed and
sorts the saved comments from the lowest extracted rating to the highest.

Review progress is saved atomically every five loaded batches. Run the same
command and output path after an interruption to resume with saved comments;
duplicates are ignored while the scraper advances to new reviews. Transitions
use three attempts and a 15-second timeout by default. Use
`--checkpoint-every`, `--pagination-retries`, and `--pagination-timeout` to tune
these settings. Abnormal failures save HTML and a screenshot in `debug/`.

## Output

Results are saved incrementally to `temu_ph_<keyword>.json`. Important fields
include:

```json
{
  "platform": "temu",
  "market": "PH",
  "currency": "PHP",
  "rating": 4.7,
  "total_rating": 1200,
  "comments": [
    {
      "rating": 2,
      "content": "Sira agad after two days"
    }
  ]
}
```

Products with no written feedback are saved with `comments: []`,
`review_status: "no_reviews"`, and checkpoint stop reason `no_reviews`. A
missing review widget on a product that reports existing reviews is recorded
separately as `review_widget_missing` so layout/login failures are not mistaken
for genuinely empty products.

Analyze the output with:

```powershell
cd ..\sentiment-analysis
.\.venv\Scripts\Activate.ps1
python -m defaketive_sentiment ..\temu-scraper\temu_ph_laptop_stand.json
```

## Tests

```powershell
python -m unittest -v
```

Unit tests cover Temu URL canonicalization, PH search URLs, numeric parsing,
JSON-LD normalization, review normalization, filters, and compatible output.
Live extraction remains a manual integration test because Temu can require
verification and its rendered layout changes frequently.

## Attribution and license

The browser lifecycle, cookie persistence, incremental-save pattern, and
output conventions follow the MIT-licensed Shopee/Lazada projects in this
repository. Temu-specific URL handling, extraction, filters, diagnostics, and
review collection are newly implemented. See [LICENSE](LICENSE).
