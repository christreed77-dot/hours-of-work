#!/usr/bin/env python3
"""Build site/data.json: prices of goods/services and the labor hours needed to buy one unit at five wage
levels (10th, 25th, 50th, 75th, 90th percentile).

Sources: FRED (BLS, Census), Zillow's public rent index CSV, and a small hand-maintained CSV (data/manual).
One free key is needed:  https://fredaccount.stlouisfed.org/apikeys  ->  export FRED_API_KEY=...
Standard library only.
"""
import argparse, bisect, csv, datetime as dt, io, json, os, re, statistics, sys, time
import urllib.parse, urllib.request

HOURS_PER_WEEK = 40          # weekly earnings -> hourly wage
START = "2000-01-01"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FRED_URL = "https://fred.stlouisfed.org/series/"

INCOMES = [
    {"id": "p10", "label": "10th percentile", "pct": 10},
    {"id": "p25", "label": "25th percentile", "pct": 25},
    {"id": "p50", "label": "Median (50th)",   "pct": 50},
    {"id": "p75", "label": "75th percentile", "pct": 75},
    {"id": "p90", "label": "90th percentile", "pct": 90},
]
# BLS Current Population Survey, usual weekly earnings, full-time wage & salary workers, 16+.
# IDs are hints: each is checked against the FRED title and looked up by search if it doesn't match.
WAGE_SERIES = {  # key: (title phrase, hint IDs)
    "p10": ("first decile",    ["LEU0252911200Q"]),
    "p25": ("first quartile",  ["LEU0252911300Q"]),
    "p50": ("second quartile", ["LEU0252881500Q", "LES1252881500Q"]),   # NSA preferred; the SA one is the fallback
    "p75": ("third quartile",  ["LEU0252911400Q"]),
    "p90": ("ninth decile",    ["LEU0252911500Q"]),
}

GROCERY_NOTE = "BLS says average prices are best used to compare one month's price level, not to measure price change over time. Prices are a U.S. city average."
# kind "fred": a FRED price series used directly.  `expect` must appear in the FRED title (guards against wrong IDs).
FRED_ITEMS = [
    ("eggs",    "APU0000708111", "Eggs (Grade A, large)", "dozen",  "Groceries", "eggs", [GROCERY_NOTE]),
    ("milk",    "APU0000709112", "Whole milk",            "gallon", "Groceries", "milk", [GROCERY_NOTE]),
    ("bread",   "APU0000702111", "White bread",           "pound",  "Groceries", "bread", [GROCERY_NOTE]),
    ("beef",    "APU0000703112", "Ground beef",           "pound",  "Groceries", "ground beef", [GROCERY_NOTE]),
    ("chicken", "APU0000706111", "Whole chicken",         "pound",  "Groceries", "chicken", [GROCERY_NOTE]),
    ("bananas", "APU0000711211", "Bananas",               "pound",  "Groceries", "bananas", [GROCERY_NOTE]),
    ("coffee",  "APU0000717311", "Ground coffee",         "pound",  "Groceries", "coffee", [GROCERY_NOTE]),
    ("gas",     "APU000074714",  "Gasoline (regular)",    "gallon", "Energy & utilities", "gasoline",
        ["Prices include federal, state and local taxes. U.S. city average."]),
    ("elec",    "APU000072610",  "Electricity",           "kWh",    "Energy & utilities", "electricity",
        ["Prices include fuel adjustments. U.S. city average. A typical household uses roughly 900 kWh a month, so one kWh is a tiny unit."]),
    ("natgas",  "APU000072620",  "Piped natural gas",     "therm",  "Energy & utilities", "utility (piped) gas",
        ["Prices include purchased-gas adjustments. U.S. city average."]),
    ("house",   "MSPUS",         "New house (median sale price)", "house", "Housing", "median sales price",
        ["Covers new houses sold only, not the typical existing home.",
         "Quarterly series, so the chart has four points a year.",
         "Hours shown are a lifetime-of-work scale, not a down payment: nobody pays this in wages alone."]),
]
CPI_CHILD = ("CUUR0000SEEB03", "day care")      # CPI: day care and preschool
CPI_COLLEGE = ("CUUR0000SEEB01", "college tuition")
CHILD_ANCHOR = {"year": 2022, "value": 10853,
                "source": "Child Care Aware of America, national annual average price of child care, 2022",
                "url": "https://www.childcareaware.org/?p=69645"}
