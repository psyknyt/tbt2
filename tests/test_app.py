import asyncio
import hashlib
import hmac
from datetime import date

from fastapi.testclient import TestClient

from app.clients.delta_api import DeltaApi
from app.clients.tbt import TbtApi
from app.main import app


client = TestClient(app)


def test_root() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_delta_auth_headers_sign_prehashed_request(monkeypatch) -> None:
    monkeypatch.setattr("app.clients.delta_api.settings.app_delta_base_url", "https://cdn-ind.testnet.deltaex.org/v2")
    monkeypatch.setattr("app.clients.delta_api.settings.app_delta_api_key", "test-key")
    monkeypatch.setattr("app.clients.delta_api.settings.app_delta_api_secret", "test-secret")
    monkeypatch.setattr("app.clients.delta_api.time.time", lambda: 1781057169)

    api = DeltaApi()
    payload = (
        '{"product_symbol":"ETHUSD","size":1,"side":"buy","order_type":"limit_order",'
        '"limit_price":"100","time_in_force":"gtc","mmp":"disabled","post_only":false,'
        '"reduce_only":false,"cancel_orders_accepted":false}'
    )

    headers = api._auth_headers("POST", "/orders", payload=payload)

    signature_data = f"POST1781057169/v2/orders{payload}"
    expected_signature = hmac.new(
        b"test-secret",
        signature_data.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    assert headers["signature"] == expected_signature
    assert headers["signature"] != signature_data


def test_get_day_high_low_aggregates_intraday_candles(monkeypatch) -> None:
    async def fake_get_historical_candles(
        self,
        symbol: str,
        resolution: str,
        start: int,
        end: int,
    ) -> dict:
        assert symbol == "ETHUSD"
        assert resolution == "5m"
        assert start < end
        return {
            "result": [
                {"open": "99", "high": "100.5", "low": "98.1", "close": "100"},
                {"open": "100", "high": "104.25", "low": "99", "close": "103"},
                {"open": "103", "high": "101", "low": "97.75", "close": "98"},
            ]
        }

    monkeypatch.setattr(DeltaApi, "get_historical_candles", fake_get_historical_candles)

    result = asyncio.run(DeltaApi().get_day_high_low("ETHUSD", date(2026, 6, 10)))

    assert result["high"] == 104.25
    assert result["low"] == 97.75
    assert result["candle_count"] == 3


def test_order_levels_dry_run_allows_extra_strategy_fields() -> None:
    response = client.post(
        "/order-levels/dry-run",
        json={
            "symbol": "ETHUSD",
            "side": "buy",
            "price": 2500.5,
            "risk_reward": 2,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["payload"]["symbol"] == "ETHUSD"
    assert body["payload"]["risk_reward"] == 2


def test_tbt_api_validates_base_url(monkeypatch) -> None:
    monkeypatch.setattr("app.clients.tbt.settings.app_tbt_base_url", "")

    api = TbtApi()

    try:
        api._validate_base_url()
    except ValueError as exc:
        assert "APP_TBT_BASE_URL" in str(exc)
    else:
        raise AssertionError("Expected invalid TBT base URL to raise ValueError")
