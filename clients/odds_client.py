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

    def get_events(
        self,
        sport: str,
        commence_time_from: Optional[str] = None,
        commence_time_to: Optional[str] = None,
    ) -> list[dict]:
        """
        List upcoming and live events for a sport.  **Zero quota cost.**

        Returns event stubs (id, home_team, away_team, commence_time) —
        no odds data.  Useful for checking whether a sport has any games
        on a given date before burning a paid /odds call.

        Args:
            sport:                Sport key, e.g. "basketball_nba"
            commence_time_from:   ISO-8601 lower bound (inclusive), e.g. "2026-04-02T00:00:00Z"
            commence_time_to:     ISO-8601 upper bound (inclusive), e.g. "2026-04-02T23:59:59Z"
        """
        params: dict = {"apiKey": self.api_key}
        if commence_time_from:
            params["commenceTimeFrom"] = commence_time_from
        if commence_time_to:
            params["commenceTimeTo"] = commence_time_to
        resp = requests.get(
            f"{self.base_url}/sports/{sport}/events",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        self._update_quota(resp.headers)
        return resp.json()

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

    def get_all_sports_odds(self, target_date: "date | None" = None) -> list[dict]:
        """
        Fetch moneyline odds for every sport in config.SPORTS.

        Requests all sharp + live bookmakers in a single call per sport so that
        normalization can pick the right book for pre-game vs in-progress games
        without a second API request.

        When *target_date* is provided the free ``/events`` endpoint is checked
        first for each sport.  Sports with zero events on that date are skipped,
        saving one paid quota credit each.

        Silently skips any sport that returns an HTTP error (e.g. off-season).
        """
        from datetime import datetime as _dt, timezone as _tz

        all_books = list(dict.fromkeys(config.SHARP_BOOKS + config.LIVE_SHARP_BOOKS))
        # Add any extra books needed for sport-specific overrides
        for sport_books in config.SPORT_SHARP_BOOKS.values():
            for b in sport_books:
                if b not in all_books:
                    all_books.append(b)

        # Build date window for free /events pre-check.  We widen the window
        # by ±1 day to account for UTC vs local-time edge cases (a game at
        # 11 PM ET on Apr 2 is Apr 3 in UTC).  The downstream date filter in
        # run_scan still applies the exact local-date match.
        events_from: str | None = None
        events_to:   str | None = None
        if target_date:
            from datetime import timedelta
            day_before = target_date - timedelta(days=1)
            day_after  = target_date + timedelta(days=1)
            events_from = f"{day_before.isoformat()}T00:00:00Z"
            events_to   = f"{day_after.isoformat()}T23:59:59Z"

        all_games: list[dict] = []
        paid_calls = 0
        skipped_sports: list[str] = []
        for i, sport in enumerate(config.SPORTS):
            # ── Free pre-check: skip sports with 0 events ──────────────
            if events_from and events_to:
                try:
                    events = self.get_events(sport, commence_time_from=events_from, commence_time_to=events_to)
                    if not events:
                        skipped_sports.append(sport)
                        continue
                except Exception:
                    pass  # if the free call fails, fall through to the paid call

            if paid_calls > 0:
                import time
                time.sleep(1)  # avoid 429 rate limiting between sport requests
            try:
                games = self.get_odds(sport, bookmakers=all_books)
                paid_calls += 1
                all_games.extend(games)
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    print(f"[OddsAPI] ⚠ Rate limited (429) — skipping remaining sports.")
                    break
                print(f"[OddsAPI] Skipping {sport}: {self._safe_error(e)}")
        if skipped_sports:
            print(f"[OddsAPI] Skipped {len(skipped_sports)} sport(s) with 0 events: {', '.join(skipped_sports)}")
        if self._requests_remaining is not None:
            print(f"[OddsAPI] Quota: {paid_calls} call(s) used this scan, {self._requests_remaining} remaining")
        return all_games
