"""QuantX AI — SIMULATED 54-parameter confluence + F&O options analytics.

Deterministic per symbol so the UI is stable. Clearly SIMULATED.
"""
import hashlib
import numpy as np

# 54 parameters grouped: Trend 14, Momentum 12, Volatility/Greeks 10,
# Market Structure & Order Flow 10, Options OI Confluence 8 = 54
CATEGORIES = [
    ("Trend", [
        "EMA 20/50 Cross", "EMA 50/200 Slope", "SuperTrend (10,3)", "ADX (14)",
        "Aroon Up/Down", "Parabolic SAR", "Ichimoku Cloud", "Linear Reg Slope",
        "HMA Direction", "Donchian Channel", "VWAP Position", "Price vs 200 DMA",
        "Higher-High Structure", "Trend Strength Composite",
    ]),
    ("Momentum", [
        "RSI (14)", "Stochastic %K/%D", "MACD Histogram", "Rate of Change",
        "CCI (20)", "Williams %R", "TSI", "Momentum Oscillator",
        "RSI Divergence", "Awesome Oscillator", "Ultimate Oscillator", "KST",
    ]),
    ("Volatility / Greeks", [
        "ATR (14)", "Bollinger Band Width", "Keltner Position", "India VIX Level",
        "IV Percentile", "Delta Skew", "Gamma Exposure", "Vega Sensitivity",
        "Theta Decay Rate", "Historical Vol (20)",
    ]),
    ("Market Structure & Order Flow", [
        "Support/Resistance Test", "Pivot Point Bias", "Volume Profile POC",
        "Cumulative Delta", "Bid/Ask Imbalance", "Liquidity Sweep",
        "Order Block Zone", "Fair Value Gap", "Breadth (Adv/Dec)", "Sector Correlation",
    ]),
    ("Options OI Confluence", [
        "Put/Call Ratio", "Max Pain Distance", "OI Buildup (Calls)",
        "OI Buildup (Puts)", "Change in OI", "Long/Short Buildup",
        "Strike Concentration", "IV Crush Signal",
    ]),
]


def _rng(*parts):
    seed = int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest(), 16) % (2**32)
    return np.random.default_rng(seed)


def confluence_breakdown(symbol: str):
    r = _rng("confluence", symbol)
    groups = []
    total_score = 0.0
    total_weight = 0.0
    for cat, params in CATEGORIES:
        rows = []
        for name in params:
            pr = _rng("param", symbol, name)
            reading_val = float(pr.uniform(-1, 1))
            reading = "BULLISH" if reading_val > 0.25 else "BEARISH" if reading_val < -0.25 else "NEUTRAL"
            weight = round(float(pr.uniform(0.5, 2.0)), 2)
            score = round((reading_val + 1) / 2 * 100)  # 0..100
            total_score += score * weight
            total_weight += weight
            rows.append({
                "name": name,
                "reading": reading,
                "weight": weight,
                "score": score,
            })
        cat_score = round(np.mean([x["score"] for x in rows]))
        groups.append({"category": cat, "count": len(params), "score": cat_score, "parameters": rows})
    composite = round(total_score / total_weight) if total_weight else 0
    return {
        "symbol": symbol,
        "parameter_count": 54,
        "composite_confluence": composite,
        "data_source": "SIMULATED MODEL",
        "groups": groups,
    }


def options_analytics(symbol: str, base: float = 24300):
    r = _rng("options", symbol)
    pcr = round(float(r.uniform(0.6, 1.6)), 2)
    step = 100 if base < 30000 else 100
    atm = round(base / step) * step
    max_pain = int(atm + r.choice([-2, -1, 0, 1, 2]) * step)
    iv_rank = int(r.uniform(15, 88))
    vix_corr = round(float(r.uniform(-0.9, -0.2)), 2)

    strikes = [atm + (i - 5) * step for i in range(11)]
    distribution = []
    for s in strikes:
        sr = _rng("oi", symbol, s)
        call_oi = int(sr.uniform(2, 40) * (1.4 if s >= atm else 0.8) * 100000)
        put_oi = int(sr.uniform(2, 40) * (1.4 if s <= atm else 0.8) * 100000)
        distribution.append({"strike": s, "call_oi": call_oi, "put_oi": put_oi})

    pcr_status = "Bullish" if pcr > 1.1 else "Bearish" if pcr < 0.8 else "Neutral"
    return {
        "symbol": symbol,
        "pcr": pcr,
        "pcr_status": pcr_status,
        "max_pain": max_pain,
        "atm_strike": atm,
        "iv_rank": iv_rank,
        "vix_correlation": vix_corr,
        "data_source": "SIMULATED MODEL",
        "oi_distribution": distribution,
    }
