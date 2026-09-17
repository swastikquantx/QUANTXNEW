"""QuantX AI — multi-segment instrument universe + F&O chain + opportunity generation.

Segments: NSE equity, BSE equity, F&O (index+stock futures/options with expiries),
MCX commodities. Crypto is handled by crypto_source.py (LIVE via CoinGecko).

Indian-segment quotes are deterministic per (symbol, day) — clearly labeled honest
data-source tags. A real broker feed (Zerodha/Motilal) can replace these generators.
"""
import hashlib
from datetime import date, datetime, timedelta, timezone
import numpy as np

IST = timezone(timedelta(hours=5, minutes=30))

SEGMENTS = ["NSE", "BSE", "FNO", "MCX", "CRYPTO"]
SEGMENT_LABELS = {
    "NSE": "NSE Equity", "BSE": "BSE Equity", "FNO": "F&O",
    "MCX": "Commodities (MCX)", "CRYPTO": "Crypto",
}
# Honest data-source labels per segment (no real Indian feed connected yet)
SEGMENT_SOURCE = {
    "NSE": "SIMULATED MODEL", "BSE": "SIMULATED MODEL",
    "FNO": "SIMULATED MODEL", "MCX": "SIMULATED MODEL", "CRYPTO": "LIVE",
}

# (symbol, name, base_price)
NSE_STOCKS = [
    ("RELIANCE", "Reliance Industries", 2950), ("TCS", "Tata Consultancy", 4180),
    ("HDFCBANK", "HDFC Bank", 1685), ("ICICIBANK", "ICICI Bank", 1240),
    ("INFY", "Infosys", 1870), ("HINDUNILVR", "Hindustan Unilever", 2480),
    ("ITC", "ITC", 465), ("SBIN", "State Bank of India", 830),
    ("BHARTIARTL", "Bharti Airtel", 1520), ("KOTAKBANK", "Kotak Mahindra Bank", 1760),
    ("LT", "Larsen & Toubro", 3620), ("BAJFINANCE", "Bajaj Finance", 7200),
    ("AXISBANK", "Axis Bank", 1180), ("ASIANPAINT", "Asian Paints", 2920),
    ("MARUTI", "Maruti Suzuki", 12800), ("SUNPHARMA", "Sun Pharma", 1780),
    ("TITAN", "Titan Company", 3380), ("ULTRACEMCO", "UltraTech Cement", 11200),
    ("WIPRO", "Wipro", 545), ("ONGC", "ONGC", 275),
    ("NTPC", "NTPC", 415), ("POWERGRID", "Power Grid", 335),
    ("TATAMOTORS", "Tata Motors", 985), ("TATASTEEL", "Tata Steel", 152),
    ("JSWSTEEL", "JSW Steel", 920), ("NESTLEIND", "Nestle India", 2510),
    ("HCLTECH", "HCL Technologies", 1790), ("TECHM", "Tech Mahindra", 1640),
    ("ADANIENT", "Adani Enterprises", 2950), ("ADANIPORTS", "Adani Ports", 1420),
    ("COALINDIA", "Coal India", 480), ("GRASIM", "Grasim Industries", 2680),
    ("HINDALCO", "Hindalco", 660), ("DRREDDY", "Dr Reddy's Labs", 1310),
    ("CIPLA", "Cipla", 1560), ("BAJAJFINSV", "Bajaj Finserv", 1720),
    ("BRITANNIA", "Britannia", 5240), ("EICHERMOT", "Eicher Motors", 4820),
    ("HEROMOTOCO", "Hero MotoCorp", 5480), ("INDUSINDBK", "IndusInd Bank", 1420),
    ("M&M", "Mahindra & Mahindra", 2860), ("APOLLOHOSP", "Apollo Hospitals", 7120),
    ("TATACONSUM", "Tata Consumer", 1120), ("BPCL", "BPCL", 615),
    ("SBILIFE", "SBI Life", 1560), ("HDFCLIFE", "HDFC Life", 685),
    ("LTIM", "LTIMindtree", 6120), ("DIVISLAB", "Divi's Labs", 4980),
    ("PIDILITIND", "Pidilite", 3080), ("DMART", "Avenue Supermarts", 4720),
]

