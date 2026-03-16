"""
Settlement engine — resolves pending bets against the Kalshi portfolio settlements API.

Called once at startup before each scan to automatically mark resolved bets.

Outcome logic
-------------
    YES bet + market resolves YES → win
    YES bet + market resolves NO  → loss
    NO  bet + market resolves NO  → win
    NO  bet + market resolves YES → loss
    Any bet + void market         → void, pnl = 0

P&L formula
-----------
    pnl = (revenue_cents / 100) - cost - fee_dollars

    revenue  : gross payout Kalshi credits you (in cents per the API)
    cost     : fill_count × price_per_contract, stored in DB at bet time
    fee_cost : Kalshi maker/taker fee in dollars (string in API response)
"""

from clients.kalshi_client import KalshiClient
from db.bets import get_open_bets, settle_bet


def settle_open_bets(kalshi: KalshiClient) -> None:
    """
    Check all pending bets (outcome IS NULL, fill_count > 0) against the Kalshi
    settlements API and write outcome + pnl back to the DB for any that have resolved.
    """
    open_bets = get_open_bets()
    if not open_bets:
        return

    print(f"\n[Settle] Checking {len(open_bets)} pending bet(s)...")

    try:
        settlements = kalshi.get_settlements()
    except Exception as exc:
        print(f"[Settle] ⚠  Could not fetch settlements: {exc}")
        return

    # Build ticker → settlement map for O(1) lookup
    settled_map: dict[str, dict] = {s["ticker"]: s for s in settlements}

    resolved = 0
    for bet in open_bets:
        ticker = bet["ticker"]
        s = settled_map.get(ticker)
        if s is None:
            continue  # market not yet settled

        market_result = (s.get("market_result") or "").lower()
        side = bet["side"].upper()

        if market_result == "void":
            outcome = "void"
            pnl = 0.0
        elif market_result in ("yes", "no"):
            won = (side == "YES" and market_result == "yes") or \
                  (side == "NO"  and market_result == "no")
            outcome = "win" if won else "loss"
            revenue_dollars = int(s.get("revenue", 0)) / 100.0
            fee_dollars = float(s.get("fee_cost") or 0)
            pnl = revenue_dollars - float(bet["cost"]) - fee_dollars
        else:
            continue  # unrecognized result — leave pending

        settle_bet(bet["id"], outcome, pnl)
        icon = "✅" if outcome == "win" else ("❌" if outcome == "loss" else "⚪")
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        print(f"  {icon}  {ticker} · {side} · {outcome.upper()} · {pnl_str}")
        resolved += 1

    if resolved:
        print(f"[Settle] {resolved} bet(s) settled.\n")
    else:
        print(f"[Settle] No new settlements found.\n")
