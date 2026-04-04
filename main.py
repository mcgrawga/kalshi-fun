"""
Kalshi Value Bet Scanner
========================
Polls Kalshi and The Odds API, normalizes odds to vig-removed probabilities,
fuzzy-matches markets across the two platforms, and flags Kalshi markets where
the sharp book's implied probability exceeds Kalshi's ask-implied probability
by at least MIN_EDGE.  Always scans today's games.

Usage
-----
    python main.py                        # scan today's games
    python main.py --auto-bet             # scan and auto-bet qualifying games
    python main.py --auto-bet-loop-minutes 5  # auto-bet loop, rescan every 5 min
    python main.py --auto-bet-loop-minutes 5 --run-time-minutes 60  # loop for 1 hour then exit
"""

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import config
from clients.kalshi_client import KalshiClient
from clients.odds_client import OddsClient
from engine.normalizer import normalize_all_games
from engine.matcher import match_markets
from engine.analyzer import scan_all
from alerts.notifier import print_opportunities, print_summary, print_open_bets
from models.market import KalshiMarket
from db.bets import init_db, record_bet, get_active_tickers, get_open_bets, record_skipped_bet
from engine.settler import settle_open_bets, settle_skipped_bets


_TICKER_DATE_RE = re.compile(r'-(\d{2})([A-Z]{3})(\d{2})[A-Z0-9]', re.IGNORECASE)
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


def run_scan(kalshi: KalshiClient, odds: OddsClient, debug: bool = True, already_bet_tickers: dict[str, str] | None = None, auto_bet: bool = False, auto_loop: bool = False) -> tuple[list, list]:
    """Execute one full scan cycle for today's games. Returns (value_bets, matched_markets)."""
    ts = datetime.now().strftime("%H:%M:%S")
    effective_date = date.today()
    date_label = effective_date.strftime("%a %b %-d")
    print(f"\n[{ts}] ── Scan  {date_label} ─────────────────────────────────")

    # 1. Fetch Kalshi sports markets
    raw_kalshi = kalshi.get_sports_markets()
    kalshi_markets = [_parse_kalshi_market(m) for m in raw_kalshi]

    # Filter Kalshi markets to today using the game date parsed
    # directly from the ticker (e.g. 26MAR14 → 2026-03-14). This is exact
    # and avoids any time-offset heuristics.
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
    #    Pass the target date so the free /events pre-check can skip sports
    #    with zero games, saving paid quota credits.
    raw_games = odds.get_all_sports_odds(target_date=effective_date)

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
    matched = match_markets(kalshi_markets, normalized_games, debug=debug, auto_loop=auto_loop)

    # Log per-sport match breakdown
    match_by_sport = Counter(mm.kalshi.sport_type for mm in matched)
    kalshi_by_sport = Counter(km.sport_type for km in kalshi_markets)
    for sport in config.SPORTS:
        k = kalshi_by_sport.get(sport, 0) // 2
        m = match_by_sport.get(sport, 0) // 2
        o = sport_counts.get(sport, 0)
        print(f"[Match]  {sport}: {m} / {k} Kalshi  |  {o} sportsbook")

    # 6. Fetch live bankroll
    try:
        bankroll = kalshi.get_balance()
        run_scan._last_bankroll = bankroll
    except Exception as exc:
        bankroll = getattr(run_scan, "_last_bankroll", 0.0)
        print(f"[Kalshi] ⚠ balance fetch failed ({exc}), using ${bankroll:.2f}")

    # 7. Find value bets
    value_bets = scan_all(matched, bankroll=bankroll)

    # 8. Report
    print_summary(len(kalshi_markets), len(normalized_games), len(matched), len(value_bets), bankroll=bankroll)
    if auto_bet:
        print(f"  [Auto-Bet] ENABLED  |  min edge: {config.AUTO_BET_MIN_EDGE * 100:.1f}%  |  min price: {config.AUTO_BET_MIN_PRICE*100:.0f}¢  |  sport filters: {len(config.SPORT_STRATEGY)} sport(s)")
    open_bets = get_open_bets()
    print_open_bets(open_bets)
    print_opportunities(value_bets, already_bet_tickers=already_bet_tickers or {})

    return value_bets, matched


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
    p = argparse.ArgumentParser(
        description=(
            "Kalshi Value Bet Scanner — finds mispriced moneyline markets on Kalshi\n"
            "by comparing implied probabilities against vig-removed sharp sportsbook odds.\n"
            "Thresholds and bankroll settings are configured in config.py."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python main.py                        scan today's games\n"
            "  python main.py --auto-bet             scan and auto-bet qualifying games\n"
            "  python main.py --auto-bet-loop-minutes 5  auto-bet loop, rescan every 5 min\n"
            "  python main.py --auto-bet-loop-minutes 5 --run-time-minutes 60  loop for 1 hour\n"
            "\n"
            "interactive prompt (after scan):\n"
            "  1 3 5   place bets on games #1, #3, and #5\n"
            "  r       rescan (re-fetches odds and Kalshi prices)\n"
            "  b       exit\n"
        ),
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--auto-bet",
        action="store_true",
        default=False,
        help=(
            "Automatically place bets on value bets where edge >= AUTO_BET_MIN_EDGE "
            "and passing SPORT_STRATEGY filters (both set in config.py). "
            "Games already in the bet ledger are always skipped. "
            "The table and manual prompt still appear after auto-bets are placed."
        ),
    )
    mode.add_argument(
        "--auto-bet-loop-minutes",
        type=int,
        metavar="MINUTES",
        default=None,
        help=(
            "Run in continuous unattended loop mode. Automatically places bets using the "
            "same AUTO_BET_MIN_EDGE and SPORT_STRATEGY thresholds as --auto-bet, "
            "then waits MINUTES before rescanning. No prompt is shown — a countdown "
            "displays instead. Press Ctrl+C to stop. Cannot be combined with --auto-bet."
        ),
    )
    p.add_argument(
        "--manage-mappings",
        action="store_true",
        default=False,
        help=(
            "Review and manage team-name mappings. Runs one scan, then shows all "
            "mapping entries per sport and lets you add/remove entries interactively. "
            "No bets are placed in this mode."
        ),
    )
    p.add_argument(
        "--run-time-minutes",
        type=int,
        metavar="MINUTES",
        default=None,
        help=(
            "Maximum total minutes the app should run before exiting. "
            "Only valid with --auto-bet-loop-minutes. The app finishes its "
            "current scan iteration, then exits if the deadline has passed."
        ),
    )
    return p.parse_args()



