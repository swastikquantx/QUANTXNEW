"""QuantX AI — probability calibration engine (SIMULATED backtest).

Generates immutable frozen opportunity snapshots and evaluates directional
outcomes at multiple horizons, then scores probability calibration
(reliability by band + Brier score + ECE).

All data is clearly SIMULATED — never presented as live/real results.
"""
import hashlib
import uuid
from datetime import datetime, timezone, timedelta, date

import numpy as np

HORIZONS = [7, 15, 30, 60, 90]
BANDS = [(0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 0.90), (0.90, 1.0001)]

SYMBOLS = [
    ("NIFTY50", "Nifty 50", 24300),
    ("BANKNIFTY", "Bank Nifty", 52000),
    ("FINNIFTY", "FinNifty", 24000),
    ("NIFTYIT", "Nifty IT", 43000),
    ("NIFTYAUTO", "Nifty Auto", 26000),
    ("NIFTYPHARMA", "Nifty Pharma", 22400),
    ("NIFTYFMCG", "Nifty FMCG", 57000),
]
SIGNAL_BY_DIR = {"BULLISH": "Call Buy", "BEARISH": "Put Buy", "NEUTRAL": "Neutral Straddle"}


def _rng(*parts) -> np.random.Generator:
    seed = int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest(), 16) % (2**32)
    return np.random.default_rng(seed)


def band_label(low, high):
    hi = 100 if high > 1 else int(round(high * 100))
    return f"{int(round(low * 100))}-{hi}%"


def _band_index(p):
    for i, (lo, hi) in enumerate(BANDS):
        if lo <= p < hi:
            return i
    return len(BANDS) - 1


def make_opportunities_for_date(gen_date: date, per_day: int = 4):
    """Create immutable frozen snapshots for a given generation date."""
    rng = _rng("gen", gen_date.isoformat())
    picks = rng.choice(len(SYMBOLS), size=min(per_day, len(SYMBOLS)), replace=False)
    now_iso = datetime.now(timezone.utc).isoformat()
    docs = []
    for idx in picks:
        symbol, name, base = SYMBOLS[int(idx)]
        r = _rng("opp", gen_date.isoformat(), symbol)
        prob = float(np.clip(r.normal(0.70, 0.11), 0.50, 0.97))
        direction = str(r.choice(["BULLISH", "BEARISH", "NEUTRAL"], p=[0.45, 0.35, 0.20]))
        spot = round(base * (1 + r.normal(0, 0.01)), 2)
        rr = round(float(r.uniform(1.4, 2.6)), 1)
        risk = round(spot * 0.006, 2)
        sl = round(spot - risk if direction != "BEARISH" else spot + risk, 2)
        target = round(spot + risk * rr if direction != "BEARISH" else spot - risk * rr, 2)
        docs.append({
            "id": f"opp_{uuid.uuid4().hex[:12]}",
            "gen_date": gen_date.isoformat(),
            "symbol": symbol,
            "name": name,
            "signal_type": SIGNAL_BY_DIR[direction],
            "direction": direction,
            "probability": round(prob * 100, 1),   # stored as percent, immutable
            "entry": spot,
            "stop_loss": sl,
            "target": target,
            "risk_reward": f"1:{rr}",
            "data_source": "SIMULATED MODEL",
            "frozen_at": now_iso,
            "immutable": True,
        })
    return docs


def realized_favorable(prob_frac: float, opp_id: str, horizon: int):
    """Simulated directional resolution with mild real-world overconfidence bias."""
    r = _rng("outcome", opp_id, horizon)
    # overconfidence: high-probability calls resolve slightly below their stated odds
    p_eff = float(np.clip(prob_frac - 0.06 * max(prob_frac - 0.5, 0) / 0.5, 0.02, 0.99))
    favorable = 1 if r.random() < p_eff else 0
    magnitude = float(abs(r.normal(0.8, 0.4)))
    move = round(magnitude if favorable else -magnitude * 0.7, 2)
    return favorable, move


def build_outcome(opp: dict, horizon: int):
    prob_frac = opp["probability"] / 100.0
    favorable, move = realized_favorable(prob_frac, opp["id"], horizon)
    return {
        "id": f"out_{uuid.uuid4().hex[:12]}",
        "opportunity_id": opp["id"],
        "symbol": opp["symbol"],
        "gen_date": opp["gen_date"],
        "horizon": horizon,
        "probability": round(prob_frac, 4),
        "favorable": favorable,
        "realized_move_pct": move,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "data_source": "SIMULATED MODEL",
    }


def compute_calibration(points):
    """points: list of {probability(frac), favorable(0/1)}. Returns Brier, ECE, bands."""
    n = len(points)
    if n == 0:
        return {"count": 0, "brier_score": None, "ece": None, "bands": []}
    probs = np.array([p["probability"] for p in points], dtype=float)
    outs = np.array([p["favorable"] for p in points], dtype=float)
    brier = float(np.mean((probs - outs) ** 2))

    bands = []
    ece = 0.0
    for lo, hi in BANDS:
        mask = (probs >= lo) & (probs < hi)
        cnt = int(mask.sum())
        if cnt == 0:
            bands.append({
                "band": band_label(lo, hi), "band_low": lo, "count": 0,
                "predicted_avg": None, "observed_favorable": None,
            })
            continue
        pred = float(probs[mask].mean())
        obs = float(outs[mask].mean())
        ece += (cnt / n) * abs(pred - obs)
        bands.append({
            "band": band_label(lo, hi), "band_low": lo, "count": cnt,
            "predicted_avg": round(pred * 100, 1), "observed_favorable": round(obs * 100, 1),
        })
    return {
        "count": n,
        "brier_score": round(brier, 4),
        "ece": round(ece, 4),
        "bands": bands,
    }


def brier_grade(brier):
    if brier is None:
        return "—"
    if brier <= 0.12:
        return "Excellent"
    if brier <= 0.18:
        return "Good"
    if brier <= 0.25:
        return "Fair"
    return "Poor"
