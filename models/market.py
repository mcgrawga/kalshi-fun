from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class NormalizedOddsMarket:
    """
    A sportsbook game normalized to vig-removed true probabilities.

    home_prob + away_prob ≈ 1.0 (after vig removal via multiplicative method).
    raw_home_odds / raw_away_odds are the original American odds for reference.
    """

    sport: str
    home_team: str
    away_team: str
    commence_time: datetime
    home_prob: float        # vig-removed true probability for home team
    away_prob: float        # vig-removed true probability for away team
    source_book: str        # e.g. "pinnacle"
    raw_home_odds: float    # original American odds
    raw_away_odds: float
    event_id: str = ""     # The Odds API event ID (used for live odds refetch)
    is_live: bool = False   # True if odds were fetched from the live endpoint


@dataclass
class KalshiMarket:
    """
    A Kalshi binary market representing a single game outcome.

    Prices are in dollars (0.0–1.0). A yes_ask of 0.45 means you pay $0.45
    per contract, which pays $1.00 if YES resolves.
    """

    ticker: str
    title: str
    yes_ask: float          # dollars to buy YES (0.0–1.0)
    no_ask: float           # dollars to buy NO
    yes_bid: float          # dollars sellers offer YES for
    no_bid: float           # dollars sellers offer NO for
    close_time: datetime
    volume: float = 0.0
    open_interest: float = 0.0
    sport_type: str = ""    # e.g. "basketball_nba", "basketball_ncaab", "icehockey_nhl"
    game_date: Optional[date] = None  # parsed from ticker (e.g. 26MAR14 → 2026-03-14)

    @property
    def yes_implied_prob(self) -> float:
        """Kalshi's implied probability of YES resolving (based on ask price)."""
        return self.yes_ask  # already 0.0–1.0

    @property
    def no_implied_prob(self) -> float:
        """Kalshi's implied probability of NO resolving (based on ask price)."""
        return self.no_ask  # already 0.0–1.0

    @property
    def yes_decimal_odds(self) -> float:
        """Decimal payout per $1 wagered on YES: pays $1 / yes_ask."""
        return 1.0 / self.yes_ask if self.yes_ask > 0 else 0.0

    @property
    def no_decimal_odds(self) -> float:
        """Decimal payout per $1 wagered on NO: pays $1 / no_ask."""
        return 1.0 / self.no_ask if self.no_ask > 0 else 0.0


@dataclass
class MatchedMarket:
    """
    A Kalshi market paired with a sportsbook game.

    yes_is_home: if True, betting YES on Kalshi = betting on the home team.
    confidence:  fuzzy match confidence score from 0.0 to 1.0.
    """

    kalshi: KalshiMarket
    sportsbook: NormalizedOddsMarket
    yes_is_home: bool
    confidence: float


@dataclass
class ValueBet:
    """
    A detected value betting opportunity on Kalshi.

    The edge is the difference between the sharp book's vig-removed probability
    and Kalshi's ask-implied probability. A positive edge means Kalshi is
    underpricing this outcome relative to what the sharp market believes.
    """

    kalshi_market: KalshiMarket
    sportsbook_market: NormalizedOddsMarket
    side: str                   # "YES" or "NO"
    kalshi_implied_prob: float  # what Kalshi's ask price implies
    sharp_true_prob: float      # vig-removed probability from sharp book
    edge: float                 # sharp_true_prob - kalshi_implied_prob
    decimal_odds: float         # Kalshi decimal odds for this side
    ev_per_dollar: float        # expected profit per $1 wagered
    kelly_fraction: float       # fractional Kelly bet size (fraction of bankroll)
    recommended_bet: float      # dollar amount = kelly_fraction * bankroll
    matched_team: str           # team that wins if this bet pays out
    yes_team: str               # team the Kalshi YES contract is named after
    game_time: datetime         # when the game starts
    contracts: int              # number of contracts Kelly recommends (recommended_bet / ask_price)
    below_minimum_bet: bool     # True if Kelly size < cost of 1 contract
