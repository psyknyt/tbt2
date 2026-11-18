import hashlib
import hmac
import json
import ssl
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import certifi
import httpx
import truststore

from app.config import settings


class DeltaApi:
    def __init__(self) -> None:
        self.base_url = settings.app_delta_base_url.strip().rstrip("/")
        self.api_key = settings.app_delta_api_key.strip()
        self.api_secret = settings.app_delta_api_secret.strip()
        self.api_prefix = self._api_prefix()
        self.origin_url = self._origin_url()
        self.ssl_context = self._create_ssl_context()

    def _create_ssl_context(self) -> ssl.SSLContext:
        try:
            return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except Exception:
            return ssl.create_default_context(cafile=certifi.where())

    def _api_prefix(self) -> str:
        base_path = urlsplit(self.base_url).path.rstrip("/")
        return base_path if base_path else "/v2"

    def _origin_url(self) -> str:
        parsed = urlsplit(self.base_url)
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))

    def _request_path(self, path: str) -> str:
        return f"{self.api_prefix}{path}"

    def _signature(self, message: str) -> str:
        return hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _auth_headers(
        self,
        method: str,
        path: str,
        payload: str = "",
        query_string: str = "",
    ) -> dict[str, str]:
        if not self.api_key or not self.api_secret:
            raise ValueError("Delta API key and secret are required for order endpoints")

        timestamp = str(int(time.time()))
        request_path = self._request_path(path)
        signature_data = method.upper() + timestamp + request_path + query_string + payload

        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "python-fastapi-delta-client",
            "api-key": self.api_key,
            "signature": self._signature(signature_data),
            "timestamp": timestamp,
        }

    def auth_diagnostics(self) -> dict[str, str | int | bool]:
        return {
            "base_url": self.base_url,
            "origin_url": self.origin_url,
            "api_prefix": self.api_prefix,
            "api_key_loaded": bool(self.api_key),
            "api_key_length": len(self.api_key),
            "api_key_preview": self._mask(self.api_key),
            "api_secret_loaded": bool(self.api_secret),
            "api_secret_length": len(self.api_secret),
            "server_utc_time": datetime.now(timezone.utc).isoformat(),
            "timestamp": int(time.time()),
        }

    def _mask(self, value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}...{value[-4:]}"

    def _timezone(self, tz: str):
        try:
            return ZoneInfo(tz)
        except ZoneInfoNotFoundError:
            if tz in {"Asia/Kolkata", "Asia/Calcutta"}:
                return timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
            raise ValueError(
                f"Timezone '{tz}' is not available. Install the 'tzdata' package "
                "or use Asia/Kolkata."
            )

    async def _authenticated_request(
        self,
        method: str,
        path: str,
        body: dict,
    ) -> dict:
        payload = json.dumps(body, separators=(",", ":"))
        request_path = self._request_path(path)
        print(body)
        async with httpx.AsyncClient(
            base_url=self.origin_url,
            timeout=10,
            verify=self.ssl_context,
        ) as client:
            response = await client.request(
                method,
                request_path,
                content=payload,
                headers=self._auth_headers(method, path, payload=payload),
            )
            # return self._auth_headers(method, path, payload=payload)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise httpx.HTTPStatusError(
                    f"{exc}. Delta response: {response.text}",
                    request=exc.request,
                    response=exc.response,
                ) from exc
            return response.json()

    async def get_product(self, symbol: str | None = None) -> dict:
        async with httpx.AsyncClient(
            base_url=self.origin_url,
            timeout=10,
            verify=self.ssl_context,
        ) as client:
            if symbol:
                response = await client.get(f"{self.api_prefix}/products/{symbol}")
            else:
                response = await client.get(f"{self.api_prefix}/products")

            response.raise_for_status()
            return response.json()
     
    async def get_tickers(self, symbol: str | None = None) -> dict:
        async with httpx.AsyncClient(
            base_url=self.origin_url,
            timeout=10,
            verify=self.ssl_context,
        ) as client:
            if symbol:
                response = await client.get(f"{self.api_prefix}/tickers/{symbol}")
            else:
                response = await client.get(f"{self.api_prefix}/tickers")

            response.raise_for_status()
            return response.json()

    async def get_option_chain(
        self,
        underlying_asset_symbol: str,
        expiry_date: str,
        contract_types: str = "call_options,put_options",
    ) -> dict:
        async with httpx.AsyncClient(
            base_url=self.origin_url,
            timeout=10,
            verify=self.ssl_context,
        ) as client:
            response = await client.get(
                f"{self.api_prefix}/tickers",
                params={
                    "contract_types": contract_types,
                    "underlying_asset_symbols": underlying_asset_symbol,
                    "expiry_date": expiry_date,
                },
            )

            response.raise_for_status()
            return response.json()

    async def get_historical_candles(
        self,
        symbol: str,
        resolution: str,
        start: int,
        end: int,
    ) -> dict:
        async with httpx.AsyncClient(
            base_url=self.origin_url,
            timeout=10,
            verify=self.ssl_context,
        ) as client:
            response = await client.get(
                f"{self.api_prefix}/history/candles",
                params={
                    "symbol": symbol,
                    "resolution": resolution,
                    "start": start,
                    "end": end,
                },
            )
            

            response.raise_for_status()
            return response.json()

    async def get_day_high_low(
        self,
        symbol: str,
        trading_date: date,
        tz: str = "Asia/Kolkata",
        resolution: str = "5m",
    ) -> dict:
        market_tz = self._timezone(tz)
        start_dt = datetime.combine(trading_date, datetime.min.time(), tzinfo=market_tz)
        end_dt = start_dt + timedelta(days=1)

        data = await self.get_historical_candles(
            symbol=symbol,
            resolution=resolution,
            start=int(start_dt.timestamp()),
            end=int(end_dt.timestamp()),
        )
        
        candles = data.get("result", [])

        if not candles:
            return {
                "symbol": symbol,
                "date": trading_date.isoformat(),
                "timezone": tz,
                "resolution": resolution,
                "open": None,
                "close": None,
                "high": None,
                "low": None,
                "candle_count": 0,
            }

        highs = [float(candle["high"]) for candle in candles]
        lows = [float(candle["low"]) for candle in candles]
        close = [float(candle["close"]) for candle in candles]
        open = [float(candle["open"]) for candle in candles]


        return {
            "symbol": symbol,
            "date": trading_date.isoformat(),
            "timezone": tz,
            "resolution": resolution,
            "start": int(start_dt.timestamp()),
            "end": int(end_dt.timestamp()),
            "open": max(open),
            "high": max(highs),
            "low": min(lows),
            "close": max(close),
            "candle_count": len(candles),
        }

    async def get_previous_day_high_low(
        self,
        symbol: str,
        tz: str = "Asia/Kolkata",
        resolution: str = "5m",
    ) -> dict:
        market_tz = self._timezone(tz)
        previous_day = datetime.now(market_tz).date() - timedelta(days=1)
        return await self.get_day_high_low(
            symbol=symbol,
            trading_date=previous_day,
            tz=tz,
            resolution=resolution,
        )

    async def place_order(self, order: dict) -> dict:
        return await self._authenticated_request("POST", "/orders", order)

    async def cancel_order(self, order: dict) -> dict:
        return await self._authenticated_request("DELETE", "/orders", order)

    async def update_order(self, order: dict) -> dict:
        return await self._authenticated_request("PUT", "/orders", order)
