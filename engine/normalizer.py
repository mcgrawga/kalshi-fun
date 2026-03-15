"""
Odds normalizer: converts raw sportsbook data to vig-removed true probabilities.

Key math
--------
American odds → raw implied probability (includes the book's vig):
    negative odds (e.g. -110):  P = |odds| / (|odds| + 100)
    positive odds (e.g. +150):  P = 100   / (odds  + 100)

Vig removal via multiplicative method:
    overround = P_home + P_away           # > 1.0 because of vig
    P_home_true = P_home / overround
    P_away_true = P_away / overround

This preserves the relative weight of each side while forcing them to sum to 1.
"""

from datetime import datetime
from typing import Optional

from models.market import NormalizedOddsMarket


def american_to_implied(odds: float) -> float:
    """
    Convert American odds to raw implied probability (with vig baked in).

    Examples:
        -110  →  0.5238  (52.38%)
        +150  →  0.4000  (40.00%)
        -300  →  0.7500  (75.00%)
        +300  →  0.2500  (25.00%)
    """
    if odds < 0:
        return abs(odds) / (abs(odds) + 100.0)
    else:
        return 100.0 / (odds + 100.0)


def remove_vig_multiplicative(
    prob_a: float, prob_b: float
) -> tuple[float, float]:
    """
    Remove sportsbook vig using the multiplicative (proportional) method.

    Both inputs are raw implied probabilities that sum to > 1 due to vig.
    Returns (true_prob_a, true_prob_b) which sum to exactly 1.0.
    """
    overround = prob_a + prob_b
    return prob_a / overround, prob_b / overround


def vig_percentage(prob_a: float, prob_b: float) -> float:
    """Return the book's vig as a percentage (e.g. 0.048 = 4.8%)."""
    return (prob_a + prob_b) - 1.0


def normalize_game(
    game: dict,
    bookmaker_key: str,
    is_live: bool = False,
) -> Optional[NormalizedOddsMarket]:
    """
    Parse a single raw game dict from The Odds API response into a
    NormalizedOddsMarket with vig-removed probabilities.

    Args:
        game:          Raw game dict from The Odds API.
        bookmaker_key: Which bookmaker's odds to use (e.g. "pinnacle").

    Returns:
        NormalizedOddsMarket, or None if the bookmaker or h2h market is absent.
    """
    # ── Find the target bookmaker ────────────────────────────────────────────
    target_bm = next(
        (bm for bm in game.get("bookmakers", []) if bm["key"] == bookmaker_key),
        None,
    )
    if target_bm is None:
        return None

    # ── Find h2h (moneyline) market ──────────────────────────────────────────
    h2h = next(
        (mkt for mkt in target_bm.get("markets", []) if mkt["key"] == "h2h"),
        None,
    )
    if h2h is None or len(h2h.get("outcomes", [])) < 2:
        return None

    outcomes = h2h["outcomes"]
    home_team_name = game.get("home_team", "")
    away_team_name = game.get("away_team", "")

    # Match outcomes to home/away by team name
    home_odds: Optional[float] = None
    away_odds: Optional[float] = None
    for outcome in outcomes:
        if outcome["name"] == home_team_name:
            home_odds = float(outcome["price"])
        elif outcome["name"] == away_team_name:
            away_odds = float(outcome["price"])

    # Fallback: assign by position if names don't exactly match
    if home_odds is None or away_odds is None:
        if len(outcomes) >= 2:
            home_odds = float(outcomes[0]["price"])
            away_odds = float(outcomes[1]["price"])
            home_team_name = outcomes[0]["name"]
            away_team_name = outcomes[1]["name"]
        else:
            return None

    raw_home_prob = american_to_implied(home_odds)
    raw_away_prob = american_to_implied(away_odds)
    home_prob, away_prob = remove_vig_multiplicative(raw_home_prob, raw_away_prob)

    commence_time = datetime.fromisoformat(
        game["commence_time"].replace("Z", "+00:00")
    )

    return NormalizedOddsMarket(
        sport=game.get("sport_key", ""),
        home_team=home_team_name,
        away_team=away_team_name,
        commence_time=commence_time,
        home_prob=home_prob,
        away_prob=away_prob,
        source_book=bookmaker_key,
        raw_home_odds=home_odds,
        raw_away_odds=away_odds,
        event_id=game.get("id", ""),
        is_live=is_live,
    )


def normalize_all_games(
    games: list[dict],
    books: Optional[list[str]] = None,
    is_live: bool = False,
    now_utc: Optional[datetime] = None,
) -> list[NormalizedOddsMarket]:
    """
    Normalize all games from The Odds API, picking the right bookmaker per game.

    When now_utc is provided, games that have already started use
    config.LIVE_SHARP_BOOKS priority (DraftKings, FanDuel) since Pinnacle
    doesn't offer live in-game odds. Upcoming games use config.SHARP_BOOKS
    (Pinnacle first). Both sets of odds are already present in the raw response
    from get_all_sports_odds() — no second API call is needed.

    Args:
        games:    Raw game dicts from The Odds API.
        books:    Override book priority for all games (ignores now_utc logic).
        is_live:  Force-tag all results as live.
        now_utc:  Current UTC time for pre-game vs live detection.

    Skips games where no configured book has odds.
    """
    import config

    results: list[NormalizedOddsMarket] = []
    for game in games:
        commence_time = datetime.fromisoformat(
            game.get("commence_time", "").replace("Z", "+00:00")
        )
        game_is_live = now_utc is not None and commence_time <= now_utc

        if books is not None:
            book_priority = books
        elif game_is_live:
            book_priority = config.LIVE_SHARP_BOOKS
        else:
            sport_key = game.get("sport_key", "")
            book_priority = config.SPORT_SHARP_BOOKS.get(sport_key, config.SHARP_BOOKS)

        for book in book_priority:
            market = normalize_game(game, book, is_live=game_is_live or is_live)
            if market is not None:
                results.append(market)
                break

    return results
