"""Synthetic stand-in for the FRED API, used ONLY to preview the site and test the pipeline offline.
Numbers are invented (smooth growth + noise) and are not real data."""
import random, re
import build_data as B

WAGE_TITLES = {
    "LEU0252911200Q": ("first decile", 287, 0.035), "LEU0252911300Q": ("first quartile", 380, 0.032),
    "LEU0252881500Q": ("second quartile", 600, 0.031), "LEU0252911400Q": ("third quartile", 950, 0.030),
    "LEU0252911500Q": ("ninth decile", 1356, 0.030),
}
PRICE = {  # series: (title, start price, annual growth, noise)
    "APU0000708111": ("Average Price: Eggs, Grade A, Large (Cost per Dozen)", 0.95, 0.045, 0.06),
    "APU0000709112": ("Average Price: Milk, Fresh, Whole (Cost per Gallon)", 2.8, 0.02, 0.01),
    "APU0000702111": ("Average Price: Bread, White, Pan (Cost per Pound)", 0.95, 0.03, 0.01),
    "APU0000703112": ("Average Price: Ground Beef, 100% Beef (Cost per Pound)", 1.8, 0.05, 0.02),
    "APU0000706111": ("Average Price: Chicken, Fresh, Whole (Cost per Pound)", 1.0, 0.03, 0.02),
    "APU0000711211": ("Average Price: Bananas, Per Lb.", 0.5, 0.015, 0.01),
    "APU0000717311": ("Average Price: Coffee, 100%, Ground Roast", 3.2, 0.04, 0.03),
    "APU000074714":  ("Average Price: Gasoline, Unleaded Regular (Cost per Gallon)", 1.5, 0.05, 0.08),
    "APU000072610":  ("Average Price: Electricity per Kilowatt-Hour", 0.085, 0.03, 0.004),
    "APU000072620":  ("Average Price: Utility (Piped) Gas per Therm", 0.9, 0.04, 0.04),
    "MSPUS":         ("Median Sales Price of Houses Sold for the United States", 165000, 0.05, 0.02),
}

def _dates(quarterly, end="2026-06-01"):
    out, y, m = [], 2000, 1
    step = 3 if quarterly else 1
    while f"{y:04d}-{m:02d}-01" <= end:
        out.append(f"{y:04d}-{m:02d}-01"); m += step
        if m > 12: m -= 12; y += 1
    return out

def fake_fred_get(endpoint, **p):
    rnd = random.Random(7)
    sid = p.get("series_id")
    if endpoint == "series":
        if sid in WAGE_TITLES:
            ph = WAGE_TITLES[sid][0]
            title = f"Employed full time: Usual weekly nominal earnings ({ph}): Wage and salary workers: 16 years and over"
            return {"seriess": [{"id": sid, "title": title, "frequency_short": "Q", "seasonal_adjustment_short": "NSA"}]}
        return {"seriess": [{"id": sid, "title": PRICE[sid][0], "frequency_short": "M", "seasonal_adjustment_short": "NSA"}]}
    if endpoint == "series/search":
        return {"seriess": []}
    if endpoint == "series/observations":
        rnd = random.Random(hash(sid) % 1000 if False else sum(map(ord, sid)))
        if sid in WAGE_TITLES:
            _, base, g = WAGE_TITLES[sid]; ds = _dates(True)
            obs = [{"date": d, "value": "." if d == "2025-10-01" else str(round(base * (1 + g) ** (i / 4) * (1 + rnd.uniform(-.006, .006))))} for i, d in enumerate(ds)]
        else:
            _, base, g, nz = PRICE[sid]; ds = _dates(sid == "MSPUS")
            per = 4 if sid == "MSPUS" else 12
            obs = [{"date": d, "value": str(round(base * (1 + g) ** (i / per) * (1 + rnd.uniform(-nz, nz) * 2), 4))} for i, d in enumerate(ds)]
        return {"observations": obs}
    raise KeyError(endpoint)

CPI = {  # series: (title, start index, annual growth)
    "CUUR0000SEEB03": ("Consumer Price Index for All Urban Consumers: Day Care and Preschool in U.S. City Average", 100, 0.04),
    "CUUR0000SEEB01": ("Consumer Price Index for All Urban Consumers: College Tuition and Fees in U.S. City Average", 100, 0.05),
}

def fake_zori():
    import datetime
    head = "RegionID,SizeRank,RegionName,RegionType,StateName"
    ds = [f"{y}-{m:02d}-28" for y in range(2015, 2027) for m in range(1, 13) if (y, m) <= (2026, 9)]
    v = [str(round(1300 * 1.04 ** (i / 12), 2)) for i in range(len(ds))]
    return head + "," + ",".join(ds) + "\n102001,0,United States,country," + "," + ",".join(v) + "\n"

def fake_http_get(url):
    if "zillowstatic" in url:
        return fake_zori()
    raise KeyError(url)

_orig = fake_fred_get
def fake_fred_get2(endpoint, **p):
    sid = p.get("series_id")
    if sid in CPI:
        if endpoint == "series":
            return {"seriess": [{"id": sid, "title": CPI[sid][0], "frequency_short": "M", "seasonal_adjustment_short": "NSA"}]}
        if endpoint == "series/observations":
            _, base, g = CPI[sid]; rnd = random.Random(3)
            obs = [{"date": d, "value": "." if d == "2025-10-01" else str(round(base * (1 + g) ** (i / 12) * (1 + rnd.uniform(-.002, .002)), 3))}
                   for i, d in enumerate(_dates(False, "2026-09-01"))]
            return {"observations": obs}
    return _orig(endpoint, **p)

def install():
    B.fred_get = fake_fred_get2
    B.http_get = fake_http_get
