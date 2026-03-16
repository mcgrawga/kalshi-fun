"""
Kalshi Value Bet Scanner
========================
Polls Kalshi and The Odds API, normalizes odds to vig-removed probabilities,
fuzzy-matches markets across the two platforms, and flags Kalshi markets where
the sharp book's implied probability exceeds Kalshi's ask-implied probability
by at least MIN_EDGE.

Usage
-----
    python main.py                     # scan all upcoming games
    python main.py --date tomorrow     # only tomorrow's games
    python main.py --date 2026-03-14   # specific date
"""

import argparse
import sys
import time
import re
from datetime import date, datetime, timedelta, timezone

import config
from clients.kalshi_client import KalshiClient
from clients.odds_client import OddsClient
from engine.normalizer import normalize_all_games
from engine.matcher import match_markets
from engine.analyzer import scan_all
from alerts.notifier import print_opportunities, print_summary
from models.market import KalshiMarket
from db.bets import init_db, record_bet, get_active_tickers
from engine.settler import settle_open_bets


_TICKER_DATE_RE = re.compile(r'-(\d{2})([A-Z]{3})(\d{2})[A-Z]', re.IGNORECASE)
_MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def _parse_game_date_from_ticker(ticker: str) -> date | None:
    """Extract the game date encoded in the Kalshi ticker.

    Format: KXNBAGAME-26MAR14SACLAC-SAC  →  2026-03-14
    The date segment is YYMONDD immediately after the first dash.
    """
    m = _TICKER_DATE_RE.search(ticker.upper())
    if not m:
        return None
    try:
        year = 2000 + int(m.group(1))
        month = _MONTH_MAP.get(m.group(2))
        day = int(m.group(3))
        if month:
            return date(year, month, day)
    except (ValueError, KeyError):
        pass
    return None