def _countdown(seconds: int) -> None:
    """Print a live countdown in M:SS format on a single overwriting line."""
    try:
        for remaining in range(seconds, 0, -1):
            mins, secs = divmod(remaining, 60)
            print(f"  ⏱  Next scan in {mins}:{secs:02d}...  ", end="\r", flush=True)
            time.sleep(1)
        print(" " * 40, end="\r", flush=True)  # clear the line
    except KeyboardInterrupt:
        print(" " * 40, end="\r", flush=True)
        raise


def _place_bet(kalshi: KalshiClient, bet) -> None:
    """Place a single order for `bet` and record it in the DB if filled."""
    ask = bet.kalshi_market.yes_ask if bet.side == "YES" else bet.kalshi_market.no_ask
    sm = bet.sportsbook_market
    opponent = sm.away_team if bet.yes_team == sm.home_team else sm.home_team
    bankroll_before = kalshi.get_balance()
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
                opponent=opponent,
                contracts=bet.contracts,
                fill_count=filled,
                price=ask,
                edge=bet.edge,
                sharp_prob=bet.sharp_true_prob,
                kalshi_prob=bet.kalshi_implied_prob,
                game_time=bet.game_time,
                order_id=order_id,
                bankroll_at_bet=bankroll_before,
            )

    except Exception as exc:
        print(f"  ❌  Order failed ({bet.kalshi_market.ticker}): {exc}")


def _check_sport_strategy(bet) -> str | None:
    """Check per-sport strategy filters. Returns a skip reason string, or None if the bet passes."""
    rules = config.SPORT_STRATEGY.get(bet.kalshi_market.sport_type)
    if not rules:
        return None  # no sport-specific rules → allow

    allowed_sides = rules.get("sides")
    if allowed_sides and bet.side not in allowed_sides:
        return f"side {bet.side} blocked (allowed: {', '.join(allowed_sides)})"

    min_sharp = rules.get("min_sharp", 0.0)
    if bet.sharp_true_prob < min_sharp:
        return f"sharp {bet.sharp_true_prob*100:.1f}% < min {min_sharp*100:.0f}%"

    max_sharp = rules.get("max_sharp", 1.0)
    if bet.sharp_true_prob > max_sharp:
        return f"sharp {bet.sharp_true_prob*100:.1f}% > max {max_sharp*100:.0f}%"

    return None


