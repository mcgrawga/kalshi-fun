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
from engine.aliases import ALIASES_BY_SPORT
from engine.mappings import get_mapping, save_mapping


# ─── Team alias tables ────────────────────────────────────────────────────────
# Per-sport alias dicts live in engine/aliases/{nba,nhl,ncaab,wncaab,nrl}.py
# Each file is fully isolated — a key in nba.py has no effect on nhl lookups.
# Use ALIASES_BY_SPORT.get(sport, {}) to access the correct table.


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


def _strip_college_nickname(name: str, sport: str) -> str:
    """
    Strip the mascot/nickname from an Odds API college team name by finding
    the longest prefix that exists in the sport's alias table.

    Examples (basketball_ncaab):
        "Alabama Crimson Tide"          → "Alabama"
        "Michigan St Spartans"          → "Michigan St"
        "North Carolina Central Eagles" → "North Carolina Central"
        "Seton Hall Pirates"            → "Seton Hall"
        "UT-Arlington Mavericks"        → "UT-Arlington"

    If NO prefix matches an alias the name is returned unchanged so the
    fuzzy scorer still gets a chance to handle it.
    """
    aliases = ALIASES_BY_SPORT.get(sport, {})
    name = name.strip()
    parts = name.split()
    for end in range(len(parts), 0, -1):
        candidate = " ".join(parts[:end])
        if candidate.lower() in aliases:
            return candidate
    return name


# Keep old name as a shim so any external callers don't break.
def _strip_ncaab_nickname(name: str, sport: str = "basketball_ncaab") -> str:
    return _strip_college_nickname(name, sport)


def canonicalize(name: str, sport: str = "") -> str:
    """
    Resolve a team name string to its canonical form via the sport-specific
    alias table. Falls back to title-cased input if no alias is found.

    Each sport's aliases are fully isolated in engine/aliases/<sport>.py —
    there are no cross-sport collisions. If a team name isn't resolving
    correctly, add it to the appropriate sport alias file.
    """
    key = name.strip().lower()
    aliases = ALIASES_BY_SPORT.get(sport, {})
    if key in aliases:
        return aliases[key]
    return name.strip().title()


def _team_sim(a: str, b: str, sport: str = "") -> float:
    """Fuzzy similarity score 0–100 between two team name strings."""
    if sport in ("basketball_ncaab", "basketball_wncaab"):
        # Odds API uses "School Nickname" format; strip the nickname so
        # "South Carolina Gamecocks" compares against Kalshi's "South Carolina".
        a = _strip_college_nickname(a, sport)
        b = _strip_college_nickname(b, sport)
    ca = canonicalize(a, sport).lower()
    cb = canonicalize(b, sport).lower()

    # Substring containment: if one name is fully contained in the other
    # (e.g. "South Florida" in "South Florida Bulls"), treat as near-perfect match.
    # Require the shorter string to be multi-word so that single-word school names
    # ("Iowa", "Illinois") never spuriously match their State counterparts.
    _norm = lambda s: re.sub(r"[^a-z0-9 ]", "", s).strip()
    na, nb = _norm(ca), _norm(cb)
    if len(na) >= 4 and len(nb) >= 4:
        shorter = na if len(na) <= len(nb) else nb
        if (na in nb or nb in na) and len(shorter.split()) >= 2:
            return 95.0

    return fuzz.token_sort_ratio(ca, cb)


# ─── Matching ─────────────────────────────────────────────────────────────────


