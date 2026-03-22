import base64
import datetime
import time
import uuid
from urllib.parse import urlparse
import requests
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

import config

# Maps each Kalshi series ticker to the matching Odds API sport key.
# Used to tag raw market dicts so the matcher can enforce sport isolation.
_SERIES_TO_SPORT: dict[str, str] = {
    "KXNBAGAME": "basketball_nba",
    "KXNCAAMBGAME": "basketball_ncaab",
    "KXNCAAWBGAME": "basketball_wncaab",
    "KXNHLGAME": "icehockey_nhl",
    "KXRUGBYNRLMATCH": "rugbyleague_nrl",
    "KXMLSGAME": "soccer_usa_mls",
}


class KalshiClient:
    """
    Client for the Kalshi Trading API v2.

    Authentication uses RSA-PSS request signing (no session tokens):
      1. Generate an API key at kalshi.com/account/profile → API Keys
      2. Set KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH in your environment
      3. Each request is signed with: timestamp + HTTP_METHOD + path (no query string)

    Docs: https://docs.kalshi.com/getting_started/api_keys
    """

    def __init__(self):
        self.base_url = config.KALSHI_BASE_URL
        self.base_path = urlparse(self.base_url).path  # e.g. "/trade-api/v2"
        self._private_key = self._load_private_key()
        print("[Kalshi] RSA key loaded successfully.")

    # ─── Auth ─────────────────────────────────────────────────────────────────

    def _load_private_key(self):
        """Load the RSA private key from the path set in config."""
        path = config.KALSHI_PRIVATE_KEY_PATH
        if not path:
            raise ValueError(
                "KALSHI_PRIVATE_KEY_PATH is not set. "
                "Generate a key at kalshi.com/account/profile → API Keys."
            )
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )

    def _sign(self, method: str, path: str) -> dict[str, str]:
        """
        Build the three auth headers required by Kalshi for every request.

        Signature = RSA-PSS( SHA256, timestamp_ms + METHOD + /path/without/query )
        """
        ts_ms = str(int(datetime.datetime.now().timestamp() * 1000))
        # Strip query string before signing
        path_no_query = path.split("?")[0]
        msg = (ts_ms + method.upper() + path_no_query).encode("utf-8")

        sig = self._private_key.sign(
            msg,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        return {
            "KALSHI-ACCESS-KEY": config.KALSHI_API_KEY_ID,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode("utf-8"),
            "KALSHI-ACCESS-TIMESTAMP": ts_ms,
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        """Signed GET request. Path should start with /trade-api/v2/..."""
        url = self.base_url + path
        sign_path = self.base_path + path
        resp = requests.get(url, headers=self._sign("GET", sign_path), params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        """Signed POST request. Path should start with /trade-api/v2/..."""
        url = self.base_url + path
        sign_path = self.base_path + path
        resp = requests.post(url, headers=self._sign("POST", sign_path), json=body, timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ─── Markets ──────────────────────────────────────────────────────────────

    def get_markets(
        self,
        status: str = "open",
        limit: int = 200,
    ) -> list[dict]:
        """
        Fetch all active markets from Kalshi, handling cursor-based pagination.

        Returns a flat list of raw market dicts. Key price fields:
            yes_ask_dollars, yes_bid_dollars, no_ask_dollars, no_bid_dollars  (0.0–1.0)
            volume_fp, open_interest_fp, close_time, ticker, title, status
        """
        markets: list[dict] = []
        cursor: Optional[str] = None

        while True:
            params: dict = {"status": status, "limit": limit}
            if cursor:
                params["cursor"] = cursor

            data = self._get("/markets", params=params)
            batch: list[dict] = data.get("markets", [])
            markets.extend(batch)

            cursor = data.get("cursor")
            if not cursor or not batch:
                break

            time.sleep(0.5)  # avoid 429 rate limiting during pagination

        return markets

    def get_markets_for_series(self, series_ticker: str) -> list[dict]:
        """
        Fetch all open markets for a specific Kalshi series ticker.
        Much faster than fetching all markets — targets only the series we care about.
        """
        markets: list[dict] = []
        cursor: Optional[str] = None

        while True:
            params: dict = {"status": "open", "limit": 200, "series_ticker": series_ticker}
            if cursor:
                params["cursor"] = cursor

            data = self._get("/markets", params=params)
            batch: list[dict] = data.get("markets", [])
            markets.extend(batch)

            cursor = data.get("cursor")
            if not cursor or not batch:
                break

            time.sleep(0.3)

        return markets

    def get_sports_markets(self) -> list[dict]:
        """
        Fetch game-level moneyline markets for each configured Kalshi series,
        filtered by the MIN_VOLUME liquidity threshold.

        Each returned market dict has an injected '_sport_type' key (e.g.
        'basketball_nba') so the matcher can enforce sport isolation and avoid
        cross-sport false matches.

        Markets where expected_expiration_time is in the past are skipped —
        those games have already been played and prices are settlement values.
        """
        result = []
        now = datetime.datetime.now(datetime.timezone.utc)

        for series in config.KALSHI_SERIES:
            markets = self.get_markets_for_series(series)
            sport_type = _SERIES_TO_SPORT.get(series, "")
            for m in markets:
                volume = float(m.get("volume_fp", 0) or 0)
                if volume < config.MIN_VOLUME:
                    continue

                # Skip draw/tie-outcome contracts (NRL has 3-way markets;
                # -TIE contracts have no sportsbook h2h counterpart)
                if m.get("ticker", "").upper().endswith("-TIE"):
                    continue

                # Skip markets whose game has already been played
                exp_str = m.get("expected_expiration_time", "")
                if exp_str:
                    try:
                        exp_dt = datetime.datetime.fromisoformat(
                            exp_str.replace("Z", "+00:00")
                        )
                        if exp_dt < now:
                            continue  # game already over, prices are settlement values
                    except (ValueError, AttributeError):
                        pass

                m["_sport_type"] = sport_type  # tag for the matcher
                result.append(m)

        return result

    def get_market(self, ticker: str) -> dict:
        """Fetch a single market by ticker."""
        return self._get(f"/markets/{ticker}").get("market", {})

    def place_order(
        self,
        ticker: str,
        side: str,
        count: int,
        price_dollars: float,
    ) -> dict:
        """
        Place a limit buy order using immediate-or-cancel time in force.

        Args:
            ticker:        Kalshi market ticker (e.g. "KXNHLGAME-26MAR14NYRMIN-NYR")
            side:          "YES" or "NO" (case-insensitive)
            count:         Number of contracts to buy (>= 1)
            price_dollars: Limit price per contract, e.g. 0.09 for $0.09

        Returns:
            Raw order dict from the Kalshi API response.
        """
        side_lower = side.lower()
        price_str = f"{price_dollars:.4f}"
        body: dict = {
            "ticker": ticker,
            "side": side_lower,
            "action": "buy",
            "client_order_id": str(uuid.uuid4()),
            "count": count,
            "time_in_force": "immediate_or_cancel",
        }
        if side_lower == "yes":
            body["yes_price_dollars"] = price_str
        else:
            body["no_price_dollars"] = price_str

        return self._post("/portfolio/orders", body)

    # ─── Portfolio ────────────────────────────────────────────────────────────

    def get_settlements(self, limit: int = 200) -> list[dict]:
        """
        Fetch all portfolio settlement records from Kalshi, paginating until complete.

        Each record contains:
            ticker         — Kalshi market ticker
            market_result  — "yes", "no", or "void"
            revenue        — gross payout in cents (integer)
            fee_cost       — fees paid in dollars (string, e.g. "0.03")
            settled_time   — ISO-8601 UTC settlement timestamp
        """
        settlements: list[dict] = []
        cursor: Optional[str] = None

        while True:
            params: dict = {"limit": limit}
            if cursor:
                params["cursor"] = cursor

            data = self._get("/portfolio/settlements", params=params)
            batch: list[dict] = data.get("settlements", [])
            settlements.extend(batch)

            cursor = data.get("cursor")
            if not cursor or not batch:
                break

        return settlements

    def get_settlement_for_ticker(self, ticker: str) -> Optional[dict]:
        """
        Fetch the settlement record for a single specific ticker, if it exists.
        Returns None if the market has not been settled yet.
        """
        data = self._get("/portfolio/settlements", params={"ticker": ticker, "limit": 1})
        settlements = data.get("settlements", [])
        # Verify the record actually belongs to this ticker — if the API ignores
        # the ticker param it would return an unrelated settlement.
        if settlements and settlements[0].get("ticker") == ticker:
            return settlements[0]
        return None

    def get_fills(self, ticker: str, limit: int = 200) -> list[dict]:
        """
        Fetch all fill records for a specific ticker from the portfolio.

        Each fill record contains:
            action         — "buy" or "sell"
            side           — "yes" or "no"
            count_fp       — contracts filled (string, e.g. "5.00")
            yes_price_dollars / no_price_dollars — price per contract (string)
            fee_cost       — fees paid in dollars (string)
            created_time   — ISO-8601 UTC timestamp
            order_id       — associated order ID
        """
        fills: list[dict] = []
        cursor: Optional[str] = None

        while True:
            params: dict = {"ticker": ticker, "limit": limit}
            if cursor:
                params["cursor"] = cursor

            data = self._get("/portfolio/fills", params=params)
            batch: list[dict] = data.get("fills", [])
            fills.extend(batch)

            cursor = data.get("cursor")
            if not cursor or not batch:
                break

        return fills
