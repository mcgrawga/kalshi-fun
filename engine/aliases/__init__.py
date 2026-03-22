"""
Sport-isolated team alias tables.

Each sport's aliases live in their own module — keys are lowercase team name
variants, values are the canonical form used by The Odds API. No cross-sport
sharing: a key in nba.py has no effect on nhl.py lookups and vice versa.

ALIASES_BY_SPORT maps each Odds API sport key → that sport's alias dict.
Callers should look up ALIASES_BY_SPORT.get(sport, {}) rather than importing
individual modules directly.
"""

from engine.aliases import nba, nhl, ncaab, wncaab, nrl

ALIASES_BY_SPORT: dict[str, dict[str, str]] = {
    "basketball_nba":      nba.ALIASES,
    "icehockey_nhl":       nhl.ALIASES,
    "basketball_ncaab":    ncaab.ALIASES,
    "basketball_wncaab":   wncaab.ALIASES,
    "rugbyleague_nrl":     nrl.ALIASES,
}
