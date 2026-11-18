
def get_trade_strikes(spot: float, interval: int = 20):
    closest = round(spot / interval) * interval

    return {
        "closest_strike": closest,
        "call_strike": closest + (2 * interval),
        "put_strike": closest - (2 * interval),
    }