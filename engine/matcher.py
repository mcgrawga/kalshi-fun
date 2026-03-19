"""
Market matcher: links Kalshi binary markets to sportsbook game lines.

The core challenge
------------------
Kalshi titles are free-form text:
    "NBA: Will the Los Angeles Lakers beat the Boston Celtics?"

The Odds API returns structured data:
    home_team: "Los Angeles Lakers", away_team: "Boston Celtics"

Strategy
--------
1. Parse the Kalshi title with regex to extract team names and which side is YES.
2. Canonicalize extracted names through the alias table.
3. Fuzzy-match canonical names against sportsbook home/away teams.
4. Filter by game time proximity to avoid cross-week false matches.
"""

import re
from datetime import datetime, timezone
from typing import Optional

from rapidfuzz import fuzz

from models.market import KalshiMarket, MatchedMarket, NormalizedOddsMarket


# ─── Team alias table ─────────────────────────────────────────────────────────
# Maps common aliases / short names → the canonical name as The Odds API uses.

TEAM_ALIASES: dict[str, str] = {
    # ── NBA ──────────────────────────────────────────────────────────────────
    "lakers": "Los Angeles Lakers",
    "los angeles lakers": "Los Angeles Lakers",
    "la lakers": "Los Angeles Lakers",
    "celtics": "Boston Celtics",
    "boston celtics": "Boston Celtics",
    "warriors": "Golden State Warriors",
    "golden state warriors": "Golden State Warriors",
    "gsw": "Golden State Warriors",
    "heat": "Miami Heat",
    "miami heat": "Miami Heat",
    "bulls": "Chicago Bulls",
    "chicago bulls": "Chicago Bulls",
    "knicks": "New York Knicks",
    "new york knicks": "New York Knicks",
    "bucks": "Milwaukee Bucks",
    "milwaukee bucks": "Milwaukee Bucks",
    "nuggets": "Denver Nuggets",
    "denver nuggets": "Denver Nuggets",
    "suns": "Phoenix Suns",
    "phoenix suns": "Phoenix Suns",
    "76ers": "Philadelphia 76ers",
    "sixers": "Philadelphia 76ers",
    "philadelphia 76ers": "Philadelphia 76ers",
    "nets": "Brooklyn Nets",
    "brooklyn nets": "Brooklyn Nets",
    "raptors": "Toronto Raptors",
    "toronto raptors": "Toronto Raptors",
    "clippers": "Los Angeles Clippers",
    "la clippers": "Los Angeles Clippers",
    "los angeles clippers": "Los Angeles Clippers",
    "mavericks": "Dallas Mavericks",
    "mavs": "Dallas Mavericks",
    "dallas mavericks": "Dallas Mavericks",
    "thunder": "Oklahoma City Thunder",
    "okc thunder": "Oklahoma City Thunder",
    "oklahoma city thunder": "Oklahoma City Thunder",
    "spurs": "San Antonio Spurs",
    "san antonio spurs": "San Antonio Spurs",
    "hawks": "Atlanta Hawks",
    "atlanta hawks": "Atlanta Hawks",
    "hornets": "Charlotte Hornets",
    "charlotte hornets": "Charlotte Hornets",
    "cavaliers": "Cleveland Cavaliers",
    "cavs": "Cleveland Cavaliers",
    "cleveland cavaliers": "Cleveland Cavaliers",
    "pistons": "Detroit Pistons",
    "detroit pistons": "Detroit Pistons",
    "pacers": "Indiana Pacers",
    "indiana pacers": "Indiana Pacers",
    "magic": "Orlando Magic",
    "orlando magic": "Orlando Magic",
    "wizards": "Washington Wizards",
    "washington wizards": "Washington Wizards",
    "pelicans": "New Orleans Pelicans",
    "new orleans pelicans": "New Orleans Pelicans",
    "rockets": "Houston Rockets",
    "houston rockets": "Houston Rockets",
    "grizzlies": "Memphis Grizzlies",
    "memphis grizzlies": "Memphis Grizzlies",
    "jazz": "Utah Jazz",
    "utah jazz": "Utah Jazz",
    "kings": "Sacramento Kings",
    "sacramento kings": "Sacramento Kings",
    "timberwolves": "Minnesota Timberwolves",
    "wolves": "Minnesota Timberwolves",
    "minnesota timberwolves": "Minnesota Timberwolves",
    "trail blazers": "Portland Trail Blazers",
    "blazers": "Portland Trail Blazers",
    "portland trail blazers": "Portland Trail Blazers",
    # ── NFL ──────────────────────────────────────────────────────────────────
    "chiefs": "Kansas City Chiefs",
    "kansas city chiefs": "Kansas City Chiefs",
    "eagles": "Philadelphia Eagles",
    "philadelphia eagles": "Philadelphia Eagles",
    "cowboys": "Dallas Cowboys",
    "dallas cowboys": "Dallas Cowboys",
    "patriots": "New England Patriots",
    "new england patriots": "New England Patriots",
    "bills": "Buffalo Bills",
    "buffalo bills": "Buffalo Bills",
    "packers": "Green Bay Packers",
    "green bay packers": "Green Bay Packers",
    "steelers": "Pittsburgh Steelers",
    "pittsburgh steelers": "Pittsburgh Steelers",
    "bears": "Chicago Bears",
    "chicago bears": "Chicago Bears",
    "ravens": "Baltimore Ravens",
    "baltimore ravens": "Baltimore Ravens",
    "broncos": "Denver Broncos",
    "denver broncos": "Denver Broncos",
    "lions": "Detroit Lions",
    "detroit lions": "Detroit Lions",
    "seahawks": "Seattle Seahawks",
    "seattle seahawks": "Seattle Seahawks",
    "49ers": "San Francisco 49ers",
    "niners": "San Francisco 49ers",
    "san francisco 49ers": "San Francisco 49ers",
    "rams": "Los Angeles Rams",
    "la rams": "Los Angeles Rams",
    "los angeles rams": "Los Angeles Rams",
    "chargers": "Los Angeles Chargers",
    "la chargers": "Los Angeles Chargers",
    "los angeles chargers": "Los Angeles Chargers",
    "raiders": "Las Vegas Raiders",
    "las vegas raiders": "Las Vegas Raiders",
    "cardinals": "Arizona Cardinals",
    "arizona cardinals": "Arizona Cardinals",
    "falcons": "Atlanta Falcons",
    "atlanta falcons": "Atlanta Falcons",
    "panthers": "Carolina Panthers",
    "carolina panthers": "Carolina Panthers",
    "saints": "New Orleans Saints",
    "new orleans saints": "New Orleans Saints",
    "buccaneers": "Tampa Bay Buccaneers",
    "bucs": "Tampa Bay Buccaneers",
    "tampa bay buccaneers": "Tampa Bay Buccaneers",
    "vikings": "Minnesota Vikings",
    "minnesota vikings": "Minnesota Vikings",
    "giants": "New York Giants",
    "ny giants": "New York Giants",
    "new york giants": "New York Giants",
    "jets": "New York Jets",
    "ny jets": "New York Jets",
    "new york jets": "New York Jets",
    "dolphins": "Miami Dolphins",
    "miami dolphins": "Miami Dolphins",
    "texans": "Houston Texans",
    "houston texans": "Houston Texans",
    "colts": "Indianapolis Colts",
    "indianapolis colts": "Indianapolis Colts",
    "jaguars": "Jacksonville Jaguars",
    "jacksonville jaguars": "Jacksonville Jaguars",
    "titans": "Tennessee Titans",
    "tennessee titans": "Tennessee Titans",
    "bengals": "Cincinnati Bengals",
    "cincinnati bengals": "Cincinnati Bengals",
    "browns": "Cleveland Browns",
    "cleveland browns": "Cleveland Browns",
    "commanders": "Washington Commanders",
    "washington commanders": "Washington Commanders",
    # ── MLB ──────────────────────────────────────────────────────────────────
    "yankees": "New York Yankees",
    "new york yankees": "New York Yankees",
    "red sox": "Boston Red Sox",
    "boston red sox": "Boston Red Sox",
    "cubs": "Chicago Cubs",
    "chicago cubs": "Chicago Cubs",
    "white sox": "Chicago White Sox",
    "chicago white sox": "Chicago White Sox",
    "dodgers": "Los Angeles Dodgers",
    "la dodgers": "Los Angeles Dodgers",
    "los angeles dodgers": "Los Angeles Dodgers",
    "sf giants": "San Francisco Giants",
    "san francisco giants": "San Francisco Giants",
    "astros": "Houston Astros",
    "houston astros": "Houston Astros",
    "braves": "Atlanta Braves",
    "atlanta braves": "Atlanta Braves",
    "mets": "New York Mets",
    "new york mets": "New York Mets",
    "phillies": "Philadelphia Phillies",
    "philadelphia phillies": "Philadelphia Phillies",
    "blue jays": "Toronto Blue Jays",
    "toronto blue jays": "Toronto Blue Jays",
    "rays": "Tampa Bay Rays",
    "tampa bay rays": "Tampa Bay Rays",
    "orioles": "Baltimore Orioles",
    "baltimore orioles": "Baltimore Orioles",
    "guardians": "Cleveland Guardians",
    "cleveland guardians": "Cleveland Guardians",
    "tigers": "Detroit Tigers",
    "detroit tigers": "Detroit Tigers",
    "royals": "Kansas City Royals",
    "kansas city royals": "Kansas City Royals",
    "twins": "Minnesota Twins",
    "minnesota twins": "Minnesota Twins",
    "brewers": "Milwaukee Brewers",
    "milwaukee brewers": "Milwaukee Brewers",
    "cardinals": "St. Louis Cardinals",
    "st. louis cardinals": "St. Louis Cardinals",
    "reds": "Cincinnati Reds",
    "cincinnati reds": "Cincinnati Reds",
    "pirates": "Pittsburgh Pirates",
    "pittsburgh pirates": "Pittsburgh Pirates",
    "cubs": "Chicago Cubs",
    "padres": "San Diego Padres",
    "san diego padres": "San Diego Padres",
    "rockies": "Colorado Rockies",
    "colorado rockies": "Colorado Rockies",
    "diamondbacks": "Arizona Diamondbacks",
    "dbacks": "Arizona Diamondbacks",
    "arizona diamondbacks": "Arizona Diamondbacks",
    "mariners": "Seattle Mariners",
    "seattle mariners": "Seattle Mariners",
    "angels": "Los Angeles Angels",
    "la angels": "Los Angeles Angels",
    "los angeles angels": "Los Angeles Angels",
    "athletics": "Oakland Athletics",
    "a's": "Oakland Athletics",
    "oakland athletics": "Oakland Athletics",
    "rangers": "Texas Rangers",
    "texas rangers": "Texas Rangers",
    "nationals": "Washington Nationals",
    "washington nationals": "Washington Nationals",
    "marlins": "Miami Marlins",
    "miami marlins": "Miami Marlins",
    # ── NHL ──────────────────────────────────────────────────────────────────
    "bruins": "Boston Bruins",
    "boston bruins": "Boston Bruins",
    "blackhawks": "Chicago Blackhawks",
    "chicago blackhawks": "Chicago Blackhawks",
    "ny rangers": "New York Rangers",
    "new york rangers": "New York Rangers",
    "penguins": "Pittsburgh Penguins",
    "pittsburgh penguins": "Pittsburgh Penguins",
    "maple leafs": "Toronto Maple Leafs",
    "leafs": "Toronto Maple Leafs",
    "toronto maple leafs": "Toronto Maple Leafs",
    "canadiens": "Montreal Canadiens",
    "habs": "Montreal Canadiens",
    "montreal canadiens": "Montreal Canadiens",
    "lightning": "Tampa Bay Lightning",
    "tampa bay lightning": "Tampa Bay Lightning",
    "capitals": "Washington Capitals",
    "caps": "Washington Capitals",
    "washington capitals": "Washington Capitals",
    "golden knights": "Vegas Golden Knights",
    "vgk": "Vegas Golden Knights",
    "vegas golden knights": "Vegas Golden Knights",
    "oilers": "Edmonton Oilers",
    "edmonton oilers": "Edmonton Oilers",
    "flames": "Calgary Flames",
    "calgary flames": "Calgary Flames",
    "canucks": "Vancouver Canucks",
    "vancouver canucks": "Vancouver Canucks",
    "avalanche": "Colorado Avalanche",
    "avs": "Colorado Avalanche",
    "colorado avalanche": "Colorado Avalanche",
    "wild": "Minnesota Wild",
    "minnesota wild": "Minnesota Wild",
    "blues": "St. Louis Blues",
    "st. louis blues": "St. Louis Blues",
    "predators": "Nashville Predators",
    "preds": "Nashville Predators",
    "nashville predators": "Nashville Predators",
    "stars": "Dallas Stars",
    "dallas stars": "Dallas Stars",
    "jets": "Winnipeg Jets",
    "winnipeg jets": "Winnipeg Jets",
    "ducks": "Anaheim Ducks",
    "anaheim ducks": "Anaheim Ducks",
    "kings": "Los Angeles Kings",
    "la kings": "Los Angeles Kings",
    "los angeles kings": "Los Angeles Kings",
    "sharks": "San Jose Sharks",
    "san jose sharks": "San Jose Sharks",
    "senators": "Ottawa Senators",
    "sens": "Ottawa Senators",
    "ottawa senators": "Ottawa Senators",
    "sabres": "Buffalo Sabres",
    "buffalo sabres": "Buffalo Sabres",
    "flyers": "Philadelphia Flyers",
    "philadelphia flyers": "Philadelphia Flyers",
    "devils": "New Jersey Devils",
    "new jersey devils": "New Jersey Devils",
    "islanders": "New York Islanders",
    "ny islanders": "New York Islanders",
    "new york islanders": "New York Islanders",
    "hurricanes": "Carolina Hurricanes",
    "canes": "Carolina Hurricanes",
    "carolina hurricanes": "Carolina Hurricanes",
    "panthers": "Florida Panthers",
    "florida panthers": "Florida Panthers",
    "blue jackets": "Columbus Blue Jackets",
    "cbj": "Columbus Blue Jackets",
    "columbus blue jackets": "Columbus Blue Jackets",
    "coyotes": "Arizona Coyotes",
    "utah hockey club": "Utah Hockey Club",
    # ── Kalshi truncated names (as they appear in market titles) ─────────────
    # NBA — city/state only forms (e.g. "Boston at Oklahoma City Winner?")
    # Note: Cities shared between NBA and NHL (e.g. "Minnesota", "Colorado",
    # "Carolina", "Florida", "Pittsburgh", "Columbus") are intentionally
    # OMITTED here. They fall back to title-cased form and rely on the sport
    # isolation filter + fuzzy matching to resolve correctly.
    "boston": "Boston Celtics",
    "miami": "Miami Heat",
    "chicago": "Chicago Bulls",
    "atlanta": "Atlanta Hawks",
    "cleveland": "Cleveland Cavaliers",
    "detroit": "Detroit Pistons",
    "indiana": "Indiana Pacers",
    "milwaukee": "Milwaukee Bucks",
    "toronto": "Toronto Raptors",
    "brooklyn": "Brooklyn Nets",
    "philadelphia": "Philadelphia 76ers",
    "washington": "Washington Wizards",
    "charlotte": "Charlotte Hornets",
    "orlando": "Orlando Magic",
    "denver": "Denver Nuggets",
    "oklahoma city": "Oklahoma City Thunder",
    # Note: bare 'oklahoma' intentionally omitted — collides with NCAAB Oklahoma Sooners
    "golden state": "Golden State Warriors",
    "san antonio": "San Antonio Spurs",
    "new orleans": "New Orleans Pelicans",
    "portland": "Portland Trail Blazers",
    "minnesota": "Minnesota Timberwolves",  # safe: sport isolation prevents NHL Wild collision
    "memphis": "Memphis Grizzlies",
    "sacramento": "Sacramento Kings",
    "houston": "Houston Rockets",
    "utah": "Utah Jazz",
    "phoenix": "Phoenix Suns",
    "dallas": "Dallas Mavericks",
    "los angeles l": "Los Angeles Lakers",
    "los angeles c": "Los Angeles Clippers",
    "new york k": "New York Knicks",
    "new york n": "New York Nets",
    # NHL — city/state only forms
    "vegas": "Vegas Golden Knights",
    "new jersey": "New Jersey Devils",
    "new york r": "New York Rangers",
    "new york i": "New York Islanders",
    "los angeles k": "Los Angeles Kings",
    "san jose": "San Jose Sharks",
    "winnipeg": "Winnipeg Jets",
    "anaheim": "Anaheim Ducks",
    "edmonton": "Edmonton Oilers",
    "calgary": "Calgary Flames",
    "vancouver": "Vancouver Canucks",
    "pittsburgh": "Pittsburgh Penguins",
    "columbus": "Columbus Blue Jackets",
    "florida": "Florida Panthers",
    "carolina": "Carolina Hurricanes",
    "montreal": "Montreal Canadiens",
    "ottawa": "Ottawa Senators",
    "buffalo": "Buffalo Sabres",
    "nashville": "Nashville Predators",
    "st. louis": "St. Louis Blues",
    "seattle k": "Seattle Kraken",
    "seattle kraken": "Seattle Kraken",
    "kraken": "Seattle Kraken",
    "utah h": "Utah Hockey Club",
    # ── NCAAB aliases ─────────────────────────────────────────────────────────
    # Two layers per team:
    #   1. Bare school name (e.g. "alabama") — anchor for _strip_ncaab_nickname
    #      when walking down "Alabama Crimson Tide" → "Alabama Crimson" → "Alabama"
    #   2. Full Odds API "School Nickname" form — direct fast-path
    # When adding a new team: add BOTH the bare name AND "bare name nickname".
    # Run `python main.py --date <date> --debug` to find missing entries.
    # ── Power conferences ────────────────────────────────────────────────────
    "alabama": "Alabama",
    "alabama crimson tide": "Alabama",
    "arizona": "Arizona",
    "arizona wildcats": "Arizona",
    "arizona st": "Arizona St",
    "arizona state": "Arizona St",
    "arizona state sun devils": "Arizona St",
    "arkansas": "Arkansas",
    "arkansas razorbacks": "Arkansas",
    "auburn": "Auburn",
    "auburn tigers": "Auburn",
    "baylor": "Baylor",
    "baylor bears": "Baylor",
    "ball state": "Ball State",
    "ball state cardinals": "Ball State",
    "byu": "BYU",
    "brigham young": "BYU",
    "brigham young cougars": "BYU",
    "cincinnati": "Cincinnati",
    "cincinnati bearcats": "Cincinnati",
    "clemson": "Clemson",
    "clemson tigers": "Clemson",
    "colorado buffaloes": "Colorado",
    "creighton": "Creighton",
    "creighton bluejays": "Creighton",
    "davidson": "Davidson",
    "davidson wildcats": "Davidson",
    "dayton": "Dayton",
    "dayton flyers": "Dayton",
    "depaul": "DePaul",
    "depaul blue demons": "DePaul",
    "duke": "Duke",
    "duke blue devils": "Duke",
    "duquesne": "Duquesne",
    "duquesne dukes": "Duquesne",
    "florida": "Florida",
    "florida gators": "Florida",
    "florida st": "Florida St",
    "florida state": "Florida St",
    "florida state seminoles": "Florida St",
    "georgetown": "Georgetown",
    "georgetown hoyas": "Georgetown",
    "georgia": "Georgia",
    "georgia bulldogs": "Georgia",
    "georgia tech": "Georgia Tech",
    "georgia tech yellow jackets": "Georgia Tech",
    "gonzaga": "Gonzaga",
    "gonzaga bulldogs": "Gonzaga",
    "howard": "Howard",
    "howard bison": "Howard",
    "illinois": "Illinois",
    "illinois fighting illini": "Illinois",
    "iowa": "Iowa",
    "iowa hawkeyes": "Iowa",
    "iowa st": "Iowa St",
    "iowa st.": "Iowa St",
    "iowa state": "Iowa St",
    "iowa state cyclones": "Iowa St",
    "iowa st cyclones": "Iowa St",
    "kansas": "Kansas",
    "kansas jayhawks": "Kansas",
    "kansas st": "Kansas St",
    "kansas state": "Kansas St",
    "kansas state wildcats": "Kansas St",
    "kentucky": "Kentucky",
    "kentucky wildcats": "Kentucky",
    "louisville": "Louisville",
    "louisville cardinals": "Louisville",
    "lsu": "LSU",
    "lsu tigers": "LSU",
    "marquette": "Marquette",
    "marquette golden eagles": "Marquette",
    "maryland": "Maryland",
    "maryland terrapins": "Maryland",
    "michigan": "Michigan",
    "michigan wolverines": "Michigan",
    "michigan st": "Michigan St",
    "michigan state": "Michigan St",
    "michigan state spartans": "Michigan St",
    "michigan st spartans": "Michigan St",
    "mississippi st": "Mississippi St",
    "mississippi state": "Mississippi St",
    "mississippi state bulldogs": "Mississippi St",
    "nc state": "NC State",
    "n.c. state": "NC State",
    "north carolina": "North Carolina",
    "north carolina tar heels": "North Carolina",
    "notre dame": "Notre Dame",
    "notre dame fighting irish": "Notre Dame",
    "ohio st": "Ohio St",
    "ohio st.": "Ohio St",
    "ohio state": "Ohio St",
    "ohio state buckeyes": "Ohio St",
    "ohio st buckeyes": "Ohio St",
    "oklahoma": "Oklahoma",
    "oklahoma sooners": "Oklahoma",
    "oregon": "Oregon",
    "oregon ducks": "Oregon",
    "penn st": "Penn St",
    "penn state": "Penn St",
    "penn state nittany lions": "Penn St",
    "purdue": "Purdue",
    "purdue boilermakers": "Purdue",
    "rutgers": "Rutgers",
    "rutgers scarlet knights": "Rutgers",
    "seton hall": "Seton Hall",
    "seton hall pirates": "Seton Hall",
    "st. john's": "St. John's",
    "st. john's red storm": "St. John's",
    "syracuse": "Syracuse",
    "syracuse orange": "Syracuse",
    "tcu": "TCU",
    "tcu horned frogs": "TCU",
    "temple": "Temple",
    "temple owls": "Temple",
    "tennessee": "Tennessee",
    "tennessee volunteers": "Tennessee",
    "texas": "Texas",
    "texas longhorns": "Texas",
    "texas am": "Texas A&M",
    "texas a&m": "Texas A&M",
    "texas a&m aggies": "Texas A&M",
    "texas tech": "Texas Tech",
    "texas tech red raiders": "Texas Tech",
    "tulsa": "Tulsa",
    "tulsa golden hurricane": "Tulsa",
    "ucla": "UCLA",
    "ucla bruins": "UCLA",
    "usc": "USC",
    "usc trojans": "USC",
    "vanderbilt": "Vanderbilt",
    "vanderbilt commodores": "Vanderbilt",
    "villanova": "Villanova",
    "villanova wildcats": "Villanova",
    "virginia": "Virginia",
    "virginia cavaliers": "Virginia",
    "virginia tech": "Virginia Tech",
    "virginia tech hokies": "Virginia Tech",
    "wake forest": "Wake Forest",
    "wake forest demon deacons": "Wake Forest",
    "wichita st": "Wichita St",
    "wichita state": "Wichita St",
    "wichita state shockers": "Wichita St",
    "wisconsin": "Wisconsin",
    "wisconsin badgers": "Wisconsin",
    "xavier": "Xavier",
    "xavier musketeers": "Xavier",
    # ── Mid-majors / conference tournament regulars ─────────────────────────
    "akron": "Akron",
    "akron zips": "Akron",
    "cal state fullerton": "Cal State Fullerton",
    "csu fullerton": "Cal State Fullerton",
    "csu fullerton titans": "Cal State Fullerton",
    "cal state northridge": "Cal State Northridge",
    "csu northridge": "Cal State Northridge",
    "csu northridge matadors": "Cal State Northridge",
    "csun": "Cal State Northridge",
    "california baptist": "California Baptist",
    "cal baptist": "California Baptist",
    "cal baptist lancers": "California Baptist",
    "california": "California Golden Bears",
    "cal": "California Golden Bears",
    "cal bears": "California Golden Bears",
    "california golden bears": "California Golden Bears",
    "davidson": "Davidson",
    "delaware st": "Delaware St",
    "delaware state": "Delaware St",
    "delaware st hornets": "Delaware St",
    "drake": "Drake",
    "george washington": "George Washington",
    "gw": "George Washington",
    "gw revolutionaries": "George Washington",
    "george washington colonials": "George Washington",
    "hawaii": "Hawaii",
    "hawai'i": "Hawaii",
    "hawaii warriors": "Hawaii",
    "hawai'i rainbow warriors": "Hawaii",
    "kent st": "Kent St",
    "kent state": "Kent St",
    "kent state golden flashes": "Kent St",
    "kent st golden flashes": "Kent St",
    "kennesaw st": "Kennesaw St",
    "kennesaw state": "Kennesaw St",
    "kennesaw st owls": "Kennesaw St",
    "louisiana tech": "Louisiana Tech",
    "louisiana tech bulldogs": "Louisiana Tech",
    "massachusetts": "UMass",
    "umass": "UMass",
    "umass minutemen": "UMass",
    "massachusetts minutemen": "UMass",
    "miami (fl)": "Miami FL",
    "miami (oh)": "Miami OH",
    "miami fl": "Miami FL",
    "miami oh": "Miami OH",
    "miami hurricanes": "Miami FL",
    "miami (florida) hurricanes": "Miami FL",
    "miami (ohio) redhawks": "Miami OH",
    "missouri st": "Missouri St",
    "missouri state": "Missouri St",
    "missouri state bears": "Missouri St",
    "missouri st bears": "Missouri St",
    "nebraska": "Nebraska",
    "nebraska cornhuskers": "Nebraska",
    "nevada": "Nevada",
    "nevada wolf pack": "Nevada",
    "new mexico": "New Mexico",
    "new mexico lobos": "New Mexico",
    "north carolina central": "North Carolina Central",
    "north carolina central eagles": "North Carolina Central",
    "north texas": "North Texas",
    "north texas mean green": "North Texas",
    "ohio": "Ohio",
    "ohio bobcats": "Ohio",
    "ole miss": "Ole Miss",
    "ole miss rebels": "Ole Miss",
    "prairie view a&m": "Prairie View A&M",
    "prairie view panthers": "Prairie View A&M",  # Odds API omits A&M
    "prairie view a&m panthers": "Prairie View A&M",
    "rhode island": "Rhode Island",
    "saint joseph's": "Saint Joseph's",
    "saint joseph's hawks": "Saint Joseph's",
    "saint louis": "Saint Louis",
    "saint louis billikens": "Saint Louis",
    "saint mary's": "Saint Mary's",
    "sam houston": "Sam Houston",
    "sam houston bearkats": "Sam Houston",
    "sam houston st bearkats": "Sam Houston",
    "san diego st": "San Diego St",
    "san diego state": "San Diego St",
    "san diego st aztecs": "San Diego St",
    "south carolina st": "South Carolina St",
    "south carolina state": "South Carolina St",
    "south carolina st bulldogs": "South Carolina St",
    "south florida": "South Florida",
    "southern": "Southern",
    "southern jaguars": "Southern",
    "southern university": "Southern",
    "southern university jaguars": "Southern",
    "st. bonaventure": "St. Bonaventure",
    "st. bonaventure bonnies": "St. Bonaventure",
    "toledo": "Toledo",
    "toledo rockets": "Toledo",
    "tulane": "Tulane",
    "tulane green wave": "Tulane",
    "uc irvine": "UC Irvine",
    "uc irvine anteaters": "UC Irvine",
    "uic": "UIC Flames",
    "uic flames": "UIC Flames",
    "illinois chicago": "UIC Flames",
    "illinois-chicago": "UIC Flames",
    "ui chicago": "UIC Flames",
    "uc san diego": "UC San Diego",
    "uc san diego tritons": "UC San Diego",
    "ucf": "UCF",
    "ucf knights": "UCF",
    "uab": "UAB",
    "uab blazers": "UAB",
    "uconn": "UConn",
    "uconn huskies": "UConn",
    "connecticut huskies": "UConn",
    "ut arlington": "UT Arlington",
    "ut-arlington": "UT Arlington",
    "ut-arlington mavericks": "UT Arlington",
    "utsa": "UTSA",
    "utsa roadrunners": "UTSA",
    "rice": "Rice",
    "rice owls": "Rice",
    "utah utes": "Utah",
    "utah st": "Utah St",
    "utah st.": "Utah St",
    "utah state": "Utah St",
    "utah state aggies": "Utah St",
    "utah st aggies": "Utah St",
    "utah tech": "Utah Tech",
    "utah tech trailblazers": "Utah Tech",
    "utah valley": "Utah Valley",
    "utah valley wolverines": "Utah Valley",
    "vcu": "VCU",
    "vcu rams": "VCU",
    "alabama a&m": "Alabama A&M",
    "alabama a&m bulldogs": "Alabama A&M",
    "florida a&m": "Florida A&M",
    "florida a&m rattlers": "Florida A&M",
    "charlotte 49ers": "Charlotte 49ers",  # UNC Charlotte (not NBA Hornets)

    # Full name aliases — The Odds API sometimes uses hyphenated forms that
    # differ slightly from Kalshi's shorter titles.
    "sydney roosters": "Sydney Roosters",
    "penrith panthers": "Penrith Panthers",
    "melbourne storm": "Melbourne Storm",
    "brisbane broncos": "Brisbane Broncos",
    "canberra raiders": "Canberra Raiders",
    "canterbury bulldogs": "Canterbury Bulldogs",
    "canterbury-bankstown bulldogs": "Canterbury Bulldogs",
    "newcastle knights": "Newcastle Knights",
    "manly sea eagles": "Manly Sea Eagles",
    "manly-warringah sea eagles": "Manly Sea Eagles",
    "gold coast titans": "Gold Coast Titans",
    "dolphins": "Dolphins",
    "brisbane dolphins": "Dolphins",
    "cronulla sharks": "Cronulla Sharks",
    "cronulla-sutherland sharks": "Cronulla Sharks",
    "wests tigers": "Wests Tigers",
    "north queensland cowboys": "North Queensland Cowboys",
    "st. george illawarra dragons": "St. George Illawarra Dragons",
    "st george illawarra dragons": "St. George Illawarra Dragons",
    "new zealand warriors": "New Zealand Warriors",
    "south sydney rabbitohs": "South Sydney Rabbitohs",
    "parramatta eels": "Parramatta Eels",
}


