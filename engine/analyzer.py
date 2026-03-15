"""
Value bet analyzer: computes edge, EV, and Kelly bet sizing.

Key formulas
------------
Kalshi decimal odds:
    If yes_ask = 45 cents, you pay $0.45 to win $1.00
    → decimal odds = 100 / 45 = 2.222

Expected value per $1 wagered:
    EV = P_true × decimal_odds − 1

Full Kelly criterion fraction:
    f* = (P × b − Q) / b   where b = decimal_odds − 1, Q = 1 − P

We apply a fractional Kelly multiplier (e.g. 0.25 = quarter Kelly) to reduce
variance while still sizing proportionally to edge.
"""

from models.market import MatchedMarket, ValueBet
import config


def ev_per_dollar(true_prob: float, decimal_odds: float) -> float:
    """
    Expected profit per $1 wagered.

    A positive value means the bet has positive expected value.
    Example: true_prob=0.52, decimal_odds=2.22 → EV = 0.52×2.22 − 1 = +0.154
    """
    return true_prob * decimal_odds - 1.0


def kelly_fraction(true_prob: float, decimal_odds: float) -> float:
    """
    Full Kelly criterion fraction of bankroll to wager.

    f* = (P × b − Q) / b
    where:
        b = decimal_odds − 1  (net profit per $1 wagered)
        P = true_prob
        Q = 1 − P

    Returns 0 for any situation with non-positive expected value.
    """
    b = decimal_odds - 1.0
    if b <= 0.0:
        return 0.0
    q = 1.0 - true_prob
    return max(0.0, (true_prob * b - q) / b)


def analyze_match(match: MatchedMarket, min_edge: float) -> list[ValueBet]:
    """
    Examine one matched market pair and return any value bets found.

    Checks both YES and NO sides independently. A side is a value bet when:
        sharp_true_prob > kalshi_ask_implied_prob + min_edge

    Args:
        match:     A paired (Kalshi market, sportsbook market).
        min_edge:  Minimum probability edge to flag (e.g. 0.03 = 3%).

    Returns:
        0, 1, or 2 ValueBet objects (one per qualifying side).
    """
    bets: list[ValueBet] = []
    km = match.kalshi
    sm = match.sportsbook

    # Determine which sportsbook probability maps to each Kalshi side
    if match.yes_is_home:
        sharp_yes_prob = sm.home_prob
        sharp_no_prob = sm.away_prob
        yes_team = sm.home_team
        no_team = sm.away_team
    else:
        sharp_yes_prob = sm.away_prob
        sharp_no_prob = sm.home_prob
        yes_team = sm.away_team
        no_team = sm.home_team

    # ── YES side ──────────────────────────────────────────────────────────────
    # Skip if price is at a settlement extreme (≤1¢ or ≥99¢ = already resolved)
    if km.yes_ask > 0.01 and km.yes_ask < 0.99:
        yes_edge = sharp_yes_prob - km.yes_implied_prob
        if yes_edge >= min_edge:
            dec_odds = km.yes_decimal_odds
            fk = kelly_fraction(sharp_yes_prob, dec_odds) * config.KELLY_FRACTION
            n_contracts = max(1, round(fk * config.BANKROLL / km.yes_ask)) if km.yes_ask > 0 else 0
            bets.append(
                ValueBet(
                    kalshi_market=km,
                    sportsbook_market=sm,
                    side="YES",
                    kalshi_implied_prob=km.yes_implied_prob,
                    sharp_true_prob=sharp_yes_prob,
                    edge=yes_edge,
                    decimal_odds=dec_odds,
                    ev_per_dollar=ev_per_dollar(sharp_yes_prob, dec_odds),
                    kelly_fraction=fk,
                    recommended_bet=round(n_contracts * km.yes_ask, 2),
                    matched_team=yes_team,
                    yes_team=yes_team,
                    game_time=sm.commence_time,
                    contracts=n_contracts,
                    below_minimum_bet=(fk * config.BANKROLL < km.yes_ask),
                )
            )

    # ── NO side ───────────────────────────────────────────────────────────────
    # Skip if price is at a settlement extreme (≤1¢ or ≥99¢ = already resolved)
    if km.no_ask > 0.01 and km.no_ask < 0.99:
        no_edge = sharp_no_prob - km.no_implied_prob
        if no_edge >= min_edge:
            dec_odds = km.no_decimal_odds
            fk = kelly_fraction(sharp_no_prob, dec_odds) * config.KELLY_FRACTION
            n_contracts = max(1, round(fk * config.BANKROLL / km.no_ask)) if km.no_ask > 0 else 0
            bets.append(
                ValueBet(
                    kalshi_market=km,
                    sportsbook_market=sm,
                    side="NO",
                    kalshi_implied_prob=km.no_implied_prob,
                    sharp_true_prob=sharp_no_prob,
                    edge=no_edge,
                    decimal_odds=dec_odds,
                    ev_per_dollar=ev_per_dollar(sharp_no_prob, dec_odds),
                    kelly_fraction=fk,
                    recommended_bet=round(n_contracts * km.no_ask, 2),
                    matched_team=no_team,
                    yes_team=yes_team,
                    game_time=sm.commence_time,
                    contracts=n_contracts,
                    below_minimum_bet=(fk * config.BANKROLL < km.no_ask),
                )
            )

    return bets


def scan_all(matches: list[MatchedMarket]) -> list[ValueBet]:
    """
    Scan all matched market pairs for value bets.

    Returns results sorted by edge descending (highest edge = best value first).
    """
    all_bets: list[ValueBet] = []
    # MIN_EDGE == 0.0 is treated as "show everything" — use -inf so even
    # negative edges pass the threshold.
    threshold = -float("inf") if config.MIN_EDGE == 0.0 else config.MIN_EDGE
    for match in matches:
        all_bets.extend(analyze_match(match, threshold))

    # Deduplicate: buying YES on Team A and NO on Team B for the same game are
    # the same economic bet (both pay out if Team A wins). Keep the cheaper one
    # (lower ask price = same $1 payout for less money = better value).
    seen: dict[tuple, ValueBet] = {}
    for bet in all_bets:
        sm = bet.sportsbook_market
        # Key = (game identity, which team wins)
        key = (sm.home_team, sm.away_team, sm.commence_time, bet.matched_team)
        if key not in seen:
            seen[key] = bet
        else:
            # Keep whichever contract costs less (lower ask = better deal)
            existing = seen[key]
            existing_ask = (existing.kalshi_market.yes_ask if existing.side == "YES"
                            else existing.kalshi_market.no_ask)
            this_ask = (bet.kalshi_market.yes_ask if bet.side == "YES"
                        else bet.kalshi_market.no_ask)
            if this_ask < existing_ask:
                seen[key] = bet

    return sorted(seen.values(), key=lambda b: b.edge, reverse=True)
