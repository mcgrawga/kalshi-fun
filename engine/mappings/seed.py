"""
One-shot seeder: reads engine/aliases/*.py and generates the initial
engine/mappings/*.json files.

The alias tables map *many variants → one canonical Odds API name*.
For the mapping JSON, we want:
  - Every variant that looks like a plausible Kalshi title name → Odds API canonical.
  - The canonical name mapped to itself (identity mapping).

This gives Tier 1 lookups a strong starting point.

Run once:  python -m engine.mappings.seed
"""

import json
from pathlib import Path

from engine.aliases import nba, nhl, ncaab, wncaab, nrl, soccer_mls

_MAP_DIR = Path(__file__).resolve().parent

_SPORTS = {
    "nba.json":            nba.ALIASES,
    "nhl.json":            nhl.ALIASES,
    "ncaab.json":          ncaab.ALIASES,
    "wncaab.json":         wncaab.ALIASES,
    "nrl.json":            nrl.ALIASES,
    "soccer_usa_mls.json": soccer_mls.ALIASES,
}


def seed() -> None:
    for fname, aliases in _SPORTS.items():
        # Collect all variant → canonical pairs.
        # Use original-cased variants as keys (title-case the lowercase key).
        mapping: dict[str, str] = {}
        seen_canonicals: set[str] = set()

        for key_lower, canonical in aliases.items():
            seen_canonicals.add(canonical)

            # Recover a nicely-cased version of the key.
            # If the key matches the canonical (lowered), use the canonical casing.
            if key_lower == canonical.lower():
                nice_key = canonical
            else:
                nice_key = key_lower.title()
                # Fix common casing issues after .title()
                for fix_lower, fix_correct in [
                    ("Nc ", "NC "), ("Uc ", "UC "), ("Uic", "UIC"),
                    ("Lsu", "LSU"), ("Smu", "SMU"), ("Byu", "BYU"),
                    ("Ucla", "UCLA"), ("Unlv", "UNLV"), ("Utep", "UTEP"),
                    ("Vcu", "VCU"), ("Uab", "UAB"),
                    ("Usc ", "USC "), ("Uconn", "UConn"),
                    ("Nrl", "NRL"), ("Nba", "NBA"), ("Nhl", "NHL"),
                    ("Gsw", "GSW"), ("Okc", "OKC"),
                    ("St.", "St."), ("Mcneese", "McNeese"),
                ]:
                    nice_key = nice_key.replace(fix_lower, fix_correct)

            mapping[nice_key] = canonical

        # Also add identity mappings for all canonical names (Kalshi sometimes
        # uses the exact Odds API name in titles).
        for canon in seen_canonicals:
            if canon not in mapping:
                mapping[canon] = canon

        # Sort by key for readability
        sorted_mapping = dict(sorted(mapping.items(), key=lambda kv: kv[0].lower()))

        out_path = _MAP_DIR / fname
        with open(out_path, "w") as f:
            json.dump(sorted_mapping, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  Wrote {len(sorted_mapping):>4} entries → {out_path.name}")


if __name__ == "__main__":
    seed()