# ─── Title / ticker parsing ───────────────────────────────────────────────────

# "Sacramento at Los Angeles C Winner?"  →  away="Sacramento", home="Los Angeles C"
_AT_RE = re.compile(
    r"^(.+?) at (.+?) Winner",
    re.IGNORECASE,
)

# NRL / rugby "X vs Y Winner?" titles (no away/home distinction in title)
_VS_WINNER_RE = re.compile(
    r"^(.+?) vs\.? (.+?) Winner",
    re.IGNORECASE,
)

# Fallback patterns for older-style titles
_BEAT_RE = re.compile(
    r"will (?:the )?(.+?) (?:beat|defeat|top|win (?:against|over)) (?:the )?(.+?)(?:\?|$| on | - |\()",
    re.IGNORECASE,
)
_WIN_RE = re.compile(
    r"will (?:the )?(.+?) win(?:\?|$|[ ,])",
    re.IGNORECASE,
)
_VS_RE = re.compile(
    r"(.+?) (?:vs\.?|v\.?|@) (.+?)(?:\?|$| - | on |\()",
    re.IGNORECASE,
)


def extract_teams_from_ticker_and_title(
    ticker: str, title: str
) -> tuple[Optional[str], Optional[str]]:
    """
    Extract (yes_team, other_team) using the Kalshi ticker + title.

    Kalshi game markets now follow the pattern:
        ticker: KXNBAGAME-26MAR14SACLAC-SAC   ← last segment = YES team abbrev
        title:  "Sacramento at Los Angeles C Winner?"

    The YES team is identified by the last segment of the ticker (the YES abbrev).
    The game segment (e.g. "26MAR12NYRWPG") encodes both team abbrevs after the date.
    We cross-reference the away/home names parsed from the title against the
    YES abbrev to determine which is YES and which is the other team.

    Strategy:
        1. Parse away/home from title via "[Away] at [Home] Winner?" pattern.
        2. Extract YES_ABBREV from ticker last segment.
        3. Extract GAME_ABBREVS = last 6 chars of date segment (e.g. "NYRWPG").
           The YES_ABBREV should match the tail (last 3) or head (first 3) of GAME_ABBREVS.
        4. If YES_ABBREV == head → YES=away team; if tail → YES=home team.
        5. Fallback: check if YES_ABBREV is a substring of the canonical team name.

    Falls back to older regex patterns if the title doesn't match the 'at' format.
    """
    # ── New format: "[Away] at [Home] Winner?" ────────────────────────────────
    at_m = _AT_RE.search(title)
    if at_m:
        away_raw = at_m.group(1).strip()
        home_raw = at_m.group(2).strip()

        ticker_parts = ticker.upper().split("-")
        yes_abbrev = ticker_parts[-1] if ticker_parts else ""

        if yes_abbrev:
            # The game segment (e.g. "26MAR12NYRWPG") is the second part.
            # Strip the date prefix (digits + 3-letter month + 2 digits = ~9 chars)
            # to get the concatenated team abbrevs, then split them.
            game_seg = ticker_parts[1] if len(ticker_parts) > 1 else ""
            # Remove the date: digits at start + 3-char month + 2 more digits
            team_concat = re.sub(r'^\d+[A-Z]{3}\d+', '', game_seg)  # e.g. "LANYI"

            # Primary strategy: the YES abbrev must be either a prefix (away)
            # or suffix (home) of the team_concat string. This works regardless
            # of abbreviation length (2-char LA, 3-char NYI, 4-char UMES, etc.)
            n = len(yes_abbrev)
            if team_concat and len(team_concat) > n:
                if team_concat[:n] == yes_abbrev:
                    return away_raw, home_raw   # YES=away
                elif team_concat[-n:] == yes_abbrev:
                    return home_raw, away_raw   # YES=home
                # Neither prefix nor suffix — fall through

        # Last resort: assume away team is YES (first team listed)
        return away_raw, home_raw

    # ── NRL / "X vs Y Winner?" format ─────────────────────────────────────────
    # NRL titles don't use "at" — they use "X vs Y Winner?".
    # The team_concat order is REVERSED relative to the title order for NRL:
    #   prefix of concat → second team in title
    #   suffix of concat → first team in title
    # (opposite of the NBA/NHL "away at home" convention above)
    vs_winner_m = _VS_WINNER_RE.search(title)
    if vs_winner_m:
        t1 = vs_winner_m.group(1).strip()
        t2 = vs_winner_m.group(2).strip()

        ticker_parts = ticker.upper().split("-")
        yes_abbrev = ticker_parts[-1] if ticker_parts else ""

        if yes_abbrev:
            game_seg = ticker_parts[1] if len(ticker_parts) > 1 else ""
            team_concat = re.sub(r'^\d+[A-Z]{3}\d+', '', game_seg)
            n = len(yes_abbrev)
            if team_concat and len(team_concat) > n:
                if team_concat[:n] == yes_abbrev:
                    return t2, t1   # YES = second title team
                elif team_concat[-n:] == yes_abbrev:
                    return t1, t2   # YES = first title team

        return t1, t2  # fallback: assume first listed team is YES

    # ── Legacy patterns ───────────────────────────────────────────────────────
    m = _BEAT_RE.search(title)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    win_m = _WIN_RE.search(title)
    vs_m = _VS_RE.search(title)
    if win_m and vs_m:
        yes_team = win_m.group(1).strip()
        t1, t2 = vs_m.group(1).strip(), vs_m.group(2).strip()
        other_team = t2 if yes_team.lower() in t1.lower() else t1
        return yes_team, other_team
    if win_m:
        return win_m.group(1).strip(), None
    if vs_m:
        return vs_m.group(1).strip(), vs_m.group(2).strip()

    return None, None


