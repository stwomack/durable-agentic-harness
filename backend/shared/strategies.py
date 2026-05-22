from .models import StrategySpec


def default_candidate_strategies(n: int = 8) -> list[StrategySpec]:
    """Deterministic list of N candidate strategies covering 5 families."""
    base = [
        StrategySpec(id="rsi-14-30-70", family="RSI", params={"period": 14, "oversold": 30, "overbought": 70}),
        StrategySpec(id="macd-12-26-9", family="MACD", params={"fast": 12, "slow": 26, "signal": 9}),
        StrategySpec(id="ema-12-26", family="EMA_CROSS", params={"fast": 12, "slow": 26}),
        StrategySpec(id="ema-9-21", family="EMA_CROSS", params={"fast": 9, "slow": 21}),
        StrategySpec(id="bb-20-2", family="BOLLINGER", params={"period": 20, "std": 2.0}),
        StrategySpec(id="bb-10-1.5", family="BOLLINGER", params={"period": 10, "std": 1.5}),
        StrategySpec(id="mr-20", family="MEAN_REVERSION", params={"window": 20, "z_threshold": 1.5}),
        StrategySpec(id="rsi-7-25-75", family="RSI", params={"period": 7, "oversold": 25, "overbought": 75}),
    ]
    return base[:n]
