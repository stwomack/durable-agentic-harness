"""Deterministic per-strategy backtest code generator.

Returns a complete, self-contained Python script as a string. The script reads
the parquet OHLCV at `data_path`, runs the strategy implementation, and prints
a single JSON scorecard line as its LAST stdout line.

We hand-write these so the demo doesn't depend on the LLM producing correct
TA-Lib / pandas code on every call (it doesn't). The generated string is still
stored in the Scorecard so the War Room UI can show the executed code.
"""
from shared.models import StrategySpec


_HEADER = '''\
import json
import sys
import numpy as np
import pandas as pd
import talib

STRATEGY_ID = {strategy_id!r}
FAMILY = {family!r}
PARAMS = {params!r}
DATA_PATH = {data_path!r}

df = pd.read_parquet(DATA_PATH).sort_values("t").reset_index(drop=True)
close = df["c"].astype(float).to_numpy()
'''


_SIGNAL_BODIES = {
    "RSI": '''\
period = int(PARAMS.get("period", 14))
oversold = float(PARAMS.get("oversold", 30))
overbought = float(PARAMS.get("overbought", 70))
indicator = talib.RSI(close, timeperiod=period)
position = np.zeros(len(close), dtype=int)
pos = 0
for i in range(len(close)):
    if np.isnan(indicator[i]):
        position[i] = pos
        continue
    if pos == 0 and indicator[i] < oversold:
        pos = 1
    elif pos == 1 and indicator[i] > overbought:
        pos = 0
    position[i] = pos
''',
    "MACD": '''\
fast = int(PARAMS.get("fast", 12))
slow = int(PARAMS.get("slow", 26))
signal = int(PARAMS.get("signal", 9))
macd, sig, _ = talib.MACD(close, fastperiod=fast, slowperiod=slow, signalperiod=signal)
position = np.zeros(len(close), dtype=int)
pos = 0
for i in range(len(close)):
    if np.isnan(macd[i]) or np.isnan(sig[i]):
        position[i] = pos
        continue
    if pos == 0 and macd[i] > sig[i]:
        pos = 1
    elif pos == 1 and macd[i] < sig[i]:
        pos = 0
    position[i] = pos
''',
    "EMA_CROSS": '''\
fast = int(PARAMS.get("fast", 12))
slow = int(PARAMS.get("slow", 26))
ema_fast = talib.EMA(close, timeperiod=fast)
ema_slow = talib.EMA(close, timeperiod=slow)
position = np.zeros(len(close), dtype=int)
pos = 0
for i in range(len(close)):
    if np.isnan(ema_fast[i]) or np.isnan(ema_slow[i]):
        position[i] = pos
        continue
    if pos == 0 and ema_fast[i] > ema_slow[i]:
        pos = 1
    elif pos == 1 and ema_fast[i] < ema_slow[i]:
        pos = 0
    position[i] = pos
''',
    "BOLLINGER": '''\
period = int(PARAMS.get("period", 20))
std = float(PARAMS.get("std", 2.0))
upper, mid, lower = talib.BBANDS(close, timeperiod=period, nbdevup=std, nbdevdn=std)
position = np.zeros(len(close), dtype=int)
pos = 0
for i in range(len(close)):
    if np.isnan(lower[i]) or np.isnan(upper[i]):
        position[i] = pos
        continue
    if pos == 0 and close[i] < lower[i]:
        pos = 1
    elif pos == 1 and close[i] > upper[i]:
        pos = 0
    position[i] = pos
''',
    "MEAN_REVERSION": '''\
window = int(PARAMS.get("window", 20))
z_threshold = float(PARAMS.get("z_threshold", 1.5))
series = pd.Series(close)
sma = series.rolling(window).mean().to_numpy()
sd = series.rolling(window).std().to_numpy()
position = np.zeros(len(close), dtype=int)
pos = 0
for i in range(len(close)):
    if np.isnan(sma[i]) or np.isnan(sd[i]) or sd[i] == 0:
        position[i] = pos
        continue
    z = (close[i] - sma[i]) / sd[i]
    if pos == 0 and z < -z_threshold:
        pos = 1
    elif pos == 1 and z > 0:
        pos = 0
    position[i] = pos
''',
}


_FOOTER = '''\

# ───── PnL + scorecard ─────
returns = pd.Series(close).pct_change().fillna(0).to_numpy()
strategy_returns = np.roll(position, 1) * returns
strategy_returns[0] = 0.0

equity = np.cumprod(1 + strategy_returns)
roi = float(equity[-1] - 1) if len(equity) else 0.0
mean_r = float(np.mean(strategy_returns)) if len(strategy_returns) else 0.0
std_r = float(np.std(strategy_returns)) if len(strategy_returns) else 0.0
sharpe = float(mean_r / std_r * np.sqrt(252)) if std_r > 0 else 0.0

if len(equity):
    peak = np.maximum.accumulate(equity)
    dd = (peak - equity) / np.where(peak == 0, 1, peak)
    max_dd = float(np.max(dd))
else:
    max_dd = 0.0

trade_returns = []
entry_price = None
for i in range(len(position)):
    if position[i] == 1 and entry_price is None:
        entry_price = close[i]
    elif position[i] == 0 and entry_price is not None:
        trade_returns.append((close[i] - entry_price) / entry_price)
        entry_price = None

wins = sum(1 for r in trade_returns if r > 0)
win_rate = float(wins / len(trade_returns)) if trade_returns else 0.0
num_trades = len(trade_returns)

out = {
    "strategy_id": STRATEGY_ID,
    "roi": roi,
    "sharpe": sharpe,
    "max_drawdown": max_dd,
    "win_rate": win_rate,
    "num_trades": num_trades,
}
print(json.dumps(out))
'''


def build_backtest_code(strategy_spec: StrategySpec, data_path: str) -> str:
    """Compose a complete, deterministic backtest script for the given strategy."""
    body = _SIGNAL_BODIES.get(strategy_spec.family)
    if body is None:
        raise ValueError(f"unknown strategy family: {strategy_spec.family}")
    header = _HEADER.format(
        strategy_id=strategy_spec.id,
        family=strategy_spec.family,
        params=dict(strategy_spec.params),
        data_path=data_path,
    )
    return header + "\n" + body + _FOOTER
