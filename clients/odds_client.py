import requests
from typing import Optional

import config


class OddsClient:
    """
    Client for The Odds API (https://the-odds-api.com).

    Retrieves moneyline (h2h) odds from sportsbooks and tracks the monthly
    request quota so you don't accidentally burn through the free tier.

    Free tier: 500 requests/month.
    Tip: cache responses locally if you're polling frequently.
    """

    def __init__(self):
        self.api_key = config.ODDS_API_KEY
        self.base_url = config.ODDS_API_BASE_URL
        self._requests_remaining: Optional[int] = None
        self._requests_used: Optional[int] = None

    # ─── Quota tracking ───────────────────────────────────────────────────────

    @property
    def requests_remaining(self) -> Optional[int]:
        return self._requests_remaining

    def _update_quota(self, headers: dict) -> None:
        if "x-requests-remaining" in headers:
            self._requests_remaining = int(headers["x-requests-remaining"])
        if "x-requests-used" in headers:
            self._requests_used = int(headers["x-requests-used"])

    # ─── Endpoints ────────────────────────────────────────────────────────────

    def get_sports(self) -> list[dict]:
        """List all available sports and whether they are currently in season."""
        resp = requests.get(
            f"{self.base_url}/sports",
            params={"apiKey": self.api_key},
            timeout=10,
        )
        resp.raise_for_status()
        self._update_quota(resp.headers)
        return resp.json()

    def get_odds(
        self,
        sport: str,
        bookmakers: Optional[list[str]] = None,
        markets: str = "h2h",
        regions: str = "us",
        odds_format: str = "american",
        event_ids: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Fetch current moneyline odds for all upcoming games in a sport.

        Args:
            sport:       Sport key, e.g. "basketball_nba", "americanfootball_nfl"
            bookmakers:  List of bookmaker keys to request. Defaults to SHARP_BOOKS.
                         Examples: ["pinnacle"], ["pinnacle", "draftkings"]
            markets:     "h2h" (moneyline), "spreads", or "totals". Default h2h.
            regions:     "us", "uk", "eu", "au"
            odds_format: "american" or "decimal"
            event_ids:   Optional list of Odds API event IDs to target specific games.

        Returns:
            List of game dicts, each containing:
                id, sport_key, sport_title, commence_time,
                home_team, away_team, bookmakers[].markets[].outcomes[]
        """
        if bookmakers is None:
            bookmakers = config.SHARP_BOOKS

        params: dict = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
            "bookmakers": ",".join(bookmakers),
        }
        if event_ids:
            params["eventIds"] = ",".join(event_ids)

        resp = requests.get(
            f"{self.base_url}/sports/{sport}/odds",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        self._update_quota(resp.headers)

        return resp.json()

    def _safe_error(self, e: requests.HTTPError) -> str:
        """Return an error string with the API key redacted from the URL."""
        msg = str(e)
        if self.api_key and self.api_key in msg:
            msg = msg.replace(self.api_key, "***")
        return msg

    def get_live_odds(self, sport: str, event_ids: list[str]) -> list[dict]:
        """
        Fetch live in-progress odds for specific events using live-friendly books.

        Uses LIVE_SHARP_BOOKS (DraftKings, FanDuel) since Pinnacle does not
        offer live odds via The Odds API.

        Args:
            sport:      Sport key, e.g. "basketball_nba"
            event_ids:  List of Odds API event IDs for in-progress games.

        Returns:
            List of raw game dicts (same schema as get_odds), or [] if none found.
        """
        if not event_ids:
            return []
        try:
            return self.get_odds(
                sport,
                bookmakers=config.LIVE_SHARP_BOOKS,
                event_ids=event_ids,
            )
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                remaining = self._requests_remaining
                if remaining is not None and remaining == 0:
                    print(f"[OddsAPI] ⚠ Quota exhausted — live odds unavailable for {sport}. Falling back to pre-game lines.")
                else:
                    print(f"[OddsAPI] ⚠ Rate limited (429) for {sport} live odds. Falling back to pre-game lines.")
            else:
                print(f"[OddsAPI] Live odds fetch failed for {sport}: {self._safe_error(e)}")
            return []

    def get_all_sports_odds(self) -> list[dict]:
        """
        Fetch moneyline odds for every sport in config.SPORTS.

        Requests all sharp + live bookmakers in a single call per sport so that
        normalization can pick the right book for pre-game vs in-progress games
        without a second API request.

        Silently skips any sport that returns an HTTP error (e.g. off-season).
        """
        all_books = list(dict.fromkeys(config.SHARP_BOOKS + config.LIVE_SHARP_BOOKS))
        # Add any extra books needed for sport-specific overrides
        for sport_books in config.SPORT_SHARP_BOOKS.values():
            for b in sport_books:
                if b not in all_books:
                    all_books.append(b)
        all_games: list[dict] = []
        for i, sport in enumerate(config.SPORTS):
            if i > 0:
                import time
                time.sleep(1)  # avoid 429 rate limiting between sport requests
            try:
                games = self.get_odds(sport, bookmakers=all_books)
                all_games.extend(games)
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    print(f"[OddsAPI] ⚠ Rate limited (429) — skipping remaining sports.")
                    break
                print(f"[OddsAPI] Skipping {sport}: {self._safe_error(e)}")
        if self._requests_remaining is not None:
            print(f"[OddsAPI] Quota remaining: {self._requests_remaining}")
        return all_games
