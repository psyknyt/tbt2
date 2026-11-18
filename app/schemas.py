from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


OrderSide = Literal["buy", "sell"]
OrderType = Literal["limit_order", "market_order"]
TimeInForce = Literal["gtc", "ioc"]
MmpMode = Literal["disabled", "mmp1", "mmp2", "mmp3", "mmp4", "mmp5"]


class PlaceOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int | None = None
    product_symbol: str | None = None
    size: int = Field(gt=0)
    side: OrderSide
    order_type: OrderType
    limit_price: str | None = None
    stop_order_type: Literal["stop_loss_order", "take_profit_order"] | None = None
    stop_price: str | None = None
    trail_amount: str | None = None
    stop_trigger_method: Literal["mark_price", "last_traded_price", "spot_price"] | None = None
    time_in_force: TimeInForce | None = "gtc"
    mmp: MmpMode | None = "disabled"
    post_only: bool | None = False
    reduce_only: bool | None = False
    client_order_id: str | None = Field(default=None, max_length=32)
    cancel_orders_accepted: bool | None = False

    @model_validator(mode="after")
    def validate_product_reference(self) -> "PlaceOrderRequest":
        if bool(self.product_id) == bool(self.product_symbol):
            raise ValueError("send exactly one of product_id or product_symbol")
        if self.order_type == "limit_order" and self.limit_price is None:
            raise ValueError("limit_price is required for limit_order")
        return self


class CancelOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    client_order_id: str | None = None
    product_id: int

    @model_validator(mode="after")
    def validate_order_reference(self) -> "CancelOrderRequest":
        if bool(self.id) == bool(self.client_order_id):
            raise ValueError("send exactly one of id or client_order_id")
        return self


class UpdateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    product_id: int | None = None
    product_symbol: str | None = None
    size: int = Field(gt=0)
    limit_price: str | None = None
    mmp: MmpMode | None = None
    post_only: bool | None = None
    stop_price: str | None = None
    trail_amount: str | None = None

    @model_validator(mode="after")
    def validate_product_reference(self) -> "UpdateOrderRequest":
        if bool(self.product_id) == bool(self.product_symbol):
            raise ValueError("send exactly one of product_id or product_symbol")
        return self


class OrderLevelRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str
    side: OrderSide | None = None
    price: float | None = None
    high: float | None = None
    low: float | None = None
    open: float | None = None
    close: float | None = None
    timeframe: str | None = None
    resolution: str | None = None
    strategy: str | None = None
    metadata: dict[str, Any] | None = None