# Keep old name as alias for any other callers
def extract_teams_from_title(title: str) -> tuple[Optional[str], Optional[str]]:
    return extract_teams_from_ticker_and_title("", title)


# ─── Canonicalization ─────────────────────────────────────────────────────────


def _strip_ncaab_nickname(name: str) -> str:
    """
    Strip the mascot/nickname from an Odds API NCAAB team name by finding
    the longest prefix that exists in TEAM_ALIASES.

    Examples (requires school name keys in TEAM_ALIASES):
        "Alabama Crimson Tide"          → "Alabama"       (alias: "alabama")
        "Michigan St Spartans"          → "Michigan St"   (alias: "michigan st")
        "North Carolina Central Eagles" → "North Carolina Central"
        "Seton Hall Pirates"            → "Seton Hall"    (alias: "seton hall")
        "UT-Arlington Mavericks"        → "UT-Arlington"  (alias: "ut-arlington")

    If NO prefix matches an alias the name is returned unchanged so the
    fuzzy scorer still gets a chance to handle it.
    """
    name = name.strip()
    parts = name.split()
    # Walk from longest prefix down to single word
    for end in range(len(parts), 0, -1):
        candidate = " ".join(parts[:end])
        if candidate.lower() in TEAM_ALIASES:
            return candidate
    # No alias match at any length — return as-is
    return name


