# DeFaketive Sentiment Analysis

This is the standalone sentiment-analysis component for DeFaketive. It reads
review data produced by either the Shopee Philippines scraper or the Lazada
Philippines scraper; neither scraper needs to contain or import this model.

The model extends NLTK VADER with editable Filipino and Taglish lexicons. It
returns positive/neutral/negative sentiment, matched evidence, product-risk
categories, and duplicate-review markers. Analysis runs locally.

## Setup on Windows PowerShell

```powershell
cd E:\school\SCRAPPERS\shopee-scraper\sentiment-analysis
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m nltk.downloader vader_lexicon
```

## Analyze one review

```powershell
python -m defaketive_sentiment --text "Maganda pero mabilis masira"
```

## Analyze Shopee results

```powershell
python -m defaketive_sentiment ..\shopee_ph_laptop_stand.json
```

## Analyze Lazada results

```powershell
python -m defaketive_sentiment ..\..\lazada-scraper\lazada_ph_smoke_test.json
```

Unless `--output` is supplied, the analyzer writes a sibling file ending in
`_analyzed.json` or `_analyzed.csv` and preserves the original scrape.

For model fields, scoring, and research limitations, see
[`docs/model.md`](docs/model.md).

The original scraper's unrelated Vietnamese labeling script is preserved under
`legacy/` for reference, but it is not imported or installed by this project.

## Run tests

```powershell
python -m unittest -v
```
