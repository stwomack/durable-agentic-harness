"""Helpers the LLM-written backtest code can import.

The LLM is instructed to print a JSON scorecard as the last line of stdout;
this module makes that easier by exposing a `print_scorecard(...)` helper.
"""
import json
import sys


def print_scorecard(strategy_id: str, *, roi: float, sharpe: float, max_drawdown: float,
                    win_rate: float, num_trades: int) -> None:
    out = {
        "strategy_id": strategy_id,
        "roi": roi,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "num_trades": num_trades,
    }
    sys.stdout.flush()
    print(json.dumps(out))
