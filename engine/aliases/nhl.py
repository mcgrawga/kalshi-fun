"""
NHL team alias table.

Maps every reasonable variant of a team name → the canonical form used by
The Odds API. Keys must be lowercase. Values are title-cased canonical strings.

Two layers per team:
    1. Nickname / short form  (e.g. "bruins", "leafs")
    2. Full "City Nickname" form (e.g. "boston bruins")
    3. City-only / Kalshi truncated form (e.g. "boston")

Run `python main.py --date <date> --debug` to find missing entries.
"""

ALIASES: dict[str, str] = {
    # ── Bruins ───────────────────────────────────────────────────────────────
    "bruins": "Boston Bruins",
    "boston bruins": "Boston Bruins",
    "boston": "Boston Bruins",
    # ── Sabres ───────────────────────────────────────────────────────────────
    "sabres": "Buffalo Sabres",
    "buffalo sabres": "Buffalo Sabres",
    "buffalo": "Buffalo Sabres",
    # ── Red Wings ────────────────────────────────────────────────────────────
    "red wings": "Detroit Red Wings",
    "detroit red wings": "Detroit Red Wings",
    "detroit": "Detroit Red Wings",
    # ── Panthers ─────────────────────────────────────────────────────────────
    "florida panthers": "Florida Panthers",
    "florida": "Florida Panthers",
    # ── Canadiens ────────────────────────────────────────────────────────────
    "canadiens": "Montreal Canadiens",
    "habs": "Montreal Canadiens",
    "montreal canadiens": "Montreal Canadiens",
    "montreal": "Montreal Canadiens",
    # ── Senators ─────────────────────────────────────────────────────────────
    "senators": "Ottawa Senators",
    "sens": "Ottawa Senators",
    "ottawa senators": "Ottawa Senators",
    "ottawa": "Ottawa Senators",
    # ── Penguins ─────────────────────────────────────────────────────────────
    "penguins": "Pittsburgh Penguins",
    "pittsburgh penguins": "Pittsburgh Penguins",
    "pittsburgh": "Pittsburgh Penguins",
    # ── Lightning ────────────────────────────────────────────────────────────
    "lightning": "Tampa Bay Lightning",
    "tampa bay lightning": "Tampa Bay Lightning",
    "tampa bay": "Tampa Bay Lightning",
    # ── Capitals ─────────────────────────────────────────────────────────────
    "capitals": "Washington Capitals",
    "caps": "Washington Capitals",
    "washington capitals": "Washington Capitals",
    "washington": "Washington Capitals",
    # ── Hurricanes ───────────────────────────────────────────────────────────
    "hurricanes": "Carolina Hurricanes",
    "canes": "Carolina Hurricanes",
    "carolina hurricanes": "Carolina Hurricanes",
    "carolina": "Carolina Hurricanes",
    # ── Blue Jackets ─────────────────────────────────────────────────────────
    "blue jackets": "Columbus Blue Jackets",
    "cbj": "Columbus Blue Jackets",
    "columbus blue jackets": "Columbus Blue Jackets",
    "columbus": "Columbus Blue Jackets",
    # ── Devils ───────────────────────────────────────────────────────────────
    "devils": "New Jersey Devils",
    "new jersey devils": "New Jersey Devils",
    "new jersey": "New Jersey Devils",
    # ── Islanders ────────────────────────────────────────────────────────────
    "islanders": "New York Islanders",
    "ny islanders": "New York Islanders",
    "new york islanders": "New York Islanders",
    "new york i": "New York Islanders",
    # ── Rangers ──────────────────────────────────────────────────────────────
    "ny rangers": "New York Rangers",
    "new york rangers": "New York Rangers",
    "new york r": "New York Rangers",
    "new york": "New York Rangers",   # default NHL NY team
    # ── Flyers ───────────────────────────────────────────────────────────────
    "flyers": "Philadelphia Flyers",
    "philadelphia flyers": "Philadelphia Flyers",
    "philadelphia": "Philadelphia Flyers",
    # ── Penguins duplicate omitted ────────────────────────────────────────────
    # ── Blackhawks ───────────────────────────────────────────────────────────
    "blackhawks": "Chicago Blackhawks",
    "chicago blackhawks": "Chicago Blackhawks",
    "chicago": "Chicago Blackhawks",
    # ── Avalanche ────────────────────────────────────────────────────────────
    "avalanche": "Colorado Avalanche",
    "avs": "Colorado Avalanche",
    "colorado avalanche": "Colorado Avalanche",
    "colorado": "Colorado Avalanche",
    # ── Stars ────────────────────────────────────────────────────────────────
    "stars": "Dallas Stars",
    "dallas stars": "Dallas Stars",
    "dallas": "Dallas Stars",
    # ── Wild ─────────────────────────────────────────────────────────────────
    "wild": "Minnesota Wild",
    "minnesota wild": "Minnesota Wild",
    "minnesota": "Minnesota Wild",
    # ── Predators ────────────────────────────────────────────────────────────
    "predators": "Nashville Predators",
    "preds": "Nashville Predators",
    "nashville predators": "Nashville Predators",
    "nashville": "Nashville Predators",
    # ── Blues ────────────────────────────────────────────────────────────────
    "blues": "St. Louis Blues",
    "st. louis blues": "St. Louis Blues",
    "st. louis": "St. Louis Blues",
    # ── Jets ─────────────────────────────────────────────────────────────────
    "jets": "Winnipeg Jets",
    "winnipeg jets": "Winnipeg Jets",
    "winnipeg": "Winnipeg Jets",
    # ── Ducks ────────────────────────────────────────────────────────────────
    "ducks": "Anaheim Ducks",
    "anaheim ducks": "Anaheim Ducks",
    "anaheim": "Anaheim Ducks",
    # ── Flames ───────────────────────────────────────────────────────────────
    "flames": "Calgary Flames",
    "calgary flames": "Calgary Flames",
    "calgary": "Calgary Flames",
    # ── Oilers ───────────────────────────────────────────────────────────────
    "oilers": "Edmonton Oilers",
    "edmonton oilers": "Edmonton Oilers",
    "edmonton": "Edmonton Oilers",
    # ── Kings ────────────────────────────────────────────────────────────────
    "kings": "Los Angeles Kings",
    "la kings": "Los Angeles Kings",
    "los angeles kings": "Los Angeles Kings",
    "los angeles k": "Los Angeles Kings",
    # ── Sharks ───────────────────────────────────────────────────────────────
    "sharks": "San Jose Sharks",
    "san jose sharks": "San Jose Sharks",
    "san jose": "San Jose Sharks",
    # ── Kraken ───────────────────────────────────────────────────────────────
    "kraken": "Seattle Kraken",
    "seattle kraken": "Seattle Kraken",
    "seattle k": "Seattle Kraken",
    "seattle": "Seattle Kraken",
    # ── Canucks ──────────────────────────────────────────────────────────────
    "canucks": "Vancouver Canucks",
    "vancouver canucks": "Vancouver Canucks",
    "vancouver": "Vancouver Canucks",
    # ── Golden Knights ───────────────────────────────────────────────────────
    "golden knights": "Vegas Golden Knights",
    "vgk": "Vegas Golden Knights",
    "vegas golden knights": "Vegas Golden Knights",
    "vegas": "Vegas Golden Knights",
    # ── Maple Leafs ──────────────────────────────────────────────────────────
    "maple leafs": "Toronto Maple Leafs",
    "leafs": "Toronto Maple Leafs",
    "toronto maple leafs": "Toronto Maple Leafs",
    "toronto": "Toronto Maple Leafs",
    # ── Utah Mammoth (expansion) ──────────────────────────────────────────────
    "utah mammoth": "Utah Mammoth",
    "utah": "Utah Mammoth",
    "utah hockey club": "Utah Hockey Club",
    "utah h": "Utah Hockey Club",
    # ── Coyotes (relocated but may still appear in historical data) ───────────
    "coyotes": "Arizona Coyotes",
}