def _auto_bet(kalshi: KalshiClient, value_bets: list, already_bet_tickers: dict[str, str]) -> int:
    """
    Automatically place bets on qualifying value bets.

    A bet qualifies when ALL of the following are true:
        bet.edge            >= config.AUTO_BET_MIN_EDGE
        contract price      >= config.AUTO_BET_MIN_PRICE
        passes per-sport SPORT_STRATEGY filters
        game not already in the bet ledger (checked via already_bet_tickers)

    Bets that pass the global filters but fail the sport strategy filter are
    recorded in the skipped_bets table for later analysis.

    After each placement the bankroll is refreshed from the API and value bets
    are re-sized via scan_all so subsequent bets use the updated cash balance.

    Returns the number of bets placed.
    """
    from db.bets import game_key
    placed = 0
    for bet in value_bets:
        gk = game_key(bet.kalshi_market.ticker)
        if gk in already_bet_tickers:
            continue
        if bet.edge < config.AUTO_BET_MIN_EDGE:
            continue
        ask = bet.kalshi_market.yes_ask if bet.side == "YES" else bet.kalshi_market.no_ask
        if ask < config.AUTO_BET_MIN_PRICE:
            sm = bet.sportsbook_market
            opponent = sm.away_team if bet.yes_team == sm.home_team else sm.home_team
            reason = f"price {ask*100:.0f}\u00a2 < min {config.AUTO_BET_MIN_PRICE*100:.0f}\u00a2"
            record_skipped_bet(
                ticker=bet.kalshi_market.ticker,
                sport=bet.kalshi_market.sport_type,
                side=bet.side,
                team=bet.yes_team,
                opponent=opponent,
                price=ask,
                edge=bet.edge,
                sharp_prob=bet.sharp_true_prob,
                kalshi_prob=bet.kalshi_implied_prob,
                game_time=bet.game_time,
                reason=reason,
            )
            print(f"  [Auto-Bet] SKIP  {bet.side} · {bet.yes_team} — {reason}")
            continue

        # Per-sport strategy filter
        skip_reason = _check_sport_strategy(bet)
        if skip_reason:
            sm = bet.sportsbook_market
            opponent = sm.away_team if bet.yes_team == sm.home_team else sm.home_team
            record_skipped_bet(
                ticker=bet.kalshi_market.ticker,
                sport=bet.kalshi_market.sport_type,
                side=bet.side,
                team=bet.yes_team,
                opponent=opponent,
                price=bet.kalshi_market.yes_ask if bet.side == "YES" else bet.kalshi_market.no_ask,
                edge=bet.edge,
                sharp_prob=bet.sharp_true_prob,
                kalshi_prob=bet.kalshi_implied_prob,
                game_time=bet.game_time,
                reason=skip_reason,
            )
            print(f"  [Auto-Bet] SKIP  {bet.side} · {bet.yes_team} — {skip_reason}")
            continue

        print(f"  [Auto-Bet] Edge {bet.edge * 100:.1f}% · Kalshi {bet.kalshi_implied_prob * 100:.1f}% · Sharp {bet.sharp_true_prob * 100:.1f}% — qualifying bet:")
        _place_bet(kalshi, bet)
        placed += 1
        # Mark this game as bet so we don't bet the other side in the same pass
        already_bet_tickers[gk] = bet.kalshi_market.ticker
    return placed