def match_markets(
    kalshi_markets: list[KalshiMarket],
    odds_markets: list[NormalizedOddsMarket],
    date_window_hours: int = 18,
    min_similarity: float = 78.0,
    debug: bool = False,
    auto_loop: bool = False,
) -> list[MatchedMarket]:
    """
    Match each Kalshi market to the most similar sportsbook market.

    Three-tier matching:
        Tier 1 — Deterministic JSON lookup (engine/mappings/*.json).
                 100% accurate for any team seen before.
        Tier 2 — Fuzzy match with score ≥ 90.  Accepted automatically and
                 auto-saved to the mapping file for next time.
        Tier 3 — Fuzzy match with score 70–89.  The user is prompted to
                 confirm/skip/manually enter the correct name.  In
                 --auto-bet-loop mode, these are silently skipped.
        Below 70 — no match, game skipped entirely.

    Additional filters applied before name matching:
        1. Sport type must match (NBA Kalshi → only NBA sportsbook games, etc.).
        2. Game time within `date_window_hours` of Kalshi close_time.

    Args:
        kalshi_markets:    Open Kalshi markets (sports-filtered).
        odds_markets:      Vig-removed sportsbook markets.
        date_window_hours: Maximum hours between game times to allow a match.
        min_similarity:    Minimum rapidfuzz score (0–100) for Tier 2/3 cutoff.
        debug:             If True, print detailed info about unmatched games.
        auto_loop:         If True, skip Tier 3 prompts (for --auto-bet-loop).

    Returns:
        List of MatchedMarket pairs, one per successfully matched Kalshi market.
    """
    matched: list[MatchedMarket] = []

    # Diagnostic counters
    _diag_no_parse = 0
    _diag_no_time_eligible = 0
    _diag_no_fuzzy = 0
    _diag_tier1 = 0
    _diag_tier2 = 0
    _diag_tier3_accept = 0
    _diag_tier3_skip = 0
    _diag_ok = 0
    _debug_misses: list[dict] = []

    # Pre-index odds markets by sport for faster lookup
    _odds_by_sport: dict[str, list[NormalizedOddsMarket]] = {}
    for om in odds_markets:
        _odds_by_sport.setdefault(om.sport, []).append(om)

    for km in kalshi_markets:
        yes_team_raw, other_team_raw = extract_teams_from_ticker_and_title(km.ticker, km.title)
        if yes_team_raw is None:
            _diag_no_parse += 1
            continue

        sport = km.sport_type

        # Resolve YES team name — use ticker suffix alias as the strongest signal
        yes_canonical = canonicalize(yes_team_raw, sport)
        other_canonical = canonicalize(other_team_raw, sport) if other_team_raw else None

        ticker_suffix = km.ticker.upper().rsplit("-", 1)[-1]
        abbrev_canon = canonicalize(ticker_suffix, sport)
        if abbrev_canon.lower() != ticker_suffix.lower():
            yes_canonical = abbrev_canon

        # ── Tier 1: deterministic mapping lookup ─────────────────────────────
        # Check if this Kalshi team name has a confirmed mapping to an odds name.
        mapped_odds_name = get_mapping(sport, yes_canonical)
        mapped_other_name = get_mapping(sport, other_canonical) if other_canonical else None

        # Eligible sportsbook games (sport + time filter)
        eligible = [
            om for om in _odds_by_sport.get(sport, [])
            if abs((km.close_time - om.commence_time).total_seconds()) <= date_window_hours * 3600
        ]
        if not eligible:
            _diag_no_time_eligible += 1
            continue

        # Try Tier 1: exact match via mapping
        tier1_match = None
        tier1_yes_is_home = True
        if mapped_odds_name:
            for om in eligible:
                if mapped_odds_name.lower() == om.home_team.lower():
                    tier1_match = om
                    tier1_yes_is_home = True
                    break
                elif mapped_odds_name.lower() == om.away_team.lower():
                    tier1_match = om
                    tier1_yes_is_home = False
                    break

        if tier1_match is not None:
            _diag_tier1 += 1
            _diag_ok += 1
            matched.append(MatchedMarket(
                kalshi=km,
                sportsbook=tier1_match,
                yes_is_home=tier1_yes_is_home,
                confidence=1.0,
            ))
            continue

        # ── Tier 2 / 3: fuzzy matching ───────────────────────────────────────
        best_match: Optional[NormalizedOddsMarket] = None
        best_score = 0.0
        best_yes_is_home = True

        for om in eligible:
            # YES = home team
            home_sim = _team_sim(yes_canonical, om.home_team, sport)
            if home_sim >= 70.0:
                confirm = (
                    _team_sim(other_canonical, om.away_team, sport)
                    if other_canonical else 50.0
                )
                score = (home_sim + confirm) / 2.0
                if score > best_score:
                    best_score, best_match, best_yes_is_home = score, om, True

            # YES = away team
            away_sim = _team_sim(yes_canonical, om.away_team, sport)
            if away_sim >= 70.0:
                confirm = (
                    _team_sim(other_canonical, om.home_team, sport)
                    if other_canonical else 50.0
                )
                score = (away_sim + confirm) / 2.0
                if score > best_score:
                    best_score, best_match, best_yes_is_home = score, om, False

        if best_match is None:
            _diag_no_fuzzy += 1
            if debug:
                _debug_misses.append(_build_debug_miss(
                    km, yes_canonical, other_canonical, eligible
                ))
            continue

        # Determine which tier this falls into
        if best_score >= 90.0:
            # ── Tier 2: auto-accept and auto-save mapping ────────────────────
            odds_team = best_match.home_team if best_yes_is_home else best_match.away_team
            save_mapping(sport, yes_canonical, odds_team)
            if other_canonical:
                odds_other = best_match.away_team if best_yes_is_home else best_match.home_team
                save_mapping(sport, other_canonical, odds_other)
            _diag_tier2 += 1
            _diag_ok += 1
            matched.append(MatchedMarket(
                kalshi=km,
                sportsbook=best_match,
                yes_is_home=best_yes_is_home,
                confidence=best_score / 100.0,
            ))

        elif best_score >= 70.0:
            # ── Tier 3: user confirmation required ───────────────────────────
            odds_team = best_match.home_team if best_yes_is_home else best_match.away_team
            if auto_loop:
                # In loop mode, skip uncertain matches silently
                _diag_tier3_skip += 1
                if debug:
                    print(
                        f"[Matcher] ⏭  Skipping uncertain match "
                        f"({best_score:.0f}%): '{yes_canonical}' ↔ "
                        f"'{odds_team}' ({km.ticker})"
                    )
                continue

            # Interactive prompt
            accepted = _prompt_uncertain_match(
                sport, km, yes_canonical, other_canonical,
                best_match, best_yes_is_home, best_score, eligible,
            )
            if accepted:
                _diag_tier3_accept += 1
                _diag_ok += 1
                matched.append(MatchedMarket(
                    kalshi=km,
                    sportsbook=accepted[0],
                    yes_is_home=accepted[1],
                    confidence=best_score / 100.0,
                ))
            else:
                _diag_tier3_skip += 1
        else:
            _diag_no_fuzzy += 1
            if debug:
                _debug_misses.append(_build_debug_miss(
                    km, yes_canonical, other_canonical, eligible
                ))

    # ── Summary ───────────────────────────────────────────────────────────────
    n_kalshi_games = len(kalshi_markets) // 2
    n_matched_games = len(matched) // 2
    print(
        f"[Matcher] Matched {n_matched_games} / {n_kalshi_games} Kalshi games "
        f"to sportsbook games."
    )
    t1 = _diag_tier1 // 2
    t2 = _diag_tier2 // 2
    t3a = _diag_tier3_accept // 2
    t3s = _diag_tier3_skip // 2
    if t1 or t2 or t3a or t3s:
        print(
            f"[Matcher] Tier breakdown: "
            f"T1 (exact)={t1}  T2 (auto)={t2}  "
            f"T3 (confirmed)={t3a}  T3 (skipped)={t3s}"
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


def _build_debug_miss(
    km: KalshiMarket,
    yes_canonical: str,
    other_canonical: str | None,
    eligible: list[NormalizedOddsMarket],
) -> dict:
    """Build a debug-miss record for unmatched games."""
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
    return {
        "sport": km.sport_type,
        "kalshi_yes": yes_canonical,
        "kalshi_other": other_canonical or "?",
        "yes_sb_match": yes_best_match,
        "other_sb_match": other_best_match,
    }


def _prompt_uncertain_match(
    sport: str,
    km: KalshiMarket,
    yes_canonical: str,
    other_canonical: str | None,
    best_match: NormalizedOddsMarket,
    best_yes_is_home: bool,
    best_score: float,
    eligible: list[NormalizedOddsMarket],
) -> tuple[NormalizedOddsMarket, bool] | None:
    """
    Prompt the user to confirm an uncertain (Tier 3) match.

    Returns (sportsbook_market, yes_is_home) if accepted, or None if skipped.
    """
    odds_team = best_match.home_team if best_yes_is_home else best_match.away_team
    odds_other = best_match.away_team if best_yes_is_home else best_match.home_team

    print()
    print(f"  ⚠  Uncertain match ({best_score:.0f}% confidence):")
    print(f"     Kalshi:     \"{yes_canonical}\" vs \"{other_canonical or '?'}\"")
    print(f"     Sportsbook: \"{odds_team}\" vs \"{odds_other}\"")
    print(f"     Ticker:     {km.ticker}")
    print(f"     Sport:      {sport}")
    print()
    print(f"     [y] Accept and save mapping")
    print(f"     [n] Skip this game")
    print(f"     [m] Manually pick from eligible sportsbook games")

    try:
        choice = input(f"     Choice (y/n/m): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    if choice == "y":
        save_mapping(sport, yes_canonical, odds_team)
        if other_canonical:
            save_mapping(sport, other_canonical, odds_other)
        return (best_match, best_yes_is_home)

    elif choice == "m":
        # Show all eligible sportsbook games
        print()
        print(f"     Eligible sportsbook games for {sport}:")
        for idx, om in enumerate(eligible, 1):
            print(f"       {idx}. {om.away_team} @ {om.home_team}")
        print(f"       0. Skip (no match)")
        try:
            pick_str = input(f"     Pick game number: ").strip()
            pick = int(pick_str)
        except (ValueError, EOFError, KeyboardInterrupt):
            print()
            return None

        if pick < 1 or pick > len(eligible):
            return None

        picked = eligible[pick - 1]
        # Ask which side is the YES team
        print(f"       Is '{yes_canonical}' the home team ({picked.home_team}) or away ({picked.away_team})?")
        try:
            side = input(f"       [h]ome / [a]way: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None

        if side.startswith("h"):
            save_mapping(sport, yes_canonical, picked.home_team)
            if other_canonical:
                save_mapping(sport, other_canonical, picked.away_team)
            return (picked, True)
        elif side.startswith("a"):
            save_mapping(sport, yes_canonical, picked.away_team)
            if other_canonical:
                save_mapping(sport, other_canonical, picked.home_team)
            return (picked, False)
        return None

    # 'n' or anything else = skip
    return None