def canonicalize(name: str, sport: str = "") -> str:
    """
    Resolve a team name string to its canonical form via the alias table.
    Falls back to title-cased input if no alias is found.

    The optional `sport` parameter enables sport-aware disambiguation for
    city names shared between leagues (e.g. "Minnesota" → Timberwolves in NBA,
    Minnesota Wild in NHL).

    Only exact alias-key matches are used. Substring matching was removed
    because it caused false positives (e.g. "Oklahoma" → "Oklahoma City Thunder").
    If a new team name pattern isn't resolving correctly, add it to TEAM_ALIASES.
    """
    key = name.strip().lower()

    # Sport-aware overrides for ambiguous city names
    if sport:
        _NHL_OVERRIDES: dict[str, str] = {
            "minnesota": "Minnesota Wild",
            "colorado": "Colorado Avalanche",
            "carolina": "Carolina Hurricanes",
            "florida": "Florida Panthers",
            "pittsburgh": "Pittsburgh Penguins",
            "columbus": "Columbus Blue Jackets",
            "new york": "New York Rangers",  # NYR is the default NHL NY team
            # Cities that share a name with NBA teams
            "chicago": "Chicago Blackhawks",
            "toronto": "Toronto Maple Leafs",
            "detroit": "Detroit Red Wings",
            "dallas": "Dallas Stars",
            "boston": "Boston Bruins",
            "philadelphia": "Philadelphia Flyers",
            "washington": "Washington Capitals",
            "seattle": "Seattle Kraken",
            "utah": "Utah Mammoth",
            "tampa bay": "Tampa Bay Lightning",
            "san jose": "San Jose Sharks",
            "anaheim": "Anaheim Ducks",
            "buffalo": "Buffalo Sabres",
            "vancouver": "Vancouver Canucks",
            "calgary": "Calgary Flames",
            "edmonton": "Edmonton Oilers",
            "ottawa": "Ottawa Senators",
            "montreal": "Montreal Canadiens",
            "winnipeg": "Winnipeg Jets",
        }
        _NBA_OVERRIDES: dict[str, str] = {
            "minnesota": "Minnesota Timberwolves",
            "new york": "New York Knicks",
        }
        _NCAAB_OVERRIDES: dict[str, str] = {
            # Cities that have NBA/NHL aliases but mean something different in NCAAB
            "charlotte": "Charlotte 49ers",   # UNC Charlotte (not NBA Hornets)
            "houston": "Houston",              # Houston Cougars (not NBA Rockets)
            "memphis": "Memphis",              # Memphis Tigers (not NBA Grizzlies)
            "minnesota": "Minnesota",          # Minnesota Gophers (not NBA T-wolves)
            "washington": "Washington",        # Washington Huskies (not NBA Wizards)
            "indiana": "Indiana",              # Indiana Hoosiers (not NBA Pacers)
            "utah": "Utah",                    # Utah Utes (not NBA Jazz)
            "colorado": "Colorado",            # Colorado Buffaloes (not NHL Avs)
            "florida": "Florida",              # Florida Gators (not NHL Panthers)
            "pittsburgh": "Pittsburgh",        # Pittsburgh Panthers (not NHL Penguins)
            "miami": "Miami FL",               # Miami Hurricanes (not NBA Heat)
            "portland": "Portland",            # Portland Pilots (not NBA Trail Blazers)
        }
        if sport == "icehockey_nhl" and key in _NHL_OVERRIDES:
            return _NHL_OVERRIDES[key]
        if sport in ("basketball_nba",) and key in _NBA_OVERRIDES:
            return _NBA_OVERRIDES[key]
        if sport in ("basketball_ncaab", "basketball_wncaab") and key in _NCAAB_OVERRIDES:
            return _NCAAB_OVERRIDES[key]

    if key in TEAM_ALIASES:
        return TEAM_ALIASES[key]
    return name.strip().title()


