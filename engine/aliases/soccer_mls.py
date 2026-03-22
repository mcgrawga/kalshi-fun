"""
MLS (Major League Soccer) team alias table.

Maps every reasonable variant of an MLS team name → the canonical form used
by The Odds API. Keys must be lowercase. Values must match The Odds API
exactly.

Kalshi titles use shortened names (e.g. "New York City", "Miami", "Salt Lake")
while The Odds API typically uses the full club name (e.g. "New York City FC",
"Inter Miami CF", "Real Salt Lake").

Run `python main.py --date <date> --debug` to find missing entries.
"""

ALIASES: dict[str, str] = {
    # ── Atlanta United FC ─────────────────────────────────────────────────────
    "atlanta united fc": "Atlanta United",
    "atlanta united": "Atlanta United",
    "atlanta": "Atlanta United",
    "atl": "Atlanta United",
    # ── Austin FC ─────────────────────────────────────────────────────────────
    "austin fc": "Austin FC",
    "austin": "Austin FC",
    "atx": "Austin FC",
    # ── Charlotte FC ──────────────────────────────────────────────────────────
    "charlotte fc": "Charlotte FC",
    "charlotte": "Charlotte FC",
    "clt": "Charlotte FC",
    # ── Chicago Fire FC ───────────────────────────────────────────────────────
    "chicago fire fc": "Chicago Fire",
    "chicago fire": "Chicago Fire",
    "chicago": "Chicago Fire",
    "chi": "Chicago Fire",
    # ── FC Cincinnati ─────────────────────────────────────────────────────────
    "fc cincinnati": "FC Cincinnati",
    "cincinnati": "FC Cincinnati",
    "cin": "FC Cincinnati",
    "fcc": "FC Cincinnati",
    # ── Colorado Rapids ───────────────────────────────────────────────────────
    "colorado rapids": "Colorado Rapids",
    "colorado": "Colorado Rapids",
    "col": "Colorado Rapids",
    # ── Columbus Crew ─────────────────────────────────────────────────────────
    "columbus crew": "Columbus Crew",
    "columbus": "Columbus Crew",
    "clb": "Columbus Crew",
    # ── D.C. United ───────────────────────────────────────────────────────────
    "d.c. united": "DC United",
    "dc united": "DC United",
    "d.c.": "DC United",
    "dc": "DC United",
    "dcu": "DC United",
    # ── FC Dallas ─────────────────────────────────────────────────────────────
    "fc dallas": "FC Dallas",
    "dallas": "FC Dallas",
    "dal": "FC Dallas",
    "fcd": "FC Dallas",
    # ── Houston Dynamo FC ─────────────────────────────────────────────────────
    "houston dynamo fc": "Houston Dynamo",
    "houston dynamo": "Houston Dynamo",
    "houston": "Houston Dynamo",
    "hou": "Houston Dynamo",
    # ── Inter Miami CF ────────────────────────────────────────────────────────
    "inter miami cf": "Inter Miami CF",
    "inter miami": "Inter Miami CF",
    "miami": "Inter Miami CF",
    "mia": "Inter Miami CF",
    # ── LA Galaxy ─────────────────────────────────────────────────────────────
    "la galaxy": "LA Galaxy",
    "los angeles galaxy": "LA Galaxy",
    "los angeles g": "LA Galaxy",
    "galaxy": "LA Galaxy",
    "lag": "LA Galaxy",
    # ── Los Angeles FC (LAFC) ─────────────────────────────────────────────────
    "los angeles fc": "Los Angeles FC",
    "los angeles f": "Los Angeles FC",
    "lafc": "Los Angeles FC",
    "laf": "Los Angeles FC",
    # ── Minnesota United FC ───────────────────────────────────────────────────
    "minnesota united fc": "Minnesota United",
    "minnesota united": "Minnesota United",
    "minnesota": "Minnesota United",
    "min": "Minnesota United",
    # ── CF Montréal ───────────────────────────────────────────────────────────
    "cf montréal": "CF Montréal",
    "cf montreal": "CF Montréal",
    "montréal": "CF Montréal",
    "montreal": "CF Montréal",
    "mtl": "CF Montréal",
    # ── Nashville SC ──────────────────────────────────────────────────────────
    "nashville sc": "Nashville SC",
    "nashville": "Nashville SC",
    "nsh": "Nashville SC",
    # ── New England Revolution ────────────────────────────────────────────────
    "new england revolution": "New England Revolution",
    "new england": "New England Revolution",
    "ne revolution": "New England Revolution",
    "revolution": "New England Revolution",
    "ner": "New England Revolution",
    # ── New York City FC ──────────────────────────────────────────────────────
    "new york city fc": "New York City FC",
    "new york city": "New York City FC",
    "nycfc": "New York City FC",
    "nyc": "New York City FC",
    # ── New York Red Bulls ────────────────────────────────────────────────────
    "new york red bulls": "New York Red Bulls",
    "ny red bulls": "New York Red Bulls",
    "red bulls": "New York Red Bulls",
    "nyrb": "New York Red Bulls",
    "rbny": "New York Red Bulls",
    # ── Orlando City SC ───────────────────────────────────────────────────────
    "orlando city sc": "Orlando City",
    "orlando city": "Orlando City",
    "orlando": "Orlando City",
    "orl": "Orlando City",
    # ── Philadelphia Union ────────────────────────────────────────────────────
    "philadelphia union": "Philadelphia Union",
    "philadelphia": "Philadelphia Union",
    "philly union": "Philadelphia Union",
    "phi": "Philadelphia Union",
    # ── Portland Timbers ──────────────────────────────────────────────────────
    "portland timbers": "Portland Timbers",
    "portland": "Portland Timbers",
    "timbers": "Portland Timbers",
    "por": "Portland Timbers",
    # ── Real Salt Lake ────────────────────────────────────────────────────────
    "real salt lake": "Real Salt Lake",
    "salt lake": "Real Salt Lake",
    "rsl": "Real Salt Lake",
    # ── San Diego FC ──────────────────────────────────────────────────────────
    "san diego fc": "San Diego FC",
    "san diego": "San Diego FC",
    "sdfc": "San Diego FC",
    "sd": "San Diego FC",
    # ── San Jose Earthquakes ──────────────────────────────────────────────────
    "san jose earthquakes": "San Jose Earthquakes",
    "san jose": "San Jose Earthquakes",
    "earthquakes": "San Jose Earthquakes",
    "sje": "San Jose Earthquakes",
    # ── Seattle Sounders FC ───────────────────────────────────────────────────
    "seattle sounders fc": "Seattle Sounders",
    "seattle sounders": "Seattle Sounders",
    "seattle": "Seattle Sounders",
    "sounders": "Seattle Sounders",
    "sea": "Seattle Sounders",
    # ── Sporting Kansas City ──────────────────────────────────────────────────
    "sporting kansas city": "Sporting Kansas City",
    "sporting kc": "Sporting Kansas City",
    "kansas city": "Sporting Kansas City",
    "skc": "Sporting Kansas City",
    # ── St. Louis City SC ─────────────────────────────────────────────────────
    "st. louis city sc": "St Louis City",
    "st louis city sc": "St Louis City",
    "st. louis city": "St Louis City",
    "st louis city": "St Louis City",
    "st. louis": "St Louis City",
    "st louis": "St Louis City",
    "stl": "St Louis City",
    # ── Toronto FC ────────────────────────────────────────────────────────────
    "toronto fc": "Toronto FC",
    "toronto": "Toronto FC",
    "tor": "Toronto FC",
    "tfc": "Toronto FC",
    # ── Vancouver Whitecaps FC ────────────────────────────────────────────────
    "vancouver whitecaps fc": "Vancouver Whitecaps",
    "vancouver whitecaps": "Vancouver Whitecaps",
    "vancouver": "Vancouver Whitecaps",
    "whitecaps": "Vancouver Whitecaps",
    "van": "Vancouver Whitecaps",
}
