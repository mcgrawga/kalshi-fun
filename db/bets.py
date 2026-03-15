"""
Bet ledger — SQLite-backed store for every order placed through the scanner.

Schema
------
bets
    id            INTEGER  PK autoincrement
    placed_at     TEXT     ISO-8601 UTC timestamp of when the order was submitted
    ticker        TEXT     Kalshi market ticker
    sport         TEXT     e.g. "icehockey_nhl"
    side          TEXT     "YES" or "NO"
    team          TEXT     Display name (matches Kalshi Action column)
    contracts     INTEGER  Number of contracts requested
    fill_count    INTEGER  Contracts actually filled (0 if no fill)
    price         REAL     Ask price per contract at time of bet (0.0–1.0)
    cost          REAL     fill_count * price  (actual money spent)
    edge          REAL     Edge fraction at time of bet (e.g. 0.037)
    sharp_prob    REAL     Vig-removed sharp probability
    kalshi_prob   REAL     Kalshi ask-implied probability
    game_time     TEXT     ISO-8601 UTC game start time
    order_id      TEXT     Kalshi API order ID (or "unknown")
    outcome       TEXT     NULL=pending, "win", "loss", "push", "void"
    pnl           REAL     NULL=pending; profit/loss in dollars when settled

Database file is stored at DB_PATH (default: <project_root>/bets.db).
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Absolute path to the SQLite file — sits in the project root.
DB_PATH: Path = Path(__file__).resolve().parent.parent / "bets.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS bets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    placed_at   TEXT    NOT NULL,
    ticker      TEXT    NOT NULL,
    sport       TEXT    NOT NULL,
    side        TEXT    NOT NULL,
    team        TEXT    NOT NULL,
    contracts   INTEGER NOT NULL,
    fill_count  INTEGER NOT NULL DEFAULT 0,
    price       REAL    NOT NULL,
    cost        REAL    NOT NULL DEFAULT 0.0,
    edge        REAL    NOT NULL,
    sharp_prob  REAL    NOT NULL,
    kalshi_prob REAL    NOT NULL,
    game_time   TEXT    NOT NULL,
    order_id    TEXT    NOT NULL DEFAULT '',
    outcome     TEXT,
    pnl         REAL
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_bets_ticker ON bets(ticker);
"""


@contextmanager
def _conn():
    """Context manager that yields a sqlite3 connection with WAL mode enabled."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    """Create the database and tables if they don't exist yet."""
    with _conn() as con:
        con.execute(_CREATE_TABLE)
        con.execute(_CREATE_INDEX)


def record_bet(
    *,
    ticker: str,
    sport: str,
    side: str,
    team: str,
    contracts: int,
    fill_count: int,
    price: float,
    edge: float,
    sharp_prob: float,
    kalshi_prob: float,
    game_time: datetime,
    order_id: str,
) -> int:
    """
    Insert a new bet record and return its row id.

    cost is computed automatically as fill_count * price.
    outcome and pnl are left NULL (pending settlement).
    """
    placed_at = datetime.now(timezone.utc).isoformat()
    cost = round(fill_count * price, 4)
    with _conn() as con:
        cur = con.execute(
            """
            INSERT INTO bets
                (placed_at, ticker, sport, side, team, contracts, fill_count,
                 price, cost, edge, sharp_prob, kalshi_prob, game_time, order_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                placed_at,
                ticker,
                sport,
                side,
                team,
                contracts,
                fill_count,
                round(price, 4),
                cost,
                round(edge, 6),
                round(sharp_prob, 6),
                round(kalshi_prob, 6),
                game_time.isoformat(),
                order_id,
            ),
        )
        return cur.lastrowid


def game_key(ticker: str) -> str:
    """
    Return the game-level key for a ticker by stripping the trailing team segment.

    e.g. "KXNBAGAME-26MAR15DETTOR-TOR" → "KXNBAGAME-26MAR15DETTOR"
         "KXNBAGAME-26MAR15DETTOR-DET" → "KXNBAGAME-26MAR15DETTOR"

    Both YES and NO contracts for the same game share the same game_key,
    so we can detect when either side of a game has already been bet.
    """
    return ticker.rsplit("-", 1)[0]


def get_active_tickers(since_hours: int = 36) -> dict[str, str]:
    """
    Return a dict mapping game_key -> full ticker for bets placed within
    the last `since_hours` hours with at least one contract filled.

    Callers can tell whether a given market is the same side (ticker matches)
    or the opposite side (game_key matches but ticker differs).
    """
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    with _conn() as con:
        rows = con.execute(
            "SELECT ticker FROM bets WHERE placed_at >= ? AND fill_count > 0",
            (cutoff.isoformat(),),
        ).fetchall()
    return {game_key(row["ticker"]): row["ticker"] for row in rows}


def settle_bet(bet_id: int, outcome: str, pnl: float) -> None:
    """
    Update the outcome and P&L for a settled bet.

    outcome: "win", "loss", "push", or "void"
    pnl:     profit/loss in dollars (positive = profit, negative = loss)
    """
    with _conn() as con:
        con.execute(
            "UPDATE bets SET outcome = ?, pnl = ? WHERE id = ?",
            (outcome, round(pnl, 4), bet_id),
        )


def all_bets() -> list[sqlite3.Row]:
    """Return all bet rows ordered by placed_at descending."""
    with _conn() as con:
        return con.execute(
            "SELECT * FROM bets ORDER BY placed_at DESC"
        ).fetchall()