COLLEGE_ANCHOR = {"date": "2025-09-01", "value": 11950,
                  "source": "College Board, Trends in College Pricing 2025: average published tuition and fees, public four-year, in-state, 2025-26",
                  "url": "https://research.collegeboard.org/trends/college-pricing"}
ZORI_URL = "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv"

API = "https://api.stlouisfed.org/fred/"


# ---------- network (tests replace these two) ----------
def fred_get(endpoint, **params):
    key = os.environ.get("FRED_API_KEY")
    if not key:
        sys.exit("FRED_API_KEY is not set. Get a free key at https://fredaccount.stlouisfed.org/apikeys")
    params.update(api_key=key, file_type="json")
    return json.loads(http_get(API + endpoint + "?" + urllib.parse.urlencode(params)))


def http_get(url):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "hours-of-work-site/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8")
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt * 2)


# ---------- FRED helpers ----------
def observations(series_id):
    data = fred_get("series/observations", series_id=series_id, observation_start=START)
    out = {}
    for o in data["observations"]:
        try:
            out[o["date"]] = float(o["value"])
        except ValueError:        # "." = not published (e.g. Oct 2025, when BLS could not collect data)
            continue
    return out


def meta(series_id):
    return fred_get("series", series_id=series_id)["seriess"][0]


def resolve_wage_series(phrase, hints):
    pat = re.compile(r"\(%s\): wage and salary workers: 16 years and over$" % re.escape(phrase), re.I)

    def ok(m, nsa):
        return (pat.search(m["title"]) and m["title"].lower().startswith("employed full time")
                and m.get("frequency_short") == "Q" and (m.get("seasonal_adjustment_short") == "NSA" or not nsa))

    cands = []
    for sid in hints:
        try:
            cands.append(meta(sid))
        except Exception:
            pass
    try:
        cands += fred_get("series/search", search_text="employed full time usual weekly nominal earnings %s 16 years and over" % phrase, limit=100)["seriess"]
    except Exception:
        pass
    for nsa in (True, False):                      # prefer not-seasonally-adjusted, accept adjusted as a fallback
        for m in cands:
            if ok(m, nsa):
                return m["id"], m["title"], m.get("seasonal_adjustment_short", "")
    raise RuntimeError("Could not find the wage series for '%s'" % phrase)


def build_wages():
    raw, sources = {}, {}
    for key, (phrase, hints) in WAGE_SERIES.items():
        sid, title, sa = resolve_wage_series(phrase, hints)
        raw[key] = observations(sid)
        sources[key] = {"series": sid, "title": title, "seasonal": sa}
    quarters = sorted(set.intersection(*[set(raw[k]) for k in raw]))
    weekly = {k: [raw[k][q] for q in quarters] for k in raw}
    return quarters, weekly, sources