BSE_STOCKS = [
    ("RELIANCE", "Reliance Industries", 2950), ("TCS", "Tata Consultancy", 4180),
    ("HDFCBANK", "HDFC Bank", 1685), ("ICICIBANK", "ICICI Bank", 1240),
    ("INFY", "Infosys", 1870), ("HINDUNILVR", "Hindustan Unilever", 2480),
    ("ITC", "ITC", 465), ("SBIN", "State Bank of India", 830),
    ("BHARTIARTL", "Bharti Airtel", 1520), ("KOTAKBANK", "Kotak Mahindra Bank", 1760),
    ("LT", "Larsen & Toubro", 3620), ("BAJFINANCE", "Bajaj Finance", 7200),
    ("AXISBANK", "Axis Bank", 1180), ("ASIANPAINT", "Asian Paints", 2920),
    ("MARUTI", "Maruti Suzuki", 12800), ("SUNPHARMA", "Sun Pharma", 1780),
    ("TITAN", "Titan Company", 3380), ("ULTRACEMCO", "UltraTech Cement", 11200),
    ("WIPRO", "Wipro", 545), ("ONGC", "ONGC", 275),
    ("NTPC", "NTPC", 415), ("POWERGRID", "Power Grid", 335),
    ("TATAMOTORS", "Tata Motors", 985), ("TATASTEEL", "Tata Steel", 152),
    ("JSWSTEEL", "JSW Steel", 920), ("NESTLEIND", "Nestle India", 2510),
    ("HCLTECH", "HCL Technologies", 1790), ("TECHM", "Tech Mahindra", 1640),
    ("ADANIENT", "Adani Enterprises", 2950), ("ADANIPORTS", "Adani Ports", 1420),
]

MCX_COMMODITIES = [
    ("GOLD", "Gold (10g)", 72500), ("SILVER", "Silver (1kg)", 89500),
    ("CRUDEOIL", "Crude Oil (bbl)", 6180), ("NATURALGAS", "Natural Gas (mmBtu)", 245),
    ("COPPER", "Copper (kg)", 845), ("ZINC", "Zinc (kg)", 258),
    ("ALUMINIUM", "Aluminium (kg)", 232), ("LEAD", "Lead (kg)", 188),
    ("NICKEL", "Nickel (kg)", 1520), ("COTTON", "Cotton (bale)", 58200),
    ("MENTHAOIL", "Mentha Oil (kg)", 945), ("GOLDM", "Gold Mini (10g)", 72400),
]

# F&O underlyings: indices + liquid single-stock F&O
FNO_INDICES = [
    ("NIFTY", "Nifty 50", 24300, "index"), ("BANKNIFTY", "Bank Nifty", 52000, "index"),
    ("FINNIFTY", "FinNifty", 24000, "index"), ("MIDCPNIFTY", "Midcap Nifty", 12600, "index"),
    ("SENSEX", "BSE Sensex", 80200, "index"),
]
FNO_STOCKS = [
    ("RELIANCE", "Reliance", 2950), ("TCS", "TCS", 4180), ("HDFCBANK", "HDFC Bank", 1685),
    ("ICICIBANK", "ICICI Bank", 1240), ("INFY", "Infosys", 1870), ("SBIN", "SBI", 830),
    ("TATAMOTORS", "Tata Motors", 985), ("AXISBANK", "Axis Bank", 1180),
    ("BAJFINANCE", "Bajaj Finance", 7200), ("MARUTI", "Maruti", 12800),
]

DIRECTIONS = ["BULLISH", "BEARISH", "NEUTRAL"]

# ---- Load full instrument universe from source (universe_data.json) ----
import json as _json
import os as _os

_UF = _os.path.join(_os.path.dirname(__file__), "universe_data.json")
try:
    with open(_UF) as _f:
        _U = _json.load(_f)
    _nse = [(x["sym"], x["name"], x["price"]) for x in _U if x["seg"] == "NSE"]
    _bse = [(x["sym"], x["name"], x["price"]) for x in _U if x["seg"] == "BSE"]
    _fidx = [(x["sym"], x["name"], x["price"], "index") for x in _U if x.get("isFO") and x.get("isIndex")]
    _fstk = [(x["sym"], x["name"], x["price"]) for x in _U if x.get("isFO") and not x.get("isIndex")]
    if _nse:
        NSE_STOCKS = _nse
    if _bse:
        BSE_STOCKS = _bse
    if _fidx:
        FNO_INDICES = _fidx
    if _fstk:
        FNO_STOCKS = _fstk
except Exception:
    pass


def _rng(*parts):
    seed = int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest(), 16) % (2**32)
    return np.random.default_rng(seed)


def _ist_today():
    return datetime.now(IST).date()


def _quote(symbol, name, base, segment):
    r = _rng("quote", segment, symbol, _ist_today().isoformat())
    change = round(float(r.normal(0, 1.1)), 2)
    ltp = round(base * (1 + change / 100), 2)
    confluence = int(np.clip(r.normal(60, 15), 12, 96))
    direction = "BULLISH" if change > 0.3 else "BEARISH" if change < -0.3 else "NEUTRAL"
    return {
        "symbol": symbol, "name": name, "ltp": ltp, "change_pct": change,
        "confluence": confluence, "direction": direction,
        "data_source": SEGMENT_SOURCE[segment], "segment": segment,
    }


