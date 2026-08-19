
# Shopee Philippines Scraper

This Python application scrapes public product data from [Shopee Philippines](https://shopee.ph). It retrieves product names, canonical links, PHP prices, ratings, images, shipping labels, seller locations, descriptions, and public reviews.

The scraper is configured specifically for `shopee.ph`. It supports current and legacy Shopee product-card layouts and English Philippines review filters such as `5 Star`, `With Comments`, and `With Media`.

## Installation Steps

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/dtungpka/shopee-scraper.git
   cd shopee-scraper
   ```

2. **Create a Virtual Environment (Optional But Recommended):**
   - Linux/Mac:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   - Windows PowerShell:
     ```bash
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Before running:
- Make sure all Chrome windows are fully closed.
- Prepare to log in and solve captchas manually if prompted.

### Basic Command

```powershell
python src/retriv.py -k "your_search_term" -n 10 -r 30
```

When you see the search page loaded in the browser:
1. Log in to Shopee Philippines (if needed).
2. Solve any captcha presented.
3. After continuing to the main search page, press Enter in the terminal to proceed.
4. Keep an eye on the browser; if another captcha appears at any point, solve it to continue scraping.

### Scraping Modes

1. **Review Limit Mode:**
   - Use `-r` or `--review-limit` to collect reviews from 5-stars downwards until the limit is met:
     ```bash
     python src/retriv.py -k "laptop" -n 5 -r 10
     ```
   This collects up to 10 reviews per product, starting from the top ratings and moving downward.

2. **All-Star Types Mode:**
   - Combine `--all-star-types` with `--star-limit-per-type` to specify how many reviews to retrieve for each star rating:
     ```bash
     python src/retriv.py -k "laptop" -n 5 --all-star-types --star-limit-per-type 5
     ```
   This collects 5 reviews for 5-star, 4-star, 3-star, etc., in separate queries.

### Command-Line Arguments

- `-k`, `--keyword`: Search term (default: "Raspberry pi")
- `-n`, `--num`: Number of products to retrieve (default: 10)
- `-r`, `--review-limit`: Total reviews to collect per product (default: 30)
- `--index-only`: If set, only retrieve index data without details
- `--all-star-types`: Collect each star rating separately
- `--star-limit-per-type`: Reviews per star type (default: 10)
- `--chrome-user-data-dir`: Path to your Chrome profile directory
- `--site`: Shopee market; `shopee.ph` (or shorthand `ph`) is supported

Results are saved incrementally to `shopee_ph_<search_term>.json`, so completed products are retained if the browser is interrupted. Authentication cookies are stored separately in `cookies_shopee_ph.dat`.

## Sentiment analysis

Sentiment analysis is maintained as the independent
[`sentiment-analysis`](sentiment-analysis) subproject. After scraping, run its
CLI against this scraper's JSON output. This keeps data collection and review
analysis independent.

## DeFaketive dashboard

The responsive Streamlit dashboard adds shopper search/results/product-risk
views plus administrator overview, scraper, lexicon, database, and model
evaluation screens. It can analyze the most recent scraper JSON automatically,
accept an uploaded scraper JSON, or launch a live Shopee PH scrape.

```powershell
pip install -r requirements.txt
python -m nltk.downloader vader_lexicon
streamlit run app.py
```

Live analysis shows the three processing stages (scraping, sentiment analysis,
and risk computation). Shopee may still open Chrome for login or captcha
verification. The dashboard uses the current research formula and clearly marks
unavailable evaluation metrics rather than displaying fabricated values.

## Example Command

```bash
python src/retriv.py -k "laptop" -n 5 --all-star-types --star-limit-per-type 3
```

Use the scraper responsibly, keep request volumes low, and follow Shopee's applicable terms and local law. Shopee may require a login or manual verification; the script pauses so you can complete it in the opened Chrome window.

## License
This project is licensed under the MIT License. See the LICENSE file for details.
