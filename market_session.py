"""QuantX AI — NSE market session + pre-open order rules (IST).

Equity pre-open (09:00-09:15):
  09:00-09:08  Order entry  -> place / modify / cancel allowed (limit & market)
  09:08-09:12  Order matching & price discovery -> NO new/modify/cancel
  09:12-09:15  Buffer       -> transition, no new orders
Normal continuous: 09:15-15:30. Closing order window 15:30-15:40.
Post-close (closing price) session: 15:40-16:00.
F&O continuous starts 09:15 (no equity-style pre-open). MCX runs 09:00-23:30.
"""
from datetime import datetime, timezone, timedelta, time as dtime

IST = timezone(timedelta(hours=5, minutes=30))


def _mk(phase, label, is_tradeable, place, modify, cancel, message, tone):
    return {
        "phase": phase, "label": label, "is_tradeable": is_tradeable,
        "order_rules": {"can_place": place, "can_modify": modify, "can_cancel": cancel},
        "message": message, "tone": tone,
    }


def get_session(segment: str = None, now: datetime = None):
    now = now or datetime.now(IST)
    t = now.time()
    weekend = now.weekday() >= 5

    def between(h1, m1, h2, m2):
        return dtime(h1, m1) <= t < dtime(h2, m2)

    if weekend:
        base = _mk("CLOSED", "Closed (Weekend)", False, False, False, False,
                   "Markets closed for the weekend. Setups are for the next session.", "muted")
    elif t < dtime(9, 0):
        base = _mk("PRE_MARKET", "Pre-Market", False, False, False, False,
                   "Pre-market. Exchange pre-open begins at 09:00 — queue your limit orders.", "info")
    elif between(9, 0, 9, 8):
        base = _mk("PRE_OPEN_ENTRY", "Pre-Open · Order Entry (09:00–09:08)", False, True, True, True,
                   "Pre-open order entry: place / modify / cancel LIMIT orders now. Matched at 09:08.", "amber")
    elif between(9, 8, 9, 12):
        base = _mk("PRE_OPEN_MATCH", "Pre-Open · Price Discovery (09:08–09:12)", False, False, False, False,
                   "Order matching in progress — no new/modify/cancel. Equilibrium price being set.", "amber")
    elif between(9, 12, 9, 15):
        base = _mk("PRE_OPEN_BUFFER", "Pre-Open · Buffer (09:12–09:15)", False, False, False, False,
                   "Buffer period — transitioning to continuous market at 09:15.", "amber")
    elif between(9, 15, 15, 30):
        base = _mk("OPEN", "Market Open", True, True, True, True,
                   "Continuous market open — orders execute immediately.", "live")
    elif between(15, 30, 15, 40):
        base = _mk("CLOSING", "Closing (15:30–15:40)", False, False, False, False,
                   "Continuous session closed. Post-close (closing price) session 15:40–16:00.", "info")
    elif between(15, 40, 16, 0):
        base = _mk("POST_CLOSE", "Post-Close Session (15:40–16:00)", True, True, False, True,
                   "Post-close: orders accepted at the closing price only.", "info")
    else:
        base = _mk("CLOSED", "Closed", False, False, False, False,
                   "Markets closed. Setups are for the next session.", "muted")

    base["server_time_ist"] = now.strftime("%Y-%m-%d %H:%M:%S")
    base["segment"] = (segment or "").upper() or None

    # segment nuance
    seg = base["segment"]
    if seg in ("FNO",):
        base["segment_note"] = "F&O has no equity-style pre-open; continuous trading 09:15–15:30."
        if base["phase"].startswith("PRE_OPEN"):
            base["is_tradeable"] = False
    elif seg == "MCX":
        mcx_open = dtime(9, 0) <= t <= dtime(23, 30) and not weekend
        base["segment_note"] = "MCX commodities trade 09:00–23:30 IST."
        if mcx_open and base["phase"] in ("PRE_OPEN_ENTRY", "PRE_OPEN_MATCH", "PRE_OPEN_BUFFER", "CLOSING", "POST_CLOSE"):
            base = _mk("OPEN", "MCX Open", True, True, True, True, "MCX open — orders execute immediately.", "live")
            base["server_time_ist"] = now.strftime("%Y-%m-%d %H:%M:%S"); base["segment"] = seg
            base["segment_note"] = "MCX commodities trade 09:00–23:30 IST."
    elif seg == "CRYPTO":
        base = _mk("OPEN", "Crypto 24×7", True, True, True, True, "Crypto trades 24×7.", "live")
        base["server_time_ist"] = now.strftime("%Y-%m-%d %H:%M:%S"); base["segment"] = seg

    return base


def order_action(phase: str, segment: str = None) -> str:
    seg = (segment or "").upper()
    if seg == "CRYPTO":
        return "Trade now (24×7)"
    if seg == "FNO" and phase.startswith("PRE_OPEN"):
        return "F&O opens 09:15 — prepare order"
    return {
        "PRE_MARKET": "Queue for 09:00 pre-open",
        "PRE_OPEN_ENTRY": "Place LIMIT order now (till 09:08)",
        "PRE_OPEN_MATCH": "Locked — matching (09:08–09:12)",
        "PRE_OPEN_BUFFER": "Await 09:15 open",
        "OPEN": "Execute now — market open",
        "CLOSING": "Session closing — hold",
        "POST_CLOSE": "Place at closing price",
        "CLOSED": "Next-session setup",
    }.get(phase, "Next-session setup")