def instruments(segment: str, search: str = "", limit: int = 200):
    segment = segment.upper()
    if segment == "NSE":
        rows = [(_quote(s, n, b, "NSE")) for s, n, b in NSE_STOCKS]
    elif segment == "BSE":
        rows = [(_quote(s, n, b, "BSE")) for s, n, b in BSE_STOCKS]
    elif segment == "MCX":
        rows = [(_quote(s, n, b, "MCX")) for s, n, b in MCX_COMMODITIES]
    elif segment == "FNO":
        rows = [(_quote(s, n, b, "FNO")) for s, n, b, _ in FNO_INDICES] + \
               [(_quote(s, n, b, "FNO")) for s, n, b in FNO_STOCKS]
    else:
        rows = []
    if search:
        q = search.lower()
        rows = [x for x in rows if q in x["symbol"].lower() or q in x["name"].lower()]
    return rows[:limit]


# ---------------- F&O expiries + option chain ----------------
def _next_weekdays(target_weekday=3, count=4):
    """Next `count` weekly expiries on given weekday (3=Thursday)."""
    today = _ist_today()
    days_ahead = (target_weekday - today.weekday()) % 7
    first = today + timedelta(days=days_ahead or 7 if days_ahead == 0 else days_ahead)
    if days_ahead == 0:
        first = today  # today is expiry day
    out = []
    d = first
    for _ in range(count):
        out.append(d)
        d = d + timedelta(days=7)
    return out


def _monthly_expiries(count=3):
    today = _ist_today()
    out = []
    y, m = today.year, today.month
    for _ in range(count):
        # last Thursday of month m
        if m == 12:
            nxt = date(y + 1, 1, 1)
        else:
            nxt = date(y, m + 1, 1)
        last = nxt - timedelta(days=1)
        while last.weekday() != 3:
            last -= timedelta(days=1)
        if last >= today:
            out.append(last)
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def _underlying(symbol):
    for s, n, b, _ in FNO_INDICES:
        if s == symbol.upper():
            return n, b, True
    for s, n, b in FNO_STOCKS:
        if s == symbol.upper():
            return n, b, False
    return symbol, 1000, False


def fno_symbols():
    return [{"symbol": s, "name": n, "kind": "index"} for s, n, _, _ in FNO_INDICES] + \
           [{"symbol": s, "name": n, "kind": "stock"} for s, n, _ in FNO_STOCKS]


def expiries(symbol: str):
    _, _, is_index = _underlying(symbol)
    if is_index:
        wk = _next_weekdays(3, 4)
        mo = _monthly_expiries(2)
        allx = sorted(set([*wk, *mo]))
    else:
        allx = _monthly_expiries(3)
    return [d.isoformat() for d in allx]


def option_chain(symbol: str, expiry: str):
    name, base, is_index = _underlying(symbol)
    r = _rng("chain", symbol, expiry, _ist_today().isoformat())
    spot = round(base * (1 + float(r.normal(0, 0.006))), 2)
    step = 50 if is_index and base < 30000 else (100 if is_index else max(5, round(base * 0.01 / 5) * 5))
    atm = round(spot / step) * step
    try:
        exp_date = date.fromisoformat(expiry)
        dte = max((exp_date - _ist_today()).days, 0)
    except Exception:
        dte = 7
    tv = max(dte, 1) ** 0.5
    rows = []
    for i in range(-10, 11):
        K = atm + i * step
        sr = _rng("strike", symbol, expiry, K)
        iv = round(float(sr.uniform(11, 28)), 1)
        time_val = round(spot * (iv / 100) * (tv / 19), 2)
        ce_ltp = round(max(spot - K, 0) + time_val, 2)
        pe_ltp = round(max(K - spot, 0) + time_val, 2)
        ce_oi = int(sr.uniform(2, 45) * (1.3 if K >= atm else 0.7) * 100000)
        pe_oi = int(sr.uniform(2, 45) * (1.3 if K <= atm else 0.7) * 100000)
        rows.append({
            "strike": int(K), "ce_ltp": ce_ltp, "ce_oi": ce_oi, "ce_iv": iv,
            "pe_ltp": pe_ltp, "pe_oi": pe_oi, "pe_iv": round(iv + float(sr.uniform(-2, 2)), 1),
        })
    total_ce = sum(x["ce_oi"] for x in rows)
    total_pe = sum(x["pe_oi"] for x in rows)
    pcr = round(total_pe / total_ce, 2) if total_ce else 0
    max_pain = min(rows, key=lambda x: abs(x["ce_oi"] - x["pe_oi"]))["strike"]
    return {
        "symbol": symbol.upper(), "name": name, "expiry": expiry,
        "spot": spot, "atm": int(atm), "step": step, "dte": dte,
        "pcr": pcr, "max_pain": max_pain, "data_source": SEGMENT_SOURCE["FNO"],
        "chain": rows,
    }