# ---------- math ----------
def quarter_start(d):
    y, m, _ = map(int, d.split("-"))
    return "%04d-%02d-01" % (y, 3 * ((m - 1) // 3) + 1)


def labor_hours(price, date, quarters, weekly, income):
    """Hours to earn `price` at `income`, using the wage for the quarter containing `date` (or the latest earlier
    quarter if that one is missing or not published yet). Returns (hours, carried_flag)."""
    q = quarter_start(date)
    i = bisect.bisect_right(quarters, q) - 1
    if i < 0:
        return None, False
    return price / (weekly[income][i] / HOURS_PER_WEEK), quarters[i] != q


def chain_cpi(cpi, anchor_dates, anchor_value, out_filter=lambda d: True):
    """Scale a price index so that its value over `anchor_dates` equals `anchor_value` dollars."""
    pts = [cpi[d] for d in anchor_dates if d in cpi]
    if not pts:
        raise RuntimeError("anchor period missing from the index")
    base = statistics.mean(pts)
    return {d: anchor_value * v / base for d, v in cpi.items() if d >= START and out_filter(d)}


def make_item(spec, prices, quarters, weekly, stale=False):
    dates, pr, carried = [], [], []
    hours = {i["id"]: [] for i in INCOMES}
    for d in sorted(prices):
        if d < quarters[0]:
            continue
        row = {i["id"]: labor_hours(prices[d], d, quarters, weekly, i["id"]) for i in INCOMES}
        dates.append(d); pr.append(round(prices[d], 4)); carried.append(row["p50"][1])
        for k, (h, _) in row.items():
            hours[k].append(round(h, 5))
    if not dates:
        raise RuntimeError("no overlap with wage data")
    item = dict(spec)
    item.update(dates=dates, prices=pr, wage_carried=carried, hours=hours, last_obs=dates[-1], stale=stale)
    return item


# ---------- the individual sources ----------
def fetch_fred_item(row):
    iid, sid, name, unit, cat, expect, notes = row
    freq = "Quarterly" if sid == "MSPUS" else "Monthly"
    m = meta(sid)
    if expect not in m["title"].lower():
        raise RuntimeError("%s: series %s is titled %r (expected %r)" % (iid, sid, m["title"], expect))
    src = "Census/HUD via FRED" if sid == "MSPUS" else "BLS Average Price Data via FRED"
    return ({"id": iid, "name": name, "unit": unit, "category": cat, "cadence": freq,
             "source": src, "series": sid, "url": FRED_URL + sid, "method": "direct", "limitations": notes},
            observations(sid))


def fetch_rent():
    text = http_get(ZORI_URL)
    rows = list(csv.reader(io.StringIO(text)))
    head = rows[0]
    row = next(r for r in rows[1:] if r[head.index("RegionName")] == "United States")
    prices = {}
    for h, v in zip(head, row):
        if re.match(r"\d{4}-\d{2}-\d{2}$", h) and v:
            prices[h[:7] + "-01"] = float(v)
    spec = {"id": "rent", "name": "Rent (typical U.S. rent)", "unit": "month", "category": "Housing", "cadence": "Monthly",
            "source": "Zillow Observed Rent Index (ZORI), all homes, U.S.", "series": "ZORI", "url": "https://www.zillow.com/research/data/",
            "method": "direct",
            "limitations": ["Zillow's index of typical market rents, centered on the middle (35th to 65th percentile) of the rental market, not all renters.",
                            "It tracks rents of listed and observed units, which can differ from what existing tenants pay.",
                            "History starts in 2015.",
                            "Rent is a monthly bill, so one unit is one month."]}
    return spec, prices


def fetch_vehicles():
    prices, notes = {}, []
    with open(os.path.join(ROOT, "data", "manual", "new_vehicle_atp.csv")) as f:
        for r in csv.DictReader(f):
            prices[r["date"]] = float(r["value"])
    spec = {"id": "car", "name": "New vehicle (average transaction price)", "unit": "vehicle", "category": "Transportation",
            "cadence": "Monthly (added by hand)", "source": "Kelley Blue Book / Cox Automotive monthly reports",
            "series": "data/manual/new_vehicle_atp.csv", "url": "https://www.coxautoinc.com/insights-hub/", "method": "manual",
            "limitations": ["This is an average, not a median; expensive trucks and SUVs pull it up.",
                            "It excludes consumer incentives.",
                            "Only %d months are loaded so far. Gaps are not filled in; earlier history still needs to be added." % len(prices),
                            "Updated by hand from monthly reports (no free data feed exists), so it may lag by a few weeks."]}
    return spec, prices


def fetch_childcare():
    sid, kw = CPI_CHILD
    m = meta(sid)
    if kw not in m["title"].lower():
        raise RuntimeError("child care CPI title mismatch: %r" % m["title"])
    cpi = observations(sid)
    a = CHILD_ANCHOR
    prices = chain_cpi(cpi, ["%d-%02d-01" % (a["year"], mo) for mo in range(1, 13)], a["value"])
    spec = {"id": "childcare", "name": "Child care (one child, full year)", "unit": "year of care", "category": "Family & education",
            "cadence": "Monthly (estimated)", "source": "BLS CPI: day care and preschool, scaled to a 2022 dollar amount", "series": sid, "url": FRED_URL + sid,
            "method": "estimated",
            "limitations": ["ESTIMATE. Actual child care prices are not published monthly. This line takes a 2022 national average price ($%s, %s) and moves it with the BLS price index for day care and preschool." % (format(a["value"], ","), a["source"]),
                            "Real prices vary hugely by age of child, type of care and county; this is one national average.",
                            "The U.S. Labor Department's county-level child care database ends in 2022, so there is no more recent measured national figure to check against.",
                            "Price indexes adjust for quality, so changes in the index may differ from changes in what parents actually pay."]}
    return spec, prices


def fetch_college():
    sid, kw = CPI_COLLEGE
    m = meta(sid)
    if kw not in m["title"].lower():
        raise RuntimeError("college CPI title mismatch: %r" % m["title"])
    cpi = observations(sid)
    a = COLLEGE_ANCHOR
    prices = chain_cpi(cpi, [a["date"]], a["value"], out_filter=lambda d: d[5:7] == "09")
    spec = {"id": "college", "name": "College tuition & fees (public 4-year, in-state)", "unit": "year of tuition and fees", "category": "Family & education",
            "cadence": "Annual (estimated, September)", "source": "BLS CPI: college tuition and fees, scaled to the College Board 2025-26 average", "series": sid, "url": FRED_URL + sid,
            "method": "estimated",
            "limitations": ["ESTIMATE. Only the 2025-26 price ($%s, %s) is a published figure. Other years are that price moved by the BLS college tuition index." % (format(a["value"], ","), a["source"]),
                            "Sticker price for tuition and required fees only, for full-time in-state students at public four-year schools. It excludes room and board and what students pay after grants.",
                            "One point a year (each September)."]}
    return spec, prices


# ---------- assembly ----------
def load_previous():
    base = os.environ.get("SITE_URL", "").rstrip("/")
    if not base:
        return {}
    try:
        return {i["id"]: i for i in json.loads(http_get(base + "/data.json"))["items"]}
    except Exception as e:
        print("note: could not read the previously published data (%s)" % e, file=sys.stderr)
        return {}


def build(sample=False):
    quarters, weekly, wsrc = build_wages()
    prev = load_previous()
    items, specs = [], []

    def run(label, produce):
        try:
            for spec, prices in produce():
                items.append(make_item(spec, prices, quarters, weekly))
        except Exception as e:
            print("WARNING: %s failed: %s" % (label, e), file=sys.stderr)
            return label

    jobs = [(r[0], (lambda r=r: [fetch_fred_item(r)])) for r in FRED_ITEMS]
    jobs += [("rent", lambda: [fetch_rent()]), ("new vehicles", lambda: [fetch_vehicles()]),
             ("child care", lambda: [fetch_childcare()]), ("college", lambda: [fetch_college()])]
    for label, fn in jobs:
        run(label, fn)
    got = {i["id"] for i in items}
    for iid, old in prev.items():          # a source failed today: keep the last good copy, flagged as stale
        if iid not in got:
            old["stale"] = True
            old.setdefault("limitations", []).insert(0, "Today's refresh of this series failed, so this is the last successfully published copy.")
            items.append(old)
    if not items:
        sys.exit("No price series could be loaded.")
    order = ["Groceries", "Energy & utilities", "Transportation", "Housing", "Family & education"]
    items.sort(key=lambda i: (order.index(i["category"]) if i["category"] in order else 99))
    return {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sample": sample,
        "hours_per_week": HOURS_PER_WEEK,
        "incomes": INCOMES,
        "wages": {"quarters": quarters,
                  "weekly": {k: [round(v, 2) for v in vs] for k, vs in weekly.items()},
                  "sources": {k: dict(v, url=FRED_URL + v["series"]) for k, v in wsrc.items()}},
        "items": items,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "site", "data.json"))
    args = ap.parse_args()
    data = build()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print("wrote %s: %d items, wages through %s" % (args.out, len(data["items"]), data["wages"]["quarters"][-1]))
