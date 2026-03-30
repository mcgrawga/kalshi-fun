"""
Settlement engine — resolves pending bets against the Kalshi portfolio fills and
settlements APIs.

Called once at the top of every scan cycle to automatically mark resolved bets.

Outcome logic
-------------
    Early sell (position closed manually before market resolves):
        outcome = "sell"
        pnl     = sell_proceeds − original_cost − sell_fees

    Market resolution:
        YES bet + market resolves YES → win
        YES bet + market resolves NO  → loss
        NO  bet + market resolves NO  → win
        NO  bet + market resolves YES → loss
        Any bet + void market         → void, pnl = 0

P&L formulas
------------
    Early sell:
        pnl = (sell_price × contracts_sold) − cost − sell_fee_dollars

    Market resolution:
        pnl = (revenue_cents / 100) − cost − fee_dollars
"""

from clients.kalshi_client import KalshiClient
from db.bets import get_open_bets, settle_bet, get_unsettled_skipped_bets, settle_skipped_bet


def settle_open_bets(kalshi: KalshiClient) -> None:
    """
    Check all pending bets (outcome IS NULL, fill_count > 0) for:
      1. Market resolution — detected via GET /portfolio/settlements
      2. Early sells — detected via GET /portfolio/fills (action=sell),
         only for bets NOT already found in settlements.
    """
    open_bets = get_open_bets()
    if not open_bets:
        return

    print(f"\n[Settle] Checking {len(open_bets)} pending bet(s)...")

    # ── Pass 1: market resolution via settlements API ─────────────────────────
    # Always check settlements first. Kalshi generates "sell" fills internally
    # when it liquidates winning positions at payout — those must NOT be
    # misidentified as manual early-closes.
    try:
        settlements = kalshi.get_settlements()
    except Exception as exc:
        print(f"[Settle] ⚠  Could not fetch settlements: {exc}")
        settlements = []

    settled_map: dict[str, dict] = {s["ticker"]: s for s in settlements}

    still_open: list = []
    resolved = 0

    for bet in open_bets:
        ticker = bet["ticker"]
        s = settled_map.get(ticker)
        if s is None:
            still_open.append(bet)
            continue

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
            still_open.append(bet)
            continue

        settle_bet(bet["id"], outcome, pnl)
        icon = "✅" if outcome == "win" else ("❌" if outcome == "loss" else "⚪")
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        print(f"  {icon}  {ticker} · {side} · {outcome.upper()} · {pnl_str}")
        resolved += 1

    # ── Pass 2: per-ticker resolution + early sell detection ───────────────────
    # For bets not found in the bulk settlements response, check each one
    # individually. The market's own `result` field is the authoritative gate:
    # if it has resolved, it's always a win/loss/void — NEVER a manual sell.
    for bet in still_open:
        ticker = bet["ticker"]
        side   = bet["side"].upper()

        # First: targeted settlement lookup for this specific ticker.
        # This catches bets that fell through the bulk settlements query.
        try:
            s = kalshi.get_settlement_for_ticker(ticker)
        except Exception as exc:
            print(f"[Settle] ⚠  Could not fetch settlement for {ticker}: {exc}")
            s = None

        if s is not None:
            market_result = (s.get("market_result") or "").lower()
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
                continue
            settle_bet(bet["id"], outcome, pnl)
            icon = "✅" if outcome == "win" else ("❌" if outcome == "loss" else "⚪")
            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            print(f"  {icon}  {ticker} · {side} · {outcome.upper()} · {pnl_str}")
            resolved += 1
            continue

        # Second: check if the market itself has a result. If the market has
        # resolved, Kalshi's settlement fills (action='sell' at $1.00) are
        # internal payouts — not a manual early close. Never treat a resolved
        # market as a sell.
        # IMPORTANT: a closed/settled market returns 404 from get_market.
        # Any exception here means the market is no longer open → leave pending.
        try:
            market = kalshi.get_market(ticker)
            market_result = (market.get("result") or "").lower()
            market_status = (market.get("status") or "").lower()
            if market_result in ("yes", "no", "void") or market_status != "open":
                # Resolved or no longer open — leave pending for next cycle.
                continue
        except Exception:
            # Market not found (likely closed/settled) — do NOT check fills.
            continue

        # Third: market is still open — check fills for a manual early sell.
        try:
            fills = kalshi.get_fills(ticker)
        except Exception as exc:
            print(f"[Settle] ⚠  Could not fetch fills for {ticker}: {exc}")
            continue

        sell_fills = [f for f in fills if f.get("action") == "sell"]
        if not sell_fills:
            continue

        total_sold = sum(float(f.get("count_fp", 0)) for f in sell_fills)
        if total_sold < float(bet["fill_count"]):
            continue  # Partial sell — leave pending

        sell_proceeds = sum(
            float(f["yes_price_dollars"]) * float(f["count_fp"]) if side == "YES"
            else float(f["no_price_dollars"]) * float(f["count_fp"])
            for f in sell_fills
        )
        sell_fees = sum(float(f.get("fee_cost") or 0) for f in sell_fills)
        pnl = sell_proceeds - float(bet["cost"]) - sell_fees

        settle_bet(bet["id"], "sell", pnl)
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        print(f"  💰  {ticker} · {side} · SOLD (early close) · {pnl_str}")
        resolved += 1

    if resolved:
        print(f"[Settle] {resolved} bet(s) settled.\n")
    else:
        print(f"[Settle] No new settlements found.\n")


def settle_skipped_bets(kalshi: KalshiClient) -> None:
    """
    Resolve unsettled skipped bets by checking the Kalshi market result.

    Since no money was placed, there's no P&L — we just record whether the
    skipped bet *would have* won or lost.  This lets you query:
        SELECT reason, outcome, COUNT(*) FROM skipped_bets GROUP BY reason, outcome
    to evaluate whether your filters are saving you money.

    Uses GET /markets/{ticker} to check the market's result field.
    """
    pending = get_unsettled_skipped_bets()
    if not pending:
        return

    resolved = 0

    for skip in pending:
        ticker = skip["ticker"]
        side = skip["side"].upper()

        try:
            market = kalshi.get_market(ticker)
        except Exception:
            # Market not found / API error — skip for now, retry next cycle
            continue

        market_result = (market.get("result") or "").lower()
        if market_result not in ("yes", "no", "void"):
            continue  # not yet resolved

        if market_result == "void":
            outcome = "void"
        else:
            won = (side == "YES" and market_result == "yes") or \
                  (side == "NO"  and market_result == "no")
            outcome = "would_have_won" if won else "would_have_lost"

        settle_skipped_bet(ticker, side, outcome)
        resolved += 1
