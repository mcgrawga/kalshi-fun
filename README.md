# Kalshi Value Bet Scanner

A CLI tool that finds mispriced moneyline markets on [Kalshi](https://kalshi.com) by comparing their implied probabilities against vig-removed sharp sportsbook odds. When Kalshi's price is worse than what the sharp books say the true probability is, it flags a value bet and can place the order automatically via the Kalshi API.

## How It Works

1. **Fetch** — Pulls all active Kalshi sports markets and current odds from [The Odds API](https://the-odds-api.com) for the configured sports.
2. **Normalize** — Strips the vig from sportsbook odds to get sharp true probabilities. Uses Pinnacle (pre-game) or DraftKings/FanDuel (live) as the source of truth.
3. **Match** — Fuzzy-matches Kalshi markets to sportsbook games by team name and game time.
4. **Analyze** — Computes edge (`sharp_prob − kalshi_implied_prob`), EV, and fractional Kelly bet sizing for both YES and NO sides of every matched market.
5. **Report** — Prints a table of value bets above the minimum edge threshold.
6. **Bet** — Optionally places orders directly via the Kalshi API and records them in a local SQLite ledger.

## Supported Sports

| Sport | Kalshi Series |
|---|---|
| NBA | `KXNBAGAME` |
| NCAA Men's Basketball | `KXNCAAMBGAME` |
| NCAA Women's Basketball | `KXNCAAWBGAME` |
| NHL | `KXNHLGAME` |
| NRL (Rugby League) | `KXRUGBYNRLMATCH` |

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API credentials

Set the following environment variables (e.g. in `~/.bash_profile` or a `.env` file):

```bash
# Kalshi — generate at kalshi.com/account/profile → API Keys
export KALSHI_API_KEY_ID="your-key-id"
export KALSHI_PRIVATE_KEY_PATH="/path/to/your/private.key"

# The Odds API — sign up at the-odds-api.com
export ODDS_API_KEY="your-odds-api-key"
```

### 3. Configure settings

Edit [config.py](config.py) to tune the scanner to your preferences:

| Setting | Default | Description |
|---|---|---|
| `MIN_EDGE` | `0.001` | Minimum edge (sharp prob − Kalshi prob) to flag a bet |
| `BANKROLL` | `27.74` | Total bankroll in dollars for Kelly sizing |
| `KELLY_FRACTION` | `0.25` | Fractional Kelly multiplier (0.25 = quarter Kelly) |
| `POLL_INTERVAL_SECONDS` | `60` | Seconds between re-scans |
| `MIN_VOLUME` | `0` | Minimum Kalshi market volume to consider |
| `SHARP_BOOKS` | `["pinnacle", "betonlineag"]` | Pre-game books in priority order |
| `LIVE_SHARP_BOOKS` | `["draftkings", "fanduel", "betonlineag"]` | Live books in priority order |

## Usage

```bash
# Scan today's games (default)
python main.py

# Scan tomorrow's games
python main.py --date tomorrow

# Scan a specific date
python main.py --date 2026-03-15
```

When value bets are found, you'll be shown a table and prompted to enter game numbers to place bets. Enter `r` to rescan or `b` to exit.

## Project Structure

```
├── main.py              # Entry point — CLI, scan loop, order placement
├── config.py            # All user-configurable settings
├── requirements.txt
├── clients/
│   ├── kalshi_client.py # Kalshi REST API client (RSA key auth)
│   └── odds_client.py   # The Odds API client
├── engine/
│   ├── normalizer.py    # Vig removal → true probabilities
│   ├── matcher.py       # Fuzzy team-name matching across platforms
│   └── analyzer.py      # Edge, EV, and Kelly sizing calculations
├── models/
│   └── market.py        # Data models (KalshiMarket, ValueBet, etc.)
├── alerts/
│   └── notifier.py      # Console output / bet opportunity tables
└── db/
    └── bets.py          # SQLite bet ledger (bets.db)
```

## Bet Ledger

Every filled order is recorded in `bets.db` (SQLite, auto-created on first run). The schema tracks ticker, side, contracts, fill count, price, edge, sharp prob, Kalshi prob, game time, order ID, outcome, and P&L.

## Kelly Criterion

Bet sizing uses fractional Kelly:

$$f = \frac{P \cdot b - Q}{b} \times \text{Kelly Fraction}$$

where $b$ = decimal odds $- 1$, $P$ = sharp true probability, $Q = 1 - P$.

Quarter Kelly (`KELLY_FRACTION = 0.25`) is recommended to reduce variance while still sizing proportionally to edge.
