from urllib.parse import urlsplit

import httpx

from app.config import settings


class TbtApi:
    def __init__(self) -> None:
        self.base_url = settings.app_tbt_base_url.strip().rstrip("/")
        self.order_level_path = self._normalize_path(settings.app_tbt_order_level_path)
        self.api_key = settings.app_tbt_api_key.strip()
        self.timeout = settings.app_tbt_timeout_seconds

    def _normalize_path(self, path: str) -> str:
        normalized = path.strip() or "/order-levels"
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        return normalized

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "python-fastapi-tbt-client",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _validate_base_url(self) -> None:
        parsed = urlsplit(self.base_url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("APP_TBT_BASE_URL must be set to your order/level API URL")

    def diagnostics(self) -> dict[str, str | int | bool | float]:
        return {
            "base_url": self.base_url,
            "order_level_path": self.order_level_path,
            "api_key_loaded": bool(self.api_key),
            "api_key_length": len(self.api_key),
            "api_key_preview": self._mask(self.api_key),
            "timeout_seconds": self.timeout,
        }

    def _mask(self, value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}...{value[-4:]}"

    async def find_order_levels(self, payload: dict) -> dict:
        self._validate_base_url()
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._headers(),
        ) as client:
            response = await client.post(self.order_level_path, json=payload)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise httpx.HTTPStatusError(
                    f"{exc}. Order/level API response: {response.text}",
                    request=exc.request,
                    response=exc.response,
                ) from exc

            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                return response.json()
            return {"raw": response.text}
