# Hours of Work

Shows how many hours of work it takes to buy one unit of everyday goods and services at the 10th, 25th, 50th, 75th and 90th percentile
U.S. wage. Two menus (good, income level), charts of labor hours and price, and a table listing every data source with its limits.

**To set it up, follow SETUP.md.**

```
scripts/build_data.py   downloads data, computes hours -> site/data.json (Python standard library only)
site/                   the website (index.html, data.json, _headers)
data/manual/            hand-maintained CSV (new vehicle prices)
deploy-workflow/        the daily scheduler (copy into .github/workflows/ on GitHub; see SETUP.md)
wrangler.jsonc          tells Cloudflare to publish ./site
tests/                  offline tests using synthetic data
scripts/fake_fred.py    synthetic data for previews/tests only
```

## How the numbers work
- Hours = price of one unit / hourly wage (nominal dollars both sides, so inflation cancels).
- Wages: BLS CPS usual weekly earnings, full-time wage and salary workers, via FRED, / 40 hours.
- Each month uses its quarter's wage; months after the newest published quarter use the latest available one (flagged in tooltips).
- Items are "Measured" (straight from a source), "Estimate" (a price index scaled to one published dollar figure: child care, college tuition),
  or "Hand-entered" (new vehicles). Each item's notice on the page says which and lists its caveats.

## Adding an item
Add a row to `FRED_ITEMS` in `scripts/build_data.py` (FRED series ID, name, unit, category, a word that must appear in the series title, caveats).

## Preview locally
```
python3 scripts/make_sample.py          # synthetic data, flagged "sample"
cd site && python3 -m http.server 8000  # open http://localhost:8000
python3 tests/test_build.py
```
