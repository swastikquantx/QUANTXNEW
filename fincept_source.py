"""QuantX AI — Fincept Market Feed integration (LIVE Indian data: NSE/BSE/MCX/F&O).

Direct REST integration per Fincept guide: base https://feed.fincept.in, X-API-Key header.
In-memory TTL caching to respect rate limits. Every method fails soft (returns None)
so callers can fall back to labeled SIMULATED data — the UI never breaks.
"""
import os
import time
from datetime import date, datetime
import requests


def _base():
    return os.environ.get("FINCEPT_BASE_URL", "https://feed.fincept.in")


def _key():
    return os.environ.get("FINCEPT_API_KEY", "").strip()


_CACHE = {}


def configured() -> bool:
    return bool(_key())


def _cached(key, ttl):
    v = _CACHE.get(key)
    if v and (time.time() - v[0] < ttl):
        return v[1]
    return None


def _get(path, params=None, ttl=5):
    j = _get_raw(path, params, ttl)
    return j.get("data") if isinstance(j, dict) else None


def _get_raw(path, params=None, ttl=5):
    if not configured():
        return None
    ck = f"raw:{path}?{sorted((params or {}).items())}"
    hit = _cached(ck, ttl)
    if hit is not None:
        return hit
    try:
        resp = requests.get(
            f"{_base()}{path}",
            params=params or {},
            headers={"X-API-Key": _key(), "accept": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        j = resp.json()
        _CACHE[ck] = (time.time(), j)
        return j
    except Exception:
        stale = _CACHE.get(ck)
        return stale[1] if stale else None


def fetch_instruments(exchange, segment=None, instrument_type=None, tradable=True, limit=500, offset=0):
    """Returns (rows, total)."""
    params = {"exchange": exchange, "limit": limit, "offset": offset}
    if segment:
        params["segment"] = segment
    if instrument_type:
        params["instrument_type"] = instrument_type
    if tradable:
        params["tradable"] = "true"
    j = _get_raw("/v1/instruments", params, ttl=3600)
    if not j:
        return [], 0
    return (j.get("data") or []), int(j.get("meta", {}).get("total", 0))


def quotes(symbols):
    """Public: {symbol: quote} for a batch of canonical symbols."""
    return _quotes_map(symbols) or {}


def health():
    try:
        r = requests.get(f"{_base()}/v1/health", timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def me():
    return _get("/v1/me", ttl=300)


def _quotes_map(symbols):
    """symbols: list of canonical symbols. Returns {symbol: quote} or None."""
    if not symbols:
        return {}
    data = _get("/v1/quotes", {"symbols": ",".join(symbols)}, ttl=4)
    if not data or "quotes" not in data:
        return None
    return {q["symbol"]: q for q in data["quotes"]}


def _direction(change_pct):
    if change_pct is None:
        return "NEUTRAL"
    return "BULLISH" if change_pct > 0.3 else "BEARISH" if change_pct < -0.3 else "NEUTRAL"


def _row_from_quote(display_symbol, name, q, segment, confluence):
    src = "LIVE" if (q.get("source") == "live") else "DELAYED (15m)"
    chg = q.get("change_percent")
    return {
        "symbol": display_symbol,
        "name": name,
        "ltp": q.get("price"),
        "change_pct": round(chg, 2) if chg is not None else 0.0,
        "confluence": confluence,
        "direction": _direction(chg),
        "data_source": src,
        "segment": segment,
    }


def equity_rows(exchange, pairs, segment, confluence_fn):
    """pairs: list of (root, name). Live quotes for EXCHANGE:ROOT. Returns rows or None."""
    triples = [(f"{exchange}:{root}", root, name) for root, name in pairs]
    return quotes_rows(triples, segment, confluence_fn)


def quotes_rows(triples, segment, confluence_fn):
    """triples: list of (canonical_symbol, display_symbol, name). Returns rows or None."""
    if not configured():
        return None
    qmap = _quotes_map([t[0] for t in triples])
    if not qmap:
        return None
    rows = []
    for canon, disp, name in triples:
        q = qmap.get(canon)
        if not q:
            continue
        rows.append(_row_from_quote(disp, name, q, segment, confluence_fn(disp)))
    return rows or None


def _nearest_future_symbol(root):
    """Find nearest non-expired MCX future contract symbol for a commodity root."""
    data = _get("/v1/instruments", {
        "exchange": "MCX", "root": root, "instrument_type": "FUTURE",
        "tradable": "true", "limit": 50,
    }, ttl=1800)
    items = data.get("instruments") if isinstance(data, dict) else data
    if not items:
        return None
    today = date.today()
    best = None
    for it in items:
        sym = it.get("symbol", "")
        exp = it.get("expiry")
        try:
            ed = date.fromisoformat(exp) if exp else None
        except Exception:
            ed = None
        if ed is None:
            parts = sym.split(":")
            if len(parts) >= 3 and len(parts[2]) == 8:
                try:
                    ed = datetime.strptime(parts[2], "%Y%m%d").date()
                except Exception:
                    ed = None
        if ed and ed >= today:
            if best is None or ed < best[0]:
                best = (ed, sym)
    return best[1] if best else None


def mcx_rows(pairs, confluence_fn):
    """pairs: list of (root, name). Returns rows or None."""
    if not configured():
        return None
    sym_map = {}
    for root, name in pairs:
        s = _nearest_future_symbol(root)
        if s:
            sym_map[root] = s
    if not sym_map:
        return None
    qmap = _quotes_map(list(sym_map.values()))
    if not qmap:
        return None
    rows = []
    for root, name in pairs:
        s = sym_map.get(root)
        q = qmap.get(s) if s else None
        if not q:
            continue
        rows.append(_row_from_quote(root, name, q, "MCX", confluence_fn(root)))
    return rows or None


def expiries(root, exchange="NSE", underlying_symbol=None):
    """Expiries come embedded in the option-chain payload."""
    if not configured():
        return None
    sym = underlying_symbol or f"{exchange}:{root}:INDEX"
    data = _get("/v1/optionchain", {"symbol": sym, "strikes": 1}, ttl=1800)
    if not data:
        return None
    out = []
    for e in (data.get("expiries") or []):
        v = e.get("expires_at") or e.get("date") if isinstance(e, dict) else e
        if v:
            out.append(v[:10])
    return out or None


def option_chain(underlying_symbol, root, exchange, expiry=None, strikes=10):
    """Map Fincept /v1/optionchain to our chain shape. Returns dict or None."""
    if not configured():
        return None
    params = {"symbol": underlying_symbol, "strikes": strikes, "greeks": "true"}
    data = _get("/v1/optionchain", params, ttl=4)
    if not data:
        return None
    legs = data.get("chain") or data.get("options") or data.get("strikes")
    spot = data.get("spot") or data.get("underlying_price") or data.get("ltp")
    if not legs or not isinstance(legs, list):
        return None

    def g(d, *keys):
        for k in keys:
            if isinstance(d, dict) and d.get(k) is not None:
                return d[k]
        return None

    rows = []
    for leg in legs:
        strike = g(leg, "strike", "strike_price")
        ce = leg.get("ce") or leg.get("call") or {}
        pe = leg.get("pe") or leg.get("put") or {}
        ceg = ce.get("greeks") or {}
        peg = pe.get("greeks") or {}
        if strike is None:
            continue
        rows.append({
            "strike": int(float(strike)),
            "ce_ltp": g(ce, "ltp", "price", "last_price") or 0,
            "ce_oi": int(g(ce, "oi", "open_interest") or 0),
            "ce_iv": round(float(g(ceg, "iv", "implied_volatility") or g(ce, "iv", "implied_volatility") or 0), 1),
            "pe_ltp": g(pe, "ltp", "price", "last_price") or 0,
            "pe_oi": int(g(pe, "oi", "open_interest") or 0),
            "pe_iv": round(float(g(peg, "iv", "implied_volatility") or g(pe, "iv", "implied_volatility") or 0), 1),
        })
    if not rows:
        return None
    rows.sort(key=lambda x: x["strike"])
    if not spot:
        spot = rows[len(rows) // 2]["strike"]
    atm = min(rows, key=lambda x: abs(x["strike"] - spot))["strike"]
    total_ce = sum(r["ce_oi"] for r in rows)
    total_pe = sum(r["pe_oi"] for r in rows)
    pcr = data.get("put_call_ratio")
    if pcr is None:
        pcr = round(total_pe / total_ce, 2) if total_ce else 0
    pcr = round(float(pcr), 2)
    max_pain = min(rows, key=lambda x: abs(x["ce_oi"] - x["pe_oi"]))["strike"] if total_ce or total_pe else atm
    exp_list = []
    for e in (data.get("expiries") or []):
        v = e.get("expires_at") or e.get("date") if isinstance(e, dict) else e
        if v:
            exp_list.append(v[:10])
    dte = 0
    if expiry:
        try:
            dte = max((date.fromisoformat(expiry[:10]) - date.today()).days, 0)
        except Exception:
            dte = 0
    return {
        "symbol": root, "name": root, "expiry": expiry or "",
        "spot": round(float(spot), 2), "atm": int(atm), "step": 0, "dte": dte,
        "pcr": pcr, "max_pain": int(max_pain), "data_source": "LIVE",
        "expiries": exp_list, "chain": rows,
    }
