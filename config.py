import os

# ─── Kalshi Credentials ───────────────────────────────────────────────────────
# Key ID and private key path are set in your shell environment (e.g. ~/.bash_profile).
# kalshi.com/account/profile → API Keys → Create New API Key
KALSHI_API_KEY_ID: str = os.getenv("KALSHI_API_KEY_ID", "")
KALSHI_PRIVATE_KEY_PATH: str = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")
KALSHI_BASE_URL: str = "https://api.elections.kalshi.com/trade-api/v2"

# ─── The Odds API ─────────────────────────────────────────────────────────────
# Sign up at https://the-odds-api.com — set ODDS_API_KEY in .env
ODDS_API_KEY: str = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE_URL: str = "https://api.the-odds-api.com/v4"

# ─── Sharp Books ──────────────────────────────────────────────────────────────
# Ordered by preference. The scanner uses the first book that has odds for a game.
# Pinnacle is the gold standard; betonlineag is a solid fallback.
# Options: pinnacle, betonlineag, lowvig
SHARP_BOOKS: list[str] = ["pinnacle", "betonlineag"]

# Live books: Pinnacle does not offer live odds via The Odds API.
# DraftKings and FanDuel have the best live coverage; betonlineag is fallback.
LIVE_SHARP_BOOKS: list[str] = ["draftkings", "fanduel", "betonlineag"]

# Per-sport overrides for pre-game book priority.
# Use this for sports Pinnacle doesn't cover (e.g. NCAAW).
# If a sport is not listed here, SHARP_BOOKS is used.
SPORT_SHARP_BOOKS: dict[str, list[str]] = {
    "basketball_wncaab": ["draftkings", "fanduel", "betonlineag"],
}

# ─── Sports ───────────────────────────────────────────────────────────────────
# The Odds API sport keys to monitor.
SPORTS: list[str] = [
    "basketball_nba",
    "basketball_ncaab",
    "basketball_wncaab",
    "icehockey_nhl",
    "rugbyleague_nrl",
    "soccer_usa_mls",
    "baseball_mlb",
]

# Kalshi series tickers for game-level moneyline markets.
# KXNBAGAME       = NBA game winner
# KXNCAAMBGAME    = NCAA Men's Basketball game winner
# KXNCAAWBGAME    = NCAA Women's Basketball game winner
# KXNHLGAME       = NHL game winner
# KXRUGBYNRLMATCH = NRL (National Rugby League) match winner
KALSHI_SERIES: list[str] = ["KXNBAGAME", "KXNCAAMBGAME", "KXNCAAWBGAME", "KXNHLGAME", "KXRUGBYNRLMATCH", "KXMLSGAME", "KXMLBGAME"]

# ─── Value Bet Thresholds ────────────────────────────────────────────────────
# Minimum edge (sharp prob − Kalshi prob) to flag a bet.
# Lower = more alerts but more noise. 0.03–0.05 is a reasonable starting range.
# This just controls what displays in the value bet table. The edge column has to be
# greater than or equal to this threshold to be included in the table and considered a value bet.
MIN_EDGE: float = 0.001

# ─── Bankroll & Sizing ───────────────────────────────────────────────────────
# Bankroll is fetched live from Kalshi's GET /portfolio/balance each scan loop.

# Fractional Kelly multiplier. Full Kelly (1.0) is mathematically optimal but
# volatile. Quarter Kelly (0.25) is more conservative and widely recommended.
KELLY_FRACTION: float = 0.25

# ─── Auto-Bet Thresholds ─────────────────────────────────────────────────────
# When --auto-bet is passed, bets are placed automatically on any value bet where
# BOTH of the following conditions are met:
#   edge             >= AUTO_BET_MIN_EDGE        (the "Edge" column in the table)
#   passes SPORT_STRATEGY filters                (per-sport side/sharp rules)
# Games already in the bet ledger are always skipped.
AUTO_BET_MIN_EDGE: float = 0.02

# Global sharp probability floor for auto-bets.
# 0.60 = only take positions where sharp fair win probability is at least 60%.
AUTO_BET_MIN_SHARP: float = 0.60

# Global edge ceiling for auto-bets.
# High-edge outliers have performed poorly historically; cap to avoid tails.
AUTO_BET_MAX_EDGE: float = 0.05

# Minimum contract price (ask) to auto-bet.  Cheap contracts (longshots or
# games where the outcome is basically decided) have terrible historical ROI.
# 0.40 = skip anything under 40¢.  Set to 0.0 to disable.
AUTO_BET_MIN_PRICE: float = 0.55

# ─── Contrarian / Fade Mode ───────────────────────────────────────────────────
# When True, every auto-bet is flipped to the opposite side. If the analyzer
# finds value on YES, the app buys NO instead (and vice versa). The strategy
# filters (SPORT_STRATEGY) still apply to the *original* signal side — the
# flip happens after all filters pass. Useful for fading the model's picks.
CONTRARIAN_MODE: bool = False

# ─── Per-Sport Strategy Filters ───────────────────────────────────────────────
# Fine-grained auto-bet rules per sport. Each sport key maps to a dict with
# optional filters.  A bet must pass ALL filters to be placed.  Sports not
# listed here have no extra restrictions (only the global filters above apply).
#
# Available keys per sport:
#   sides      — list[str]  Only allow these sides (e.g. ["NO"]).  Default: both.
#   min_sharp  — float      Minimum sharp probability.  Default: 0.0
#   max_sharp  — float      Maximum sharp probability.  Default: 1.0
SPORT_STRATEGY: dict[str, dict] = {
    # "icehockey_nhl":      {"sides": ["NO"], "min_sharp": 0.50},
    # "basketball_nba":     {"sides": ["NO"],  "max_sharp": 0.50},
    # "baseball_mlb":       {"min_sharp": 0.60},
    # "basketball_ncaab":   {"min_sharp": 0.50},
    # "basketball_wncaab":  {"sides": ["YES"], "min_sharp": 0.50},
}

# ─── Liquidity Filter ─────────────────────────────────────────────────────────
# Minimum Kalshi market volume (contracts) to consider a market tradeable.
# Set > 0 to avoid thinly-traded markets where fills at the displayed price are unlikely.
MIN_VOLUME: int = 0
