"""
MLB (Major League Baseball) team alias table.

Maps every reasonable variant of an MLB team name → the canonical form used
by The Odds API. Keys must be lowercase. Values must match The Odds API
exactly.

Kalshi titles use shortened names (e.g. "New York Y", "Los Angeles D",
"Chicago C") while The Odds API uses full names (e.g. "New York Yankees",
"Los Angeles Dodgers", "Chicago Cubs").

Run `python main.py --date <date> --debug` to find missing entries.
"""

ALIASES: dict[str, str] = {
    # ── Arizona Diamondbacks ──────────────────────────────────────────────────
    "arizona diamondbacks": "Arizona Diamondbacks",
    "arizona": "Arizona Diamondbacks",
    "diamondbacks": "Arizona Diamondbacks",
    "d-backs": "Arizona Diamondbacks",
    "az": "Arizona Diamondbacks",
    # ── Atlanta Braves ────────────────────────────────────────────────────────
    "atlanta braves": "Atlanta Braves",
    "atlanta": "Atlanta Braves",
    "braves": "Atlanta Braves",
    "atl": "Atlanta Braves",
    # ── Baltimore Orioles ─────────────────────────────────────────────────────
    "baltimore orioles": "Baltimore Orioles",
    "baltimore": "Baltimore Orioles",
    "orioles": "Baltimore Orioles",
    "bal": "Baltimore Orioles",
    # ── Boston Red Sox ────────────────────────────────────────────────────────
    "boston red sox": "Boston Red Sox",
    "boston": "Boston Red Sox",
    "red sox": "Boston Red Sox",
    "bos": "Boston Red Sox",
    # ── Chicago Cubs ──────────────────────────────────────────────────────────
    "chicago cubs": "Chicago Cubs",
    "chicago c": "Chicago Cubs",
    "cubs": "Chicago Cubs",
    "chc": "Chicago Cubs",
    # ── Chicago White Sox ─────────────────────────────────────────────────────
    "chicago white sox": "Chicago White Sox",
    "chicago w": "Chicago White Sox",
    "chicago ws": "Chicago White Sox",
    "white sox": "Chicago White Sox",
    "chw": "Chicago White Sox",
    # ── Cincinnati Reds ───────────────────────────────────────────────────────
    "cincinnati reds": "Cincinnati Reds",
    "cincinnati": "Cincinnati Reds",
    "reds": "Cincinnati Reds",
    "cin": "Cincinnati Reds",
    # ── Cleveland Guardians ───────────────────────────────────────────────────
    "cleveland guardians": "Cleveland Guardians",
    "cleveland": "Cleveland Guardians",
    "guardians": "Cleveland Guardians",
    "cle": "Cleveland Guardians",
    # ── Colorado Rockies ──────────────────────────────────────────────────────
    "colorado rockies": "Colorado Rockies",
    "colorado": "Colorado Rockies",
    "rockies": "Colorado Rockies",
    "col": "Colorado Rockies",
    # ── Detroit Tigers ────────────────────────────────────────────────────────
    "detroit tigers": "Detroit Tigers",
    "detroit": "Detroit Tigers",
    "tigers": "Detroit Tigers",
    "det": "Detroit Tigers",
    # ── Houston Astros ────────────────────────────────────────────────────────
    "houston astros": "Houston Astros",
    "houston": "Houston Astros",
    "astros": "Houston Astros",
    "hou": "Houston Astros",
    # ── Kansas City Royals ────────────────────────────────────────────────────
    "kansas city royals": "Kansas City Royals",
    "kansas city": "Kansas City Royals",
    "royals": "Kansas City Royals",
    "kc": "Kansas City Royals",
    # ── Los Angeles Angels ────────────────────────────────────────────────────
    "los angeles angels": "Los Angeles Angels",
    "los angeles a": "Los Angeles Angels",
    "la angels": "Los Angeles Angels",
    "angels": "Los Angeles Angels",
    "laa": "Los Angeles Angels",
    # ── Los Angeles Dodgers ───────────────────────────────────────────────────
    "los angeles dodgers": "Los Angeles Dodgers",
    "los angeles d": "Los Angeles Dodgers",
    "la dodgers": "Los Angeles Dodgers",
    "dodgers": "Los Angeles Dodgers",
    "lad": "Los Angeles Dodgers",
    # ── Miami Marlins ─────────────────────────────────────────────────────────
    "miami marlins": "Miami Marlins",
    "miami": "Miami Marlins",
    "marlins": "Miami Marlins",
    "mia": "Miami Marlins",
    # ── Milwaukee Brewers ─────────────────────────────────────────────────────
    "milwaukee brewers": "Milwaukee Brewers",
    "milwaukee": "Milwaukee Brewers",
    "brewers": "Milwaukee Brewers",
    "mil": "Milwaukee Brewers",
    # ── Minnesota Twins ───────────────────────────────────────────────────────
    "minnesota twins": "Minnesota Twins",
    "minnesota": "Minnesota Twins",
    "twins": "Minnesota Twins",
    "min": "Minnesota Twins",
    # ── New York Mets ─────────────────────────────────────────────────────────
    "new york mets": "New York Mets",
    "new york m": "New York Mets",
    "ny mets": "New York Mets",
    "mets": "New York Mets",
    "nym": "New York Mets",
    # ── New York Yankees ──────────────────────────────────────────────────────
    "new york yankees": "New York Yankees",
    "new york y": "New York Yankees",
    "ny yankees": "New York Yankees",
    "yankees": "New York Yankees",
    "nyy": "New York Yankees",
    # ── Oakland Athletics / Athletics ─────────────────────────────────────────
    "oakland athletics": "Athletics",
    "athletics": "Athletics",
    "a's": "Athletics",
    "ath": "Athletics",
    "oakland": "Athletics",
    # ── Philadelphia Phillies ─────────────────────────────────────────────────
    "philadelphia phillies": "Philadelphia Phillies",
    "philadelphia": "Philadelphia Phillies",
    "phillies": "Philadelphia Phillies",
    "phi": "Philadelphia Phillies",
    # ── Pittsburgh Pirates ────────────────────────────────────────────────────
    "pittsburgh pirates": "Pittsburgh Pirates",
    "pittsburgh": "Pittsburgh Pirates",
    "pirates": "Pittsburgh Pirates",
    "pit": "Pittsburgh Pirates",
    # ── San Diego Padres ──────────────────────────────────────────────────────
    "san diego padres": "San Diego Padres",
    "san diego": "San Diego Padres",
    "padres": "San Diego Padres",
    "sd": "San Diego Padres",
    # ── San Francisco Giants ──────────────────────────────────────────────────
    "san francisco giants": "San Francisco Giants",
    "san francisco": "San Francisco Giants",
    "giants": "San Francisco Giants",
    "sf": "San Francisco Giants",
    # ── Seattle Mariners ──────────────────────────────────────────────────────
    "seattle mariners": "Seattle Mariners",
    "seattle": "Seattle Mariners",
    "mariners": "Seattle Mariners",
    "sea": "Seattle Mariners",
    # ── St. Louis Cardinals ───────────────────────────────────────────────────
    "st. louis cardinals": "St. Louis Cardinals",
    "st louis cardinals": "St. Louis Cardinals",
    "st. louis": "St. Louis Cardinals",
    "st louis": "St. Louis Cardinals",
    "cardinals": "St. Louis Cardinals",
    "stl": "St. Louis Cardinals",
    # ── Tampa Bay Rays ────────────────────────────────────────────────────────
    "tampa bay rays": "Tampa Bay Rays",
    "tampa bay": "Tampa Bay Rays",
    "rays": "Tampa Bay Rays",
    "tb": "Tampa Bay Rays",
    # ── Texas Rangers ─────────────────────────────────────────────────────────
    "texas rangers": "Texas Rangers",
    "texas": "Texas Rangers",
    "rangers": "Texas Rangers",
    "tex": "Texas Rangers",
    # ── Toronto Blue Jays ─────────────────────────────────────────────────────
    "toronto blue jays": "Toronto Blue Jays",
    "toronto": "Toronto Blue Jays",
    "blue jays": "Toronto Blue Jays",
    "tor": "Toronto Blue Jays",
    # ── Washington Nationals ──────────────────────────────────────────────────
    "washington nationals": "Washington Nationals",
    "washington": "Washington Nationals",
    "nationals": "Washington Nationals",
    "wsh": "Washington Nationals",
    "was": "Washington Nationals",
}
