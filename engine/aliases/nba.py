"""
NBA team alias table.

Maps every reasonable variant of a team name → the canonical form used by
The Odds API. Keys must be lowercase. Values are title-cased canonical strings.

Two layers per team:
    1. Nickname / short form  (e.g. "lakers", "celtics")
    2. Full "City Nickname" form (e.g. "los angeles lakers")
    3. City-only / Kalshi truncated form (e.g. "los angeles l")
       — only needed when the city is ambiguous across leagues.

Run `python main.py --date <date> --debug` to find missing entries.
"""

ALIASES: dict[str, str] = {
    # ── Celtics ──────────────────────────────────────────────────────────────
    "celtics": "Boston Celtics",
    "boston celtics": "Boston Celtics",
    "boston": "Boston Celtics",
    # ── Nets ─────────────────────────────────────────────────────────────────
    "nets": "Brooklyn Nets",
    "brooklyn nets": "Brooklyn Nets",
    "brooklyn": "Brooklyn Nets",
    # ── Knicks ───────────────────────────────────────────────────────────────
    "knicks": "New York Knicks",
    "new york knicks": "New York Knicks",
    "new york k": "New York Knicks",
    "ny knicks": "New York Knicks",
    # ── 76ers ────────────────────────────────────────────────────────────────
    "76ers": "Philadelphia 76ers",
    "sixers": "Philadelphia 76ers",
    "philadelphia 76ers": "Philadelphia 76ers",
    "philadelphia": "Philadelphia 76ers",
    # ── Raptors ──────────────────────────────────────────────────────────────
    "raptors": "Toronto Raptors",
    "toronto raptors": "Toronto Raptors",
    "toronto": "Toronto Raptors",
    # ── Bulls ────────────────────────────────────────────────────────────────
    "bulls": "Chicago Bulls",
    "chicago bulls": "Chicago Bulls",
    "chicago": "Chicago Bulls",
    # ── Cavaliers ────────────────────────────────────────────────────────────
    "cavaliers": "Cleveland Cavaliers",
    "cavs": "Cleveland Cavaliers",
    "cleveland cavaliers": "Cleveland Cavaliers",
    "cleveland": "Cleveland Cavaliers",
    # ── Pistons ──────────────────────────────────────────────────────────────
    "pistons": "Detroit Pistons",
    "detroit pistons": "Detroit Pistons",
    "detroit": "Detroit Pistons",
    # ── Pacers ───────────────────────────────────────────────────────────────
    "pacers": "Indiana Pacers",
    "indiana pacers": "Indiana Pacers",
    "indiana": "Indiana Pacers",
    # ── Bucks ────────────────────────────────────────────────────────────────
    "bucks": "Milwaukee Bucks",
    "milwaukee bucks": "Milwaukee Bucks",
    "milwaukee": "Milwaukee Bucks",
    # ── Timberwolves ─────────────────────────────────────────────────────────
    "timberwolves": "Minnesota Timberwolves",
    "wolves": "Minnesota Timberwolves",
    "minnesota timberwolves": "Minnesota Timberwolves",
    "minnesota": "Minnesota Timberwolves",
    # ── Pacers ───────────────────────────────────────────────────────────────
    "magic": "Orlando Magic",
    "orlando magic": "Orlando Magic",
    "orlando": "Orlando Magic",
    # ── Wizards ──────────────────────────────────────────────────────────────
    "wizards": "Washington Wizards",
    "washington wizards": "Washington Wizards",
    "washington": "Washington Wizards",
    # ── Hawks ────────────────────────────────────────────────────────────────
    "hawks": "Atlanta Hawks",
    "atlanta hawks": "Atlanta Hawks",
    "atlanta": "Atlanta Hawks",
    # ── Hornets ──────────────────────────────────────────────────────────────
    "hornets": "Charlotte Hornets",
    "charlotte hornets": "Charlotte Hornets",
    "charlotte": "Charlotte Hornets",
    # ── Heat ─────────────────────────────────────────────────────────────────
    "heat": "Miami Heat",
    "miami heat": "Miami Heat",
    "miami": "Miami Heat",
    # ── Pelicans ─────────────────────────────────────────────────────────────
    "pelicans": "New Orleans Pelicans",
    "new orleans pelicans": "New Orleans Pelicans",
    "new orleans": "New Orleans Pelicans",
    # ── Bulls duplicate omitted — listed above ────────────────────────────────
    # ── Nuggets ──────────────────────────────────────────────────────────────
    "nuggets": "Denver Nuggets",
    "denver nuggets": "Denver Nuggets",
    "denver": "Denver Nuggets",
    # ── Thunder ──────────────────────────────────────────────────────────────
    "thunder": "Oklahoma City Thunder",
    "okc thunder": "Oklahoma City Thunder",
    "oklahoma city thunder": "Oklahoma City Thunder",
    "oklahoma city": "Oklahoma City Thunder",
    # bare "oklahoma" intentionally omitted — collides with NCAAB Oklahoma Sooners
    # ── Blazers ──────────────────────────────────────────────────────────────
    "trail blazers": "Portland Trail Blazers",
    "blazers": "Portland Trail Blazers",
    "portland trail blazers": "Portland Trail Blazers",
    "portland": "Portland Trail Blazers",
    # ── Jazz ─────────────────────────────────────────────────────────────────
    "jazz": "Utah Jazz",
    "utah jazz": "Utah Jazz",
    "utah": "Utah Jazz",
    # ── Grizzlies ────────────────────────────────────────────────────────────
    "grizzlies": "Memphis Grizzlies",
    "memphis grizzlies": "Memphis Grizzlies",
    "memphis": "Memphis Grizzlies",
    # ── Spurs ────────────────────────────────────────────────────────────────
    "spurs": "San Antonio Spurs",
    "san antonio spurs": "San Antonio Spurs",
    "san antonio": "San Antonio Spurs",
    # ── Rockets ──────────────────────────────────────────────────────────────
    "rockets": "Houston Rockets",
    "houston rockets": "Houston Rockets",
    "houston": "Houston Rockets",
    # ── Mavericks ────────────────────────────────────────────────────────────
    "mavericks": "Dallas Mavericks",
    "mavs": "Dallas Mavericks",
    "dallas mavericks": "Dallas Mavericks",
    "dallas": "Dallas Mavericks",
    # ── Suns ─────────────────────────────────────────────────────────────────
    "suns": "Phoenix Suns",
    "phoenix suns": "Phoenix Suns",
    "phoenix": "Phoenix Suns",
    # ── Kings ────────────────────────────────────────────────────────────────
    "kings": "Sacramento Kings",
    "sacramento kings": "Sacramento Kings",
    "sacramento": "Sacramento Kings",
    # ── Clippers ─────────────────────────────────────────────────────────────
    "clippers": "Los Angeles Clippers",
    "la clippers": "Los Angeles Clippers",
    "los angeles clippers": "Los Angeles Clippers",
    "los angeles c": "Los Angeles Clippers",
    # ── Lakers ───────────────────────────────────────────────────────────────
    "lakers": "Los Angeles Lakers",
    "los angeles lakers": "Los Angeles Lakers",
    "la lakers": "Los Angeles Lakers",
    "los angeles l": "Los Angeles Lakers",
    # ── Warriors ─────────────────────────────────────────────────────────────
    "warriors": "Golden State Warriors",
    "golden state warriors": "Golden State Warriors",
    "gsw": "Golden State Warriors",
    "golden state": "Golden State Warriors",
}