def _parse_kalshi_market(raw: dict) -> KalshiMarket:
    """Convert a raw Kalshi API response dict into a typed KalshiMarket.
    
    We use expected_expiration_time (set ~2h after tip-off) as the game time
    for matching against sportsbook commence_time. close_time is the settlement
    deadline (weeks away) and is useless for matching purposes.
    """
    ticker = raw.get("ticker", "")
    game_time_str = raw.get("expected_expiration_time") or raw.get("close_time", "")
    try:
        close_time = datetime.fromisoformat(game_time_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        close_time = datetime.now(timezone.utc)

    return KalshiMarket(
        ticker=ticker,
        title=raw.get("title", ""),
        yes_ask=float(raw.get("yes_ask_dollars", 0) or 0),
        no_ask=float(raw.get("no_ask_dollars", 0) or 0),
        yes_bid=float(raw.get("yes_bid_dollars", 0) or 0),
        no_bid=float(raw.get("no_bid_dollars", 0) or 0),
        close_time=close_time,
        volume=float(raw.get("volume_fp", 0) or 0),
        open_interest=float(raw.get("open_interest_fp", 0) or 0),
        sport_type=raw.get("_sport_type", ""),
        game_date=_parse_game_date_from_ticker(ticker),
    )


def run_scan(kalshi: KalshiClient, odds: OddsClient, target_date: date | None = None, debug: bool = True, already_bet_tickers: dict[str, str] | None = None) -> list:
    """Execute one full scan cycle. Returns the list of value bets found."""
    ts = datetime.now().strftime("%H:%M:%S")
    date_label = target_date.strftime("%a %b %-d") if target_date else "all upcoming"
    print(f"\n[{ts}] ── Scan  {date_label} ─────────────────────────────────")

    # 1. Fetch Kalshi sports markets
    raw_kalshi = kalshi.get_sports_markets()
    kalshi_markets = [_parse_kalshi_market(m) for m in raw_kalshi]

    # Filter Kalshi markets to the target date using the game date parsed
    # directly from the ticker (e.g. 26MAR14 → 2026-03-14). This is exact
    # and avoids any time-offset heuristics.
    effective_date = target_date or date.today()
    kalshi_markets = [
        km for km in kalshi_markets
        if km.game_date == effective_date
    ]
    # Log per-series breakdown (post-filter) then total
    from collections import Counter
    kalshi_by_series = Counter(
        km.ticker.split("-")[0] for km in kalshi_markets
    )
    from clients.kalshi_client import _SERIES_TO_SPORT
    for series in config.KALSHI_SERIES:
        label = _SERIES_TO_SPORT.get(series, series)
        print(f"[Kalshi] {label}: {kalshi_by_series.get(series, 0) // 2} games.")
    print(f"[Kalshi] {len(kalshi_markets) // 2} games total on {effective_date.strftime('%b %-d')}.")

    # 2. Fetch sportsbook odds — all sharp + live books in one request per sport
    raw_games = odds.get_all_sports_odds()

    # 3. Remove vig → get sharp true probabilities.
    #    Pass now_utc so normalize_all_games picks the right book per game:
    #    Pinnacle for upcoming, DraftKings/FanDuel for in-progress.
    now_utc = datetime.now(timezone.utc)
    all_normalized = normalize_all_games(raw_games, now_utc=now_utc)

    # 4. Filter sportsbook games to the same date
    all_normalized = [
        g for g in all_normalized
        if g.commence_time.astimezone(tz=None).date() == effective_date
    ]

    # Log any in-progress games being handled with live book odds
    live_games = [g for g in all_normalized if g.is_live]
    if live_games:
        by_sport: dict[str, list] = {}
        for g in live_games:
            by_sport.setdefault(g.sport, []).append(g)
        for sport, games in by_sport.items():
            print(f"[OddsAPI] {sport}: {len(games)} game(s) using live odds ({games[0].source_book})")
            for g in games:
                print(f"          🔴 {g.away_team} @ {g.home_team}")

    normalized_games = all_normalized

    # Log per-sport counts (post-date-filter so they sum to the summary total)
    sport_counts = Counter(g.sport for g in normalized_games)
    total_odds = sum(sport_counts.values())
    for sport in config.SPORTS:
        print(f"[OddsAPI] {sport}: {sport_counts.get(sport, 0)} games")
    print(f"[OddsAPI] {total_odds} games total across {len(config.SPORTS)} sports.")

    # 5. Fuzzy-match Kalshi markets to sportsbook games
    matched = match_markets(kalshi_markets, normalized_games, debug=debug)

    # Log per-sport match breakdown
    match_by_sport = Counter(mm.kalshi.sport_type for mm in matched)
    kalshi_by_sport = Counter(km.sport_type for km in kalshi_markets)
    for sport in config.SPORTS:
        k = kalshi_by_sport.get(sport, 0) // 2
        m = match_by_sport.get(sport, 0) // 2
        o = sport_counts.get(sport, 0)
        print(f"[Match]  {sport}: {m} / {k} Kalshi  |  {o} sportsbook")

    # 6. Find value bets
    value_bets = scan_all(matched)

    # 7. Report
    print_summary(len(kalshi_markets), len(normalized_games), len(matched), len(value_bets))
    print_opportunities(value_bets, already_bet_tickers=already_bet_tickers or {})

    return value_bets


def _validate_config() -> None:
    errors = []
    if not config.KALSHI_API_KEY_ID:
        errors.append("KALSHI_API_KEY_ID must be set — generate at kalshi.com/account/profile → API Keys")
    if not config.KALSHI_PRIVATE_KEY_PATH:
        errors.append("KALSHI_PRIVATE_KEY_PATH must be set — path to the .key file downloaded from Kalshi")
    if not config.ODDS_API_KEY:
        errors.append("ODDS_API_KEY must be set in .env")
    if errors:
        for e in errors:
            print(f"[CONFIG ERROR] {e}")
        sys.exit(1)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Kalshi Value Bet Scanner")
    p.add_argument(
        "--date",
        metavar="DATE",
        default=None,
        help="Filter games to this date: 'today', 'tomorrow', or YYYY-MM-DD. "
             "Omit to scan all upcoming games.",
    )
    return p.parse_args()


def _resolve_date(raw: str | None) -> date | None:
    """Parse the --date argument into a date object, or None for 'all upcoming'."""
    if raw is None:
        return None
    today = date.today()
    if raw.lower() == "today":
        return today
    if raw.lower() == "tomorrow":
        return today + timedelta(days=1)
    try:
        return date.fromisoformat(raw)
    except ValueError:
        print(f"[ERROR] --date must be 'today', 'tomorrow', or YYYY-MM-DD (got '{raw}')")
        sys.exit(1)


def main() -> None:
    args = _parse_args()
    target_date = _resolve_date(args.date)
    date_label = target_date.strftime("%a %b %-d, %Y") if target_date else "all upcoming games"

    print("╔══════════════════════════════════════════════════════════")
    print("║          Kalshi Value Bet Scanner                        ")
    print("╠══════════════════════════════════════════════════════════")
    print(f"║  Auth         : RSA key signing")
    print(f"║  Date filter  : {date_label}")
    print(f"║  Pre-game books: {', '.join(config.SHARP_BOOKS)}")
    print(f"║  Live books   : {', '.join(config.LIVE_SHARP_BOOKS)}")
    print(f"║  Sports       : {', '.join(config.SPORTS)}")
    print(f"║  Kalshi series: {', '.join(config.KALSHI_SERIES)}")
    print(f"║  Min edge     : {config.MIN_EDGE * 100:.1f}%")
    print(f"║  Bankroll     : ${config.BANKROLL:,.2f}")
    print(f"║  Kelly mult   : {config.KELLY_FRACTION * 100:.0f}% (fractional)")
    print("╚══════════════════════════════════════════════════════════\n")

    _validate_config()
    init_db()

    kalshi = KalshiClient()
    odds = OddsClient()

    settle_open_bets(kalshi)

    while True:
        already_bet: dict[str, str] = get_active_tickers()
        value_bets = run_scan(kalshi, odds, target_date, already_bet_tickers=already_bet)

        if not value_bets:
            print("  No value bets found. Exiting.")
            break

        while True:
            try:
                raw = input(f'  Enter game number(s) to bet (e.g. "1 3 5"), "s" to rescan, or "b" for bye: ').strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[Scanner] Stopped.")
                return

            if raw.lower() == "b":
                print("  Goodbye!")
                return

            if raw.lower() in ("rescan", "s"):
                break  # re-run scan

            tokens = raw.split()
            game_nums = []
            invalid = False
            for token in tokens:
                try:
                    n = int(token)
                except ValueError:
                    print(f'  Invalid input "{token}" — enter numbers between 1 and {len(value_bets)}, or "bye".')
                    invalid = True
                    break
                if n < 1 or n > len(value_bets):
                    print(f'  Game #{n} not found — enter numbers between 1 and {len(value_bets)}.')
                    invalid = True
                    break
                game_nums.append(n)

            if invalid or not game_nums:
                continue

            print()
            for game_num in game_nums:
                bet = value_bets[game_num - 1]
                ask = bet.kalshi_market.yes_ask if bet.side == "YES" else bet.kalshi_market.no_ask
                print(f"  ⏳  Placing: Buy {bet.side} · {bet.yes_team} — {bet.contracts} contract(s) @ ${ask:.2f} · {bet.kalshi_market.ticker}")
                try:
                    resp = kalshi.place_order(
                        ticker=bet.kalshi_market.ticker,
                        side=bet.side,
                        count=bet.contracts,
                        price_dollars=ask,
                    )
                    order = resp.get("order", {})
                    order_id = order.get("order_id", "unknown")
                    status = order.get("status", "unknown")
                    filled = int(float(order.get("fill_count_fp", "0") or "0"))

                    if filled == bet.contracts:
                        print(f"  ✅  Filled {filled}/{bet.contracts} contracts · order {order_id}")
                    elif filled > 0:
                        print(f"  ⚠️   Partial fill: {filled}/{bet.contracts} contracts · order {order_id}  (status: {status})")
                    else:
                        print(f"  ❌  No fill: 0/{bet.contracts} contracts · order {order_id}  (status: {status})")

                    if filled > 0:
                        record_bet(
                            ticker=bet.kalshi_market.ticker,
                            sport=bet.kalshi_market.sport_type,
                            side=bet.side,
                            team=bet.yes_team,
                            contracts=bet.contracts,
                            fill_count=filled,
                            price=ask,
                            edge=bet.edge,
                            sharp_prob=bet.sharp_true_prob,
                            kalshi_prob=bet.kalshi_implied_prob,
                            game_time=bet.game_time,
                            order_id=order_id,
                        )

                except Exception as exc:
                    print(f"  ❌  Order failed ({bet.kalshi_market.ticker}): {exc}")
            print()
            time.sleep(2)
            break  # re-run scan


if __name__ == "__main__":
    main()
