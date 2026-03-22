"""
Deterministic team-name mapping tables (Kalshi ↔ sportsbook).

Each sport has a JSON file that maps Kalshi's team name (as seen in market
titles or ticker abbrevs) to the corresponding sportsbook team name (as
returned by The Odds API). This is a 1-to-1 relationship per sport+source.

The JSON files grow over time:
  • Tier 2 auto-saves (fuzzy ≥90) write new entries automatically.
  • Tier 3 user confirmations write new entries on accept / manual entry.

Usage
-----
    from engine.mappings import get_mapping, save_mapping

    # Look up a Kalshi team name → sportsbook name
    odds_name = get_mapping("basketball_nba", "Los Angeles Lakers")

    # Reverse: sportsbook name → Kalshi name
    kalshi_name = get_mapping_reverse("basketball_nba", "Los Angeles Lakers")

    # Persist a newly confirmed pair
    save_mapping("basketball_ncaab", "Illinois Fighting Illini", "Illinois")
"""

import json
from pathlib import Path
from threading import Lock

# ─── File layout ──────────────────────────────────────────────────────────────
# One JSON file per (sport, source) pair.  Currently the only source is
# "odds" (The Odds API), so the filenames are just {sport_key}.json.
_DIR = Path(__file__).resolve().parent

_SPORT_FILES: dict[str, str] = {
    "basketball_nba":   "nba.json",
    "icehockey_nhl":    "nhl.json",
    "basketball_ncaab": "ncaab.json",
    "basketball_wncaab": "wncaab.json",
    "rugbyleague_nrl":  "nrl.json",
    "soccer_usa_mls":   "soccer_usa_mls.json",
}

# ─── In-memory caches ────────────────────────────────────────────────────────
# Forward: kalshi_name → odds_name   (keys are lowercased for case-insensitive lookup)
# Reverse: odds_name  → kalshi_name  (keys are lowercased)
_forward: dict[str, dict[str, str]] = {}
_reverse: dict[str, dict[str, str]] = {}
_lock = Lock()
_loaded = False


def _load_all() -> None:
    """Load every sport JSON file into the in-memory caches."""
    global _loaded
    if _loaded:
        return
    with _lock:
        if _loaded:
            return
        for sport, fname in _SPORT_FILES.items():
            fpath = _DIR / fname
            if fpath.exists():
                with open(fpath, "r") as f:
                    raw: dict[str, str] = json.load(f)
            else:
                raw = {}
            fwd: dict[str, str] = {}
            rev: dict[str, str] = {}
            for kalshi_name, odds_name in raw.items():
                fwd[kalshi_name.lower()] = odds_name
                rev[odds_name.lower()] = kalshi_name
            _forward[sport] = fwd
            _reverse[sport] = rev
        _loaded = True


def _save_file(sport: str) -> None:
    """Write the current forward cache for `sport` back to its JSON file."""
    fname = _SPORT_FILES.get(sport)
    if not fname:
        return
    fpath = _DIR / fname
    fwd = _forward.get(sport, {})
    # Rebuild with original-cased keys from the values stored in reverse.
    # The forward dict stores lowercased keys but the JSON should be readable.
    rev = _reverse.get(sport, {})
    out: dict[str, str] = {}
    for key_lower, odds_name in sorted(fwd.items()):
        # Try to recover original-case Kalshi name from reverse lookup
        original = rev.get(odds_name.lower(), key_lower.title())
        out[original] = odds_name
    with open(fpath, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ─── Public API ───────────────────────────────────────────────────────────────

def get_mapping(sport: str, kalshi_name: str) -> str | None:
    """
    Look up a Kalshi team name → Odds API team name.

    Returns None if no mapping exists (caller should fall back to fuzzy match).
    """
    _load_all()
    fwd = _forward.get(sport, {})
    return fwd.get(kalshi_name.strip().lower())


def get_mapping_reverse(sport: str, odds_name: str) -> str | None:
    """
    Look up an Odds API team name → Kalshi team name.

    Returns None if no mapping exists.
    """
    _load_all()
    rev = _reverse.get(sport, {})
    return rev.get(odds_name.strip().lower())


def save_mapping(sport: str, kalshi_name: str, odds_name: str) -> None:
    """
    Persist a confirmed Kalshi ↔ Odds API name pair.

    Updates the in-memory cache and writes the JSON file to disk.
    """
    _load_all()
    with _lock:
        if sport not in _forward:
            _forward[sport] = {}
        if sport not in _reverse:
            _reverse[sport] = {}
        _forward[sport][kalshi_name.strip().lower()] = odds_name
        _reverse[sport][odds_name.strip().lower()] = kalshi_name.strip()
        _save_file(sport)


def get_all_mappings(sport: str) -> dict[str, str]:
    """Return a copy of the full forward mapping dict for a sport (lowercase keys)."""
    _load_all()
    return dict(_forward.get(sport, {}))


def reload() -> None:
    """Force-reload all JSON files from disk (useful after manual edits)."""
    global _loaded
    with _lock:
        _forward.clear()
        _reverse.clear()
        _loaded = False
    _load_all()
