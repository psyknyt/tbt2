import json

from datetime import date, timedelta, datetime
import math
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from zoneinfo import ZoneInfo

from app.config import settings
from app.clients.delta_api import DeltaApi
from app.clients.tbt import TbtApi
from app.schemas import (
    CancelOrderRequest,
    OrderLevelRequest,
    PlaceOrderRequest,
    UpdateOrderRequest,
)
from app.helpers.helper import get_trade_strikes


def is_allowed_time():
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    return True
    # return 5 <= now.hour < 6

router = APIRouter()

@router.get("/")
def read_root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "ok",
    }


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@router.get("/getProducts")
async def get_products(symbol: str | None = None) -> dict:
    try:
        return await DeltaApi().get_product(symbol)
    except Exception as e:
        print("Exception occured: ", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/option-chain")
async def get_option_chain(
    underlying_asset_symbol: str = "ETH",
    expiry_date: str = None,
    contract_types: str = "call_options,put_options",
) -> dict:
    try:    
        if not expiry_date:
            expiry_date = datetime.today()
            
        return await DeltaApi().get_option_chain(
            underlying_asset_symbol=underlying_asset_symbol,
            expiry_date=expiry_date,
            contract_types=contract_types,
        )
    except Exception as e:
        print("Exception occured: ", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/day-high-low")
async def get_day_high_low(
    symbol: str,
    trading_date: date | None = None,
    tz: str = "Asia/Kolkata",
    resolution: str = "5m",
) -> dict:
    try:
        api = DeltaApi()
        if trading_date is None:
            return await api.get_previous_day_high_low(
                symbol=symbol,
                tz=tz,
                resolution=resolution,
            )
        return await api.get_day_high_low(
            symbol=symbol,
            trading_date=trading_date,
            tz=tz,
            resolution=resolution,
        )
    except Exception as e:
        
        print("Exception occured: ", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders")
async def place_order(order: PlaceOrderRequest) -> dict:
    try:
        return await DeltaApi().place_order(order.model_dump(exclude_none=True))
    except Exception as e:
        print("Exception occured: ", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders/dry-run")
async def dry_run_place_order(order: PlaceOrderRequest) -> dict:
    return {
        "dry_run": True,
        "message": "Order validated locally. No request was sent to Delta.",
        "payload": order.model_dump(exclude_none=True),
    }


@router.get("/delta-auth-debug")
async def delta_auth_debug() -> dict:
    return DeltaApi().auth_diagnostics()


@router.post("/order-levels")
async def find_order_levels(request: OrderLevelRequest) -> dict:
    try:
        return await TbtApi().find_order_levels(request.model_dump(exclude_none=True))
    except Exception as e:
        print("Exception occured: ", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/order-levels/dry-run")
async def dry_run_find_order_levels(request: OrderLevelRequest) -> dict:
    return {
        "dry_run": True,
        "message": "Order/level request validated locally. No request was sent.",
        "payload": request.model_dump(exclude_none=True),
    }


@router.get("/order-levels-debug")
async def order_levels_debug() -> dict:
    return TbtApi().diagnostics()


@router.delete("/orders")
async def cancel_order(order: CancelOrderRequest) -> dict:
    try:
        return await DeltaApi().cancel_order(order.model_dump(exclude_none=True))
    except Exception as e:
        print("Exception occured: ", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/orders")
async def update_order(order: UpdateOrderRequest) -> dict:
    try:
        return await DeltaApi().update_order(order.model_dump(exclude_none=True))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/levels")
async def levels(
    symbol: str,
    trading_date: Optional[date] = None,
) -> dict:
    try:
        api = DeltaApi()
        
        if not trading_date:
            trading_date = datetime.today()

        previous_day = trading_date - timedelta(days=1)

        # Previous day's OHLC
        try:    
            previous = await api.get_day_high_low(
                symbol=symbol,
                trading_date=previous_day,
                resolution="1d",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str("couldn't get ohlc"))

        # Trading day's OHLC
        try: 
            current = await api.get_day_high_low(
                symbol=symbol,
                trading_date=trading_date,
                resolution="1d",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str("couldn't get TRADING DAY ohlc"))
    
        prev_high = previous.get("high")
        prev_low = previous.get("low")
        today_open = current.get("open")
        

        if prev_high is None or prev_low is None or today_open is None:            
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Missing OHLC value",
                    "symbol": symbol,
                    "trading_date": trading_date.isoformat(),
                    "previous_ohlc": previous,
                    "current_ohlc": current,
                },
            )

        prev_high = float(prev_high)
        prev_low = float(prev_low)
        today_open = float(today_open)

        factor = 0.2611
        val_factor = 100
        
        points = (prev_high - prev_low) * factor
        
        closest_stike = get_trade_strikes(today_open, 20);
        
        return {
            "symbol": symbol,
            "trading_date": trading_date.isoformat(),
            "previous_day": previous_day.isoformat(),
            "flat": points <= val_factor,
            "points_range": round(points, 2),
            "previous_day_high": prev_high,
            "previous_day_low": prev_low,
            "today_open": today_open,
            "open_price": round(today_open, 2),
            "bullish_above": round(today_open + points, 2),
            "bearish_below": round(today_open - points, 2),
            **closest_stike
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/shazam")
async def shazam(
    symbol: str =  'ETHUSD',
    trading_date: Optional[date] = None,
    expiry_date:  Optional[str] = None,
    quantity: int = 100,
):
    if not is_allowed_time():
        raise HTTPException(
            status_code=403,
            detail="Trading is only allowed between 5 AM and 6 AM"
        )

    try:
        api = DeltaApi()
        
        if not trading_date:
            trading_date = datetime.today()

        if not expiry_date:
            expiry_date = date.today()

        levels_data = await levels(
            symbol=symbol,
            trading_date=trading_date,
        )

        if levels_data["flat"]:
            product = await api.get_tickers(symbol)

            underlying_asset_symbol = product["result"]["underlying_asset_symbol"]

            current_price = float(product["result"]["spot_price"])

            if isinstance(expiry_date, str):
                expiry_date = datetime.strptime(
                    expiry_date, "%Y-%m-%d"
                ).date()

            expiry_date = expiry_date.strftime("%d-%m-%Y")
            
            try:
                chain = await api.get_option_chain(
                    underlying_asset_symbol=underlying_asset_symbol,
                    expiry_date=expiry_date,
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
            options = chain["result"]
            
            
            calls = [
                option
                for option in options
                if option["contract_type"] == "call_options"
            ]

            puts = [
                option
                for option in options
                if option["contract_type"] == "put_options"
            ]
            
            # Find closest strike irrespective of CE/PE
            all_strikes = sorted(
                {
                    float(option["strike_price"])
                    for option in options
                }
            )
            closest_strike = min(
                all_strikes,
                key=lambda strike: abs(strike - current_price)
            )

            # First strike ABOVE closest strike
            call_strike = min(
                (
                    strike
                    for strike in all_strikes
                    if strike > closest_strike
                ),
                default=closest_strike,
            )

            # First strike BELOW closest strike
            put_strike = max(
                (
                    strike
                    for strike in all_strikes
                    if strike < closest_strike
                ),
                default=closest_strike,
            )

            closest_call = next(
                option
                for option in calls
                if float(option["strike_price"]) == call_strike
            )

            closest_put = next(
                option
                for option in puts
                if float(option["strike_price"]) == put_strike
            )
            
            # closest_call = min(
            #     calls,
            #     key=lambda x: abs(
            #         float(x["strike_price"]) - current_price
            #     ),
            # )

            # closest_put = min(
            #     puts,
            #     key=lambda x: abs(
            #         float(x["strike_price"]) - current_price
            #     ),
            # )

            selected = (
                closest_call,
                closest_put
            )


            order = []
            for i in selected:
            #    ordr = await api.place_order(
            #         {
            #             "product_id": i["product_id"],
            #             "size": quantity,
            #             "side": "buy",
            #             "order_type": "market_order",
            #         }
            #     )
            #    order.append(ordr)
            
             return {
               "obj": '' 
            }

            return {
                "trade": True,
                "current_price": current_price,
                "levels": levels_data,
                "selected_option": [
                    {
                        "symbol": option.get("symbol"),
                        "strike": option.get("strike_price"),
                        "premium": option.get("mark_price"),
                        "product_id": option.get("product_id"),
                    }
                    for option in selected
                ],  
                "order": order,
            }

        return {
            "trade": "flat"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.post("/backtest")
async def backtest(
    symbol: str,
    quantity: int = 100,
    days: int = 400,
):
    api = DeltaApi()

    results = []
    cumulative_pnl = 0

    for i in range(days):
        trading_date = date.today() - timedelta(days=i)

        try:
            levels_data = await levels(
                symbol=symbol,
                trading_date=trading_date,
            )

            # Only trade flat days
            if not levels_data["flat"]:
                continue

            # Same-day expiry
            expiry_date = trading_date.strftime("%d-%m-%Y")
            
            call_strike = 'C'- f'{symbol}' - levels_data.call_strike- f'{expiry_date}' 
            put_strike = 'C'- f'{symbol}' - levels_data.put_strike- f'{expiry_date}' 


            selected = (
                call_strike,
                put_strike,
            )

            daily_pnl = 0
            trade_results = []

            for option in selected:
                option_ohlc = await api.get_day_high_low(
                    symbol=option["symbol"],
                    trading_date=expiry_date,
                    resolution="1d",
                )

                entry = float(option_ohlc["open"])
                high = float(option_ohlc["high"])
                close = float(option_ohlc["close"])

                tp = entry * 3

                if high >= tp:
                    exit_price = tp
                    tp_hit = True
                else:
                    exit_price = close
                    tp_hit = False

                pnl = (
                    exit_price - entry
                ) * quantity

                daily_pnl += pnl

                trade_results.append(
                    {
                        "symbol": option["symbol"],
                        "entry": round(entry, 2),
                        "high": round(high, 2),
                        "close": round(close, 2),
                        "tp": round(tp, 2),
                        "exit": round(exit_price, 2),
                        "tp_hit": tp_hit,
                        "pnl": round(pnl, 2),
                    }
                )

            cumulative_pnl += daily_pnl

            results.append(
                {
                    "date": trading_date.isoformat(),
                    "daily_pnl": round(daily_pnl, 2),
                    "cumulative_pnl": round(cumulative_pnl, 2),
                    "trades": trade_results,
                }
            )

        except Exception as e:
            print(
                f"Skipping la {trading_date}: {e}",
                flush=True,
            )

    total_trades = sum(
        len(day["trades"])
        for day in results
    )

    wins = sum(
        1
        for day in results
        for trade in day["trades"]
        if trade["pnl"] > 0
    )

    losses = total_trades - wins
    
    summary = {
        "days_tested": days,
        "days_traded": len(results),
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round(
            wins / total_trades * 100,
            2,
        ) if total_trades else 0,
        "total_pnl": round(
            cumulative_pnl,
            2,
        ),
        "results": results,
    }

    # Create directory if it doesn't exist
    Path("backtest_results").mkdir(
        parents=True,
        exist_ok=True,
    )

    filename = (
        f"backtest_results/"
        f"{symbol}_{days}days_"
        f"{datetime.now():%Y%m%d_%H%M%S}.json"
    )

    with open(
        filename,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            summary,
            f,
            indent=4,
            ensure_ascii=False,
        )

    summary["saved_to"] = filename

    return summary

@router.post("/backtest2")
async def backtest(
    symbol: str,
    quantity: int = 100,
    days: int = 400,
):
    api = DeltaApi()
    results = []
    cumulative_pnl = 0
    
    for i in range(days):
        trading_date = (date.today() - timedelta(days=i))

        try:
            try:                
                levels_data = await levels(
                    symbol=symbol,
                    trading_date=trading_date,
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

            # Only trade flat days
            if levels_data.get("flat"):
                # Same-day expiry
                
                expiry_date = trading_date.strftime("%d-%m-%y").replace('-', '')
                                
                product_data = await api.get_product(symbol)
                # return product_data
                            
                if product_data["success"]:
                    product_symbol=product_data["result"]["underlying_asset"]["symbol"]
                else:
                    break
                
                call_strike = f"C-{product_symbol}-{levels_data['call_strike']}-{expiry_date}"
                put_strike = f"P-{product_symbol}-{levels_data['put_strike']}-{expiry_date}"

                # Fixed: Changed from dot-notation to dictionary lookups
                selected = (
                    call_strike,
                    put_strike,
                )
                
                if not all(selected):
                    continue

                daily_pnl = 0
                trade_results = []

                for option in selected:
                    try:     
                        option_ohlc = await api.get_day_high_low(
                            symbol=option,
                            trading_date=trading_date,
                            resolution="1d",
                        )
                    except Exception as e:
                        raise HTTPException(status_code=500, detail=str(f"Eror occred: {e}"))
                    
                    
                    if option_ohlc:
                        entry = float(option_ohlc["open"])
                        high = float(option_ohlc["high"])
                        close = float(option_ohlc["close"])
                    else:
                        continue
                    
                    tp = high
                    
                    if entry > 0 and entry < 5:
                        if high >= tp:
                            exit_price = tp
                            tp_hit = True
                            rcrd = {tp: tp, high: high}
                        else:
                            exit_price = close
                            tp_hit = False
                            rcrd = {tp: tp, high: high}


                        pnl = (exit_price - entry) * (quantity/100)
                        daily_pnl += pnl
                        
                        trade_results.append({
                            "symbol": option_ohlc["symbol"],
                            "entry": round(entry, 2),
                            "high": round(high, 2),
                            "close": round(close, 2),
                            "tp": round(tp, 2),
                            "exit": round(exit_price, 2),
                            "tp_hit": tp_hit,
                            "pnl": round(pnl, 2),
                            "rcrd": rcrd
                        })
                    else:
                        tp_hit = "option not in our price zone. i.e less than 5"
                        trade_results.append({
                            "symbol": option_ohlc["symbol"],
                            "entry": round(entry, 2),
                            "high": round(high, 2),
                            "close": round(close, 2),
                            "tp": round(tp, 2),
                            "exit": round(exit_price, 2),
                            "tp_hit": tp_hit,
                            "pnl": round(pnl, 2),
                        })
                cumulative_pnl += daily_pnl

                # Formulate the explicit daily record
                day_record = {
                    "date": trading_date.isoformat(),
                    "daily_pnl": round(daily_pnl, 2),
                    "cumulative_pnl": round(cumulative_pnl, 2),
                    "trades": trade_results,
                    **levels_data
                }

                # --- PROCESS INDIVIDUAL DAY RECORD ---
                # You can pipe `day_record` straight to a database, 
                # stream it to a UI via websockets, or write to an independent log line here.
                # -------------------------------------
                
                results.append(day_record)

        except Exception as e:
            print(
                f"Skipping za {trading_date}: {e}",
                flush=True,
            )
    # return results
    # Compute high-level summary aggregates
    # total_trades = sum(len(day["trades"]) for day in results)
    # wins = sum(1 for day in results for trade in day["trades"] if trade["daily_pnl"] > 0)
    # losses = total_trades - wins
    
    total_trades = sum(
        1 for day in results 
        for trade in day["trades"] 
        if "pnl" in trade
    )

    # Calculate wins using the correct dict key 'pnl'
    wins = sum(
        1 for day in results 
        for trade in day["trades"] 
        if "pnl" in trade and trade["pnl"] > 0
    )

    losses = total_trades - wins
    
    summary = {
        "days_tested": days,
        "days_traded": len(results),
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / total_trades * 100, 2) if total_trades else 0,
        "total_pnl": round(cumulative_pnl, 2),
        "results": results,  # Holds the array of individual daily records
    }

    # File persistency backup
    Path("backtest_results").mkdir(parents=True, exist_ok=True)
    filename = f"backtest_results/{symbol}_{days}days_{datetime.now():%Y%m%d_%H%M%S}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4, ensure_ascii=False)

    summary["saved_to"] = filename

    return summary

@router.post("/backtest3")
async def backtest3(
    symbol: str,
    quantity: int = 100,
    days: int = 100,
):
    api = DeltaApi()
    results = []
    cumulative_pnl = 0.0
    skipped_trades = 0

    # Fetch product information once
    product_data = await api.get_product(symbol)

    if not product_data or not product_data.get("success"):
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch product information for {symbol}",
        )

    try:
        product_symbol = product_data["result"]["underlying_asset"]["symbol"]
    except (KeyError, TypeError):
        raise HTTPException(
            status_code=502,
            detail=f"Invalid product response for {symbol}",
        )

    for i in range(days):
        trading_date = date.today() - timedelta(days=i)

        try:
            levels_data = await levels(
                symbol=symbol,
                trading_date=trading_date,
            )

            if not levels_data.get("flat"):
                continue

            expiry_date = trading_date.strftime("%d-%m-%y").replace("-", "")

            selected = [
                f"C-{product_symbol}-{levels_data['call_strike']}-{expiry_date}",
                f"P-{product_symbol}-{levels_data['put_strike']}-{expiry_date}",
            ]

            daily_pnl = 0.0
            trade_results = []

            for option in selected:
                try:
                    option_ohlc = await api.get_day_high_low(
                        symbol=option,
                        trading_date=trading_date,
                        resolution="1d",
                    )

                    if not option_ohlc:
                        skipped_trades += 1
                        trade_results.append({
                            "symbol": option,
                            "status": "skipped",
                            "reason": "No OHLC data",
                        })
                        continue

                    # Validate OHLC values before converting
                    raw_open = option_ohlc.get("open")
                    raw_high = option_ohlc.get("high")
                    raw_close = option_ohlc.get("close")

                    if any(
                        value is None for value in
                        (raw_open, raw_high, raw_close)
                    ):
                        skipped_trades += 1
                        trade_results.append({
                            "symbol": option,
                            "status": "skipped",
                            "reason": "Missing OHLC value",
                        })
                        continue

                    entry = float(raw_open)
                    high = float(raw_high)
                    close = float(raw_close)

                    if not all(
                        math.isfinite(value)
                        for value in (entry, high, close)
                    ):
                        skipped_trades += 1
                        trade_results.append({
                            "symbol": option,
                            "status": "skipped",
                            "reason": "Invalid OHLC value",
                        })
                        continue

                    # Preserve your premium entry filter
                    if not 0 < entry < 10:
                        skipped_trades += 1
                        trade_results.append({
                            "symbol": option_ohlc.get("symbol", option),
                            "status": "skipped",
                            "reason": "Entry premium must be greater than 0 and less than 5",
                            "entry": round(entry, 2),
                            "high": round(high, 2),
                            "close": round(close, 2),
                        })
                        continue

                    # Predefined target: 3x entry premium
                    tp = 20 * entry

                    if high >= tp:
                        exit_price = tp
                        tp_hit = True
                    else:
                        exit_price = close
                        tp_hit = False

                    pnl = (exit_price - entry) * (quantity / 100)
                    daily_pnl += pnl

                    trade_results.append({
                        "symbol": option_ohlc.get("symbol", option),
                        "status": "executed",
                        "entry": round(entry, 2),
                        "high": round(high, 2),
                        "close": round(close, 2),
                        "tp": round(tp, 2),
                        "exit": round(exit_price, 2),
                        "tp_hit": tp_hit,
                        "pnl": round(pnl, 2),
                    })

                except Exception as e:
                    skipped_trades += 1
                    print(
                        f"Skipping option {option} on {trading_date}: {e}",
                        flush=True,
                    )
                    trade_results.append({
                        "symbol": option,
                        "status": "skipped",
                        "reason": str(e),
                    })

            cumulative_pnl += daily_pnl
            principle = (quantity / 100) * entry

            # Count a day as traded only if at least one trade executed
            executed_count = sum(
                trade.get("status") == "executed"
                for trade in trade_results
            )

            if executed_count:
                results.append({
                    "date": trading_date.isoformat(),
                    "daily_pnl": round(daily_pnl, 2),
                    "cumulative_pnl": round(cumulative_pnl, 2),
                    "trades": trade_results,
                    **levels_data,
                })

        except Exception as e:
            print(
                f"Skipping date {trading_date}: {e}",
                flush=True,
            )
            continue

    executed_trades = [
        trade
        for day in results
        for trade in day["trades"]
        if trade.get("status") == "executed"
    ]

    total_trades = len(executed_trades)
    wins = sum(trade["pnl"] > 0 for trade in executed_trades)
    losses = sum(trade["pnl"] < 0 for trade in executed_trades)
    breakeven = sum(trade["pnl"] == 0 for trade in executed_trades)

    summary = {
        "symbol": symbol,
        "days_tested": days,
        "days_traded": len(results),
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "breakeven": breakeven,
        "skipped_trades": skipped_trades,
        "win_rate": round(wins / total_trades * 100, 2)
        if total_trades else 0,
        "total_pnl": round(cumulative_pnl, 2),
        "results": results,
    }

    Path("backtest_results").mkdir(parents=True, exist_ok=True)

    filename = (
        f"backtest_results/"
        f"{symbol}_{days}days_backtest3_"
        f"{datetime.now():%Y%m%d_%H%M%S}.json"
    )

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4, ensure_ascii=False)

    summary["saved_to"] = filename

    return summary