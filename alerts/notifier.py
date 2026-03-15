from tabulate import tabulate
from datetime import datetime, timezone
from models.market import ValueBet
from db.bets import game_key

# ANSI color codes
_RED    = "\033[31m"
_GREEN  = "\033[32m"
_DIM    = "\033[2m"
_RESET  = "\033[0m"


def _red(text: str) -> str:
    return f"{_RED}{text}{_RESET}"


def _strike(text: str) -> str:
    return f"{_DIM}{text}{_RESET}"



def _pct(p: float) -> str:
    return f"{p * 100:.1f}%"


def _ev(ev: float) -> str:
    sign = "+" if ev >= 0 else ""
    return f"{sign}{ev * 100:.2f}¢/$"


def print_opportunities(bets: list[ValueBet], already_bet_tickers: dict[str, str] | None = None) -> None:
    """Pretty-print all value bets to stdout in a formatted table."""
    already_bet_tickers = already_bet_tickers or {}
    if not bets:
        print("\n  No value bets found above the minimum edge threshold.\n")
        return

    print(f"\n{'═' * 90}")
    print(f"  🎯  VALUE BETS FOUND: {len(bets)}")
    print(f"{'═' * 90}")

    rows = []
    live_row_indices: set[int] = set()
    bet_row_indices: set[int] = set()
    below_min_count = 0
    now_utc = datetime.now(timezone.utc)
    for i, b in enumerate(bets):
        # Convert UTC game time to local time for display
        local_time = b.game_time.astimezone(tz=None)
        tz_abbr = local_time.strftime("%Z")
        live_tag = ""
        if b.sportsbook_market.is_live:
            live_row_indices.add(i)
        gk = game_key(b.kalshi_market.ticker)
        if gk in already_bet_tickers:
            bet_row_indices.add(i)
        flag = " ⚠" if b.below_minimum_bet else ""
        below_min_count += int(b.below_minimum_bet)
        if gk in already_bet_tickers:
            if already_bet_tickers[gk] == b.kalshi_market.ticker:
                already_tag = f" {_GREEN}⬅{_RESET}"   # already bet this side
            else:
                already_tag = f" {_GREEN}⮕{_RESET}"   # already bet the other side
        else:
            already_tag = ""
        action = f"Buy {b.side} · {b.yes_team}{already_tag}"
        _SPORT_LABELS: dict[str, str] = {
            "basketball_nba": "NBA",
            "basketball_ncaab": "NCAAB",
            "basketball_wncaab": "NCAAW",
            "icehockey_nhl": "NHL",
            "rugbyleague_nrl": "NRL",
        }
        sport_label = _SPORT_LABELS.get(
            b.sportsbook_market.sport,
            b.sportsbook_market.sport.replace("_", " ").title(),
        )
        rows.append([
            sport_label,
            _pct(b.sharp_true_prob),
            _pct(b.kalshi_implied_prob),
            f"{b.edge * 100:+.1f}%",
            i + 1,
            action,
            f"{b.contracts}",
            f"${b.recommended_bet:.2f}{flag}",
            _ev(b.ev_per_dollar),
            b.kalshi_market.ticker,
            local_time.strftime(f"%m/%d %I:%M %p {tz_abbr}") + live_tag,
        ])

    headers = [
        "Sport", "Sharp Prob", "Kalshi Prob", "Edge", "Game #",
        "Kalshi Action", "Contracts", "Bet Size", "EV/$1", "Ticker", "Game Time",
    ]

    table = tabulate(rows, headers=headers, tablefmt="rounded_outline")

    # Colorize data rows: dim every odd row, red for live games (live takes priority).
    lines = table.splitlines()
    # lines[0]=top border, lines[1]=headers, lines[2]=header separator
    # lines[3..3+n-1]=data rows, lines[-1]=bottom border
    data_start = 3
    for idx in range(len(bets)):
        line_num = data_start + idx
        if line_num >= len(lines):
            break
        if idx in live_row_indices:
            lines[line_num] = _red(lines[line_num])
    table = "\n".join(lines)

    print(table)
    if below_min_count:
        print(f"  ⚠  {below_min_count} bet(s) marked above: Kelly size < 1 contract cost. You'd be betting 1 contract (the minimum).")
    print()


def print_summary(
    n_kalshi: int,
    n_odds: int,
    n_matched: int,
    n_bets: int,
) -> None:
    """Print a one-line scan summary."""
    print(
        f"  Kalshi games:   {n_kalshi // 2:>4}  |  "
        f"Sportsbook games: {n_odds:>4}  |  "
        f"Matched: {n_matched // 2:>4}  |  "
        f"Value bets: {n_bets:>3}"
    )