def _team_sim(a: str, b: str, sport: str = "") -> float:
    """Fuzzy similarity score 0–100 between two team name strings."""
    if sport in ("basketball_ncaab", "basketball_wncaab"):
        # Odds API uses "School Nickname" format; strip the nickname so
        # "South Carolina Gamecocks" compares against Kalshi's "South Carolina".
        a = _strip_ncaab_nickname(a)
        b = _strip_ncaab_nickname(b)
    ca = canonicalize(a, sport).lower()
    cb = canonicalize(b, sport).lower()

    # Substring containment: if one name is fully contained in the other
    # (e.g. "Charleston" in "Charleston Cougars"), treat as a near-perfect match.
    # Require at least 4 chars to avoid spurious single-word hits.
    _norm = lambda s: re.sub(r"[^a-z0-9 ]", "", s).strip()
    na, nb = _norm(ca), _norm(cb)
    if len(na) >= 4 and len(nb) >= 4:
        if na in nb or nb in na:
            return 95.0

    return fuzz.token_sort_ratio(ca, cb)


# ─── Matching ─────────────────────────────────────────────────────────────────


def match_markets(
    kalshi_markets: list[KalshiMarket],
    odds_markets: list[NormalizedOddsMarket],
    date_window_hours: int = 18,
    min_similarity: float = 78.0,
    debug: bool = False,
) -> list[MatchedMarket]:
    """
    Match each Kalshi market to the most similar sportsbook market.

    Matching criteria:
        1. Sport type must match (NBA Kalshi → only NBA sportsbook games, etc.).
        2. Game time within `date_window_hours` of Kalshi close_time.
           With expected_expiration_time used as close_time (~2-6h after tip-off),
           18h safely covers same-game matches while preventing adjacent-day mismatches.
        3. YES-team fuzzy similarity ≥ `min_similarity` against home or away.
        4. Secondary confirmation: the other Kalshi team also matches the
           opposing sportsbook team.

    Args:
        kalshi_markets:    Open Kalshi markets (sports-filtered).
        odds_markets:      Vig-removed sportsbook markets.
        date_window_hours: Maximum hours between game times to allow a match.
        min_similarity:    Minimum rapidfuzz score (0–100) to accept a match.

    Returns:
        List of MatchedMarket pairs, one per successfully matched Kalshi market.
    """
    matched: list[MatchedMarket] = []

    # Diagnostic counters — printed at the end to explain low match rates
    _diag_no_parse = 0
    _diag_no_time_eligible = 0   # all odds markets filtered by time/sport before fuzzy step
    _diag_no_fuzzy = 0           # survived time filter but no team name match
    _diag_ok = 0
    _debug_misses: list[dict] = []  # populated when debug=True

    for km in kalshi_markets:
        yes_team_raw, other_team_raw = extract_teams_from_ticker_and_title(km.ticker, km.title)
        if yes_team_raw is None:
            _diag_no_parse += 1
            continue  # Couldn't parse this title

        sport = km.sport_type
        yes_canonical = canonicalize(yes_team_raw, sport)
        other_canonical = canonicalize(other_team_raw, sport) if other_team_raw else None

        best_match: Optional[NormalizedOddsMarket] = None
        best_score = 0.0
        best_yes_is_home = True
        _time_eligible = 0

        for om in odds_markets:
            # ── Sport isolation ──────────────────────────────────────────────
            # Only match NBA Kalshi markets to NBA odds, NCAAB to NCAAB, etc.
            if km.sport_type and om.sport != km.sport_type:
                continue

            # ── Time proximity filter ────────────────────────────────────────
            time_diff = abs((km.close_time - om.commence_time).total_seconds())
            if time_diff > date_window_hours * 3600:
                continue

            _time_eligible += 1

            # ── Similarity: YES = home team ──────────────────────────────────
            home_sim = _team_sim(yes_canonical, om.home_team, sport)
            if home_sim >= min_similarity:
                # Confirm with the other team if we have it
                confirm = (
                    _team_sim(other_canonical, om.away_team, sport)
                    if other_canonical else 50.0
                )
                score = (home_sim + confirm) / 2.0
                if score > best_score:
                    best_score, best_match, best_yes_is_home = score, om, True

            # ── Similarity: YES = away team ──────────────────────────────────
            away_sim = _team_sim(yes_canonical, om.away_team, sport)
            if away_sim >= min_similarity:
                confirm = (
                    _team_sim(other_canonical, om.home_team, sport)
                    if other_canonical else 50.0
                )
                score = (away_sim + confirm) / 2.0
                if score > best_score:
                    best_score, best_match, best_yes_is_home = score, om, False

        if best_match is not None:
            _diag_ok += 1
            matched.append(
                MatchedMarket(
                    kalshi=km,
                    sportsbook=best_match,
                    yes_is_home=best_yes_is_home,
                    confidence=best_score / 100.0,
                )
            )
        elif _time_eligible == 0:
            _diag_no_time_eligible += 1
        else:
            _diag_no_fuzzy += 1
            if debug:
                # Find the best individual sportsbook match for each Kalshi team
                eligible = [
                    om for om in odds_markets
                    if om.sport == km.sport_type
                    and abs((km.close_time - om.commence_time).total_seconds()) <= date_window_hours * 3600
                ]
                yes_best_score, yes_best_match = 0.0, None
                other_best_score, other_best_match = 0.0, None
                for om in eligible:
                    for odds_name in [om.home_team, om.away_team]:
                        s_yes = _team_sim(yes_canonical, odds_name, km.sport_type)
                        if s_yes > yes_best_score:
                            yes_best_score = s_yes
                            yes_best_match = odds_name
                        if other_canonical:
                            s_other = _team_sim(other_canonical, odds_name, km.sport_type)
                            if s_other > other_best_score:
                                other_best_score = s_other
                                other_best_match = odds_name
                _debug_misses.append({
                    "sport": km.sport_type,
                    "kalshi_yes": yes_canonical,
                    "kalshi_other": other_canonical or "?",
                    "yes_sb_match": yes_best_match,
                    "other_sb_match": other_best_match,
                })

    n_kalshi_games = len(kalshi_markets) // 2
    n_matched_games = len(matched) // 2
    print(
        f"[Matcher] Matched {n_matched_games} / {n_kalshi_games} Kalshi games "
        f"to sportsbook games."
    )
    print(
        f"[Matcher] Unmatched breakdown (contracts): "
        f"wrong date/no odds={_diag_no_time_eligible}  "
        f"name mismatch={_diag_no_fuzzy}  "
        f"unparseable={_diag_no_parse}"
    )

    if debug and _debug_misses:
        seen: set[tuple[str, str]] = set()
        print(f"\n[Debug] Unmatched Kalshi games:")
        print(f"  {'Kalshi Team A':<38} {'Kalshi Team B':<38} {'SB Team A Match':<38} {'SB Team B Match':<38}")
        print(f"  {'-'*38} {'-'*38} {'-'*38} {'-'*38}")
        for miss in sorted(_debug_misses, key=lambda x: x["kalshi_yes"]):
            key = tuple(sorted([miss["kalshi_yes"], miss["kalshi_other"]]))
            if key in seen:
                continue
            seen.add(key)
            sp = miss["sport"].split("_")[-1]
            ya = f"{miss['yes_sb_match']} ({sp})" if miss["yes_sb_match"] else "N/A"
            ob = f"{miss['other_sb_match']} ({sp})" if miss["other_sb_match"] else "N/A"
            ka = f"{miss['kalshi_yes']} ({sp})"
            kb = f"{miss['kalshi_other']} ({sp})"
            print(
                f"  {ka:<38} {kb:<38} "
                f"{ya:<38} {ob:<38}"
            )
        print()
    return matched