def _manage_mappings_mode() -> None:
    """
    Interactive mode for reviewing and managing team-name mappings.

    Shows all mapping entries per sport, allows adding/removing entries,
    and displays stats on mapping coverage.
    """
    from engine.mappings import get_all_mappings, save_mapping, reload
    from engine.mappings import _SPORT_FILES, _DIR
    import json

    _SPORT_LABELS = {
        "basketball_nba": "NBA",
        "icehockey_nhl": "NHL",
        "basketball_ncaab": "NCAAB",
        "basketball_wncaab": "NCAAW",
        "rugbyleague_nrl": "NRL",
        "soccer_usa_mls": "MLS",
        "baseball_mlb": "MLB",
    }

    print("\n╔══════════════════════════════════════════════════════════")
    print("║          Team Name Mapping Manager                       ")
    print("╚══════════════════════════════════════════════════════════\n")

    # Show summary
    for sport, fname in _SPORT_FILES.items():
        mappings = get_all_mappings(sport)
        label = _SPORT_LABELS.get(sport, sport)
        print(f"  {label:<8} {len(mappings):>4} mappings  ({fname})")
    print()

    while True:
        print("  Commands:")
        print("    [1-7] View mappings for a sport (1=NBA 2=NHL 3=NCAAB 4=NCAAW 5=NRL 6=MLS 7=MLB)")
        print("    [a]   Add a mapping")
        print("    [d]   Delete a mapping")
        print("    [s]   Search mappings")
        print("    [q]   Quit")

        try:
            cmd = input("\n  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            return

        if cmd == "q":
            return

        sports_list = list(_SPORT_FILES.keys())
        sport_labels_list = [_SPORT_LABELS.get(s, s) for s in sports_list]

        if cmd in ("1", "2", "3", "4", "5", "6", "7"):
            idx = int(cmd) - 1
            if idx >= len(sports_list):
                continue
            sport = sports_list[idx]
            label = sport_labels_list[idx]
            mappings = get_all_mappings(sport)
            print(f"\n  ── {label} Mappings ({len(mappings)} entries) ──")
            for key_lower, odds_name in sorted(mappings.items()):
                kalshi_display = key_lower.title()
                if kalshi_display.lower() == odds_name.lower():
                    print(f"    {kalshi_display:<40} = {odds_name}")
                else:
                    print(f"    {kalshi_display:<40} → {odds_name}")
            print()

        elif cmd == "a":
            print("\n  Add a new mapping:")
            sport_str = input("    Sport (1=NBA 2=NHL 3=NCAAB 4=NCAAW 5=NRL 6=MLS 7=MLB): ").strip()
            try:
                sport = sports_list[int(sport_str) - 1]
            except (ValueError, IndexError):
                print("    Invalid sport.")
                continue
            kalshi_name = input("    Kalshi team name: ").strip()
            odds_name = input("    Odds API team name: ").strip()
            if kalshi_name and odds_name:
                save_mapping(sport, kalshi_name, odds_name)
                print(f"    ✅ Saved: '{kalshi_name}' → '{odds_name}' ({_SPORT_LABELS.get(sport, sport)})")
            else:
                print("    Cancelled.")

        elif cmd == "d":
            print("\n  Delete a mapping:")
            sport_str = input("    Sport (1=NBA 2=NHL 3=NCAAB 4=NCAAW 5=NRL 6=MLS 7=MLB): ").strip()
            try:
                sport = sports_list[int(sport_str) - 1]
            except (ValueError, IndexError):
                print("    Invalid sport.")
                continue
            kalshi_name = input("    Kalshi team name to remove: ").strip()
            # Remove from JSON file directly
            fname = _SPORT_FILES.get(sport)
            if fname:
                fpath = _DIR / fname
                if fpath.exists():
                    with open(fpath) as f:
                        data = json.load(f)
                    # Find and remove (case-insensitive key search)
                    removed = None
                    for k in list(data.keys()):
                        if k.lower() == kalshi_name.lower():
                            removed = k
                            del data[k]
                            break
                    if removed:
                        with open(fpath, "w") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                            f.write("\n")
                        reload()
                        print(f"    ✅ Removed '{removed}' from {_SPORT_LABELS.get(sport, sport)}")
                    else:
                        print(f"    Not found.")

        elif cmd == "s":
            query = input("    Search: ").strip().lower()
            if not query:
                continue
            print()
            for sport in sports_list:
                label = _SPORT_LABELS.get(sport, sport)
                mappings = get_all_mappings(sport)
                for key_lower, odds_name in sorted(mappings.items()):
                    if query in key_lower or query in odds_name.lower():
                        print(f"    [{label}] {key_lower.title():<40} → {odds_name}")
            print()


def main() -> None:
    args = _parse_args()
    today = date.today()
    date_label = today.strftime("%a %b %-d, %Y")

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
    print(f"║  Kelly mult   : {config.KELLY_FRACTION * 100:.0f}% (fractional)")
    if args.auto_bet:
        print(f"║  Auto-bet     : ON  (edge ≥ {config.AUTO_BET_MIN_EDGE * 100:.1f}%,  min price: {config.AUTO_BET_MIN_PRICE*100:.0f}¢,  sport filters: {len(config.SPORT_STRATEGY)})")
    if args.auto_bet_loop_minutes is not None:
        print(f"║  Auto-bet loop: ON  (edge ≥ {config.AUTO_BET_MIN_EDGE * 100:.1f}%,  min price: {config.AUTO_BET_MIN_PRICE*100:.0f}¢,  sport filters: {len(config.SPORT_STRATEGY)},  interval: {args.auto_bet_loop_minutes}m)")

    # ── Run-time cap setup ─────────────────────────────────────────────
    _CST = ZoneInfo("America/Chicago")
    start_time = time.monotonic()
    start_dt = datetime.now(_CST)
    deadline_dt = None
    if args.run_time_minutes is not None:
        if args.auto_bet_loop_minutes is None:
            print("[ERROR] --run-time-minutes requires --auto-bet-loop-minutes")
            sys.exit(1)
        deadline_dt = start_dt + timedelta(minutes=args.run_time_minutes)

    print("╚══════════════════════════════════════════════════════════\n")

    _validate_config()
    init_db()

    kalshi = KalshiClient()
    odds = OddsClient()

    if args.manage_mappings:
        _manage_mappings_mode()
        return

    # In loop mode, auto_bet behaviour is always active
    do_auto_bet = args.auto_bet or (args.auto_bet_loop_minutes is not None)
    is_loop = args.auto_bet_loop_minutes is not None

    schedule_info = (start_dt, deadline_dt, args.run_time_minutes, _CST) if deadline_dt is not None else None

    while True:
        settle_open_bets(kalshi)
        settle_skipped_bets(kalshi)
        already_bet: dict[str, str] = get_active_tickers()
        value_bets, matched = run_scan(kalshi, odds, already_bet_tickers=already_bet, auto_bet=do_auto_bet, auto_loop=is_loop)

        # Auto-bet qualifying rows before showing the table
        if do_auto_bet and value_bets:
            n_placed = _auto_bet(kalshi, value_bets, already_bet)
            if n_placed:
                time.sleep(1)
                # Re-render the table with green arrows on the just-placed rows
                # instead of a full rescan (saves 7 paid quota credits).
                already_bet = get_active_tickers()
                print_opportunities(value_bets, already_bet_tickers=already_bet)

        # ── Loop mode: countdown then rescan, no prompt ────────────────────
        if args.auto_bet_loop_minutes is not None:
            if not value_bets:
                print("  No value bets found.")
            # Check run-time deadline before sleeping
            if deadline_dt is not None:
                elapsed = time.monotonic() - start_time
                if elapsed >= args.run_time_minutes * 60:
                    now_ct = datetime.now(_CST).strftime('%I:%M %p CT')
                    print(f"\n  ⏰  Run-time limit reached ({args.run_time_minutes}m). Exiting at {now_ct}.")
                    return
            if schedule_info is not None:
                _start_dt, _deadline_dt, _run_minutes, _cst = schedule_info
                _now_ct = datetime.now(_cst)
                print(f"  \U0001F550  Started: {_start_dt.strftime('%I:%M %p CT')}  |  Now: {_now_ct.strftime('%I:%M %p CT')}  |  Ends: {_deadline_dt.strftime('%I:%M %p CT')}  ({_run_minutes}m)")
            _countdown(args.auto_bet_loop_minutes * 60)
            continue

        # ── Interactive mode ───────────────────────────────────────────────
        if not value_bets:
            print("  No value bets found.")

        while True:
            try:
                raw = input(f'  Enter "r" to rescan or "b" for bye: ').strip() if not value_bets else input(f'  Enter game number(s) to bet (e.g. "1 3 5"), "r" to rescan, or "b" for bye: ').strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[Scanner] Stopped.")
                return

            if raw.lower() == "b":
                print("  Goodbye!")
                return

            if raw.lower() in ("rescan", "r"):
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
                _place_bet(kalshi, value_bets[game_num - 1])
            print()
            time.sleep(2)
            break  # re-run scan


if __name__ == "__main__":
    main()
