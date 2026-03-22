"""
NRL (National Rugby League) team alias table.

Maps every reasonable variant of a team name → the canonical form used by
The Odds API. Keys must be lowercase. Values match Odds API exactly.

The Odds API uses hyphenated club names (e.g. "Canterbury-Bankstown Bulldogs")
while Kalshi titles use the short form ("Canterbury Bulldogs"). Both forms are
mapped here.

Run `python main.py --date <date> --debug` to find missing entries.
"""

ALIASES: dict[str, str] = {
    # ── Brisbane Broncos ──────────────────────────────────────────────────────
    "brisbane broncos": "Brisbane Broncos",
    "broncos": "Brisbane Broncos",
    "brisbane": "Brisbane Broncos",
    # ── Canberra Raiders ──────────────────────────────────────────────────────
    "canberra raiders": "Canberra Raiders",
    "raiders": "Canberra Raiders",
    "canberra": "Canberra Raiders",
    # ── Canterbury Bulldogs ───────────────────────────────────────────────────
    "canterbury bulldogs": "Canterbury Bulldogs",
    "canterbury-bankstown bulldogs": "Canterbury Bulldogs",
    "bulldogs": "Canterbury Bulldogs",
    "canterbury": "Canterbury Bulldogs",
    # ── Cronulla Sharks ───────────────────────────────────────────────────────
    "cronulla sharks": "Cronulla Sharks",
    "cronulla-sutherland sharks": "Cronulla Sharks",
    "sharks": "Cronulla Sharks",
    "cronulla": "Cronulla Sharks",
    # ── Dolphins ─────────────────────────────────────────────────────────────
    "dolphins": "Dolphins",
    "brisbane dolphins": "Dolphins",
    # ── Gold Coast Titans ─────────────────────────────────────────────────────
    "gold coast titans": "Gold Coast Titans",
    "titans": "Gold Coast Titans",
    "gold coast": "Gold Coast Titans",
    # ── Manly Sea Eagles ──────────────────────────────────────────────────────
    "manly sea eagles": "Manly Sea Eagles",
    "manly-warringah sea eagles": "Manly Sea Eagles",
    "sea eagles": "Manly Sea Eagles",
    "manly": "Manly Sea Eagles",
    # ── Melbourne Storm ───────────────────────────────────────────────────────
    "melbourne storm": "Melbourne Storm",
    "storm": "Melbourne Storm",
    "melbourne": "Melbourne Storm",
    # ── Newcastle Knights ─────────────────────────────────────────────────────
    "newcastle knights": "Newcastle Knights",
    "knights": "Newcastle Knights",
    "newcastle": "Newcastle Knights",
    # ── New Zealand Warriors ──────────────────────────────────────────────────
    "new zealand warriors": "New Zealand Warriors",
    "warriors": "New Zealand Warriors",
    "nz warriors": "New Zealand Warriors",
    # ── North Queensland Cowboys ──────────────────────────────────────────────
    "north queensland cowboys": "North Queensland Cowboys",
    "cowboys": "North Queensland Cowboys",
    "north queensland": "North Queensland Cowboys",
    "nq cowboys": "North Queensland Cowboys",
    # ── Parramatta Eels ───────────────────────────────────────────────────────
    "parramatta eels": "Parramatta Eels",
    "eels": "Parramatta Eels",
    "parramatta": "Parramatta Eels",
    # ── Penrith Panthers ──────────────────────────────────────────────────────
    "penrith panthers": "Penrith Panthers",
    "panthers": "Penrith Panthers",
    "penrith": "Penrith Panthers",
    # ── South Sydney Rabbitohs ────────────────────────────────────────────────
    "south sydney rabbitohs": "South Sydney Rabbitohs",
    "rabbitohs": "South Sydney Rabbitohs",
    "south sydney": "South Sydney Rabbitohs",
    "souths": "South Sydney Rabbitohs",
    # ── St. George Illawarra Dragons ─────────────────────────────────────────
    "st. george illawarra dragons": "St. George Illawarra Dragons",
    "st george illawarra dragons": "St. George Illawarra Dragons",
    "dragons": "St. George Illawarra Dragons",
    "st george": "St. George Illawarra Dragons",
    # ── Sydney Roosters ───────────────────────────────────────────────────────
    "sydney roosters": "Sydney Roosters",
    "roosters": "Sydney Roosters",
    "sydney": "Sydney Roosters",
    # ── Wests Tigers ──────────────────────────────────────────────────────────
    "wests tigers": "Wests Tigers",
    "tigers": "Wests Tigers",
    "wests": "Wests Tigers",
}
