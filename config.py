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
]

# Kalshi series tickers for game-level moneyline markets.
# KXNBAGAME       = NBA game winner
# KXNCAAMBGAME    = NCAA Men's Basketball game winner
# KXNCAAWBGAME    = NCAA Women's Basketball game winner
# KXNHLGAME       = NHL game winner
# KXRUGBYNRLMATCH = NRL (National Rugby League) match winner
KALSHI_SERIES: list[str] = ["KXNBAGAME", "KXNCAAMBGAME", "KXNCAAWBGAME", "KXNHLGAME", "KXRUGBYNRLMATCH"]

# ─── Value Bet Thresholds ────────────────────────────────────────────────────
# Minimum edge (sharp prob − Kalshi prob) to flag a bet.
# Lower = more alerts but more noise. 0.03–0.05 is a reasonable starting range.
MIN_EDGE: float = 0.001

# ─── Bankroll & Sizing ───────────────────────────────────────────────────────
BANKROLL: float = 24.88

# Fractional Kelly multiplier. Full Kelly (1.0) is mathematically optimal but
# volatile. Quarter Kelly (0.25) is more conservative and widely recommended.
KELLY_FRACTION: float = 0.25

# ─── Auto-Bet Thresholds ─────────────────────────────────────────────────────
# When --auto-bet is passed, bets are placed automatically on any value bet where
# BOTH of the following conditions are met:
#   edge             >= AUTO_BET_MIN_EDGE        (the "Edge" column in the table)
#   kalshi_implied_prob >= AUTO_BET_MIN_KALSHI_PROB (the "Kalshi Prob" column)
# Games already in the bet ledger are always skipped.
AUTO_BET_MIN_EDGE: float = 0.02
AUTO_BET_MIN_KALSHI_PROB: float = 0.09

# ─── Liquidity Filter ─────────────────────────────────────────────────────────
# Minimum Kalshi market volume (contracts) to consider a market tradeable.
# Set > 0 to avoid thinly-traded markets where fills at the displayed price are unlikely.
MIN_VOLUME: int = 0
