from shared.selection import select_winner
from shared.models import Scorecard


def test_select_winner_picks_highest_sharpe():
    cards = [
        Scorecard(strategy_id="a", sharpe=1.0, max_drawdown=0.15, roi=0.2),
        Scorecard(strategy_id="b", sharpe=1.5, max_drawdown=0.20, roi=0.18),
        Scorecard(strategy_id="c", sharpe=1.5, max_drawdown=0.10, roi=0.15),
    ]
    winner = select_winner(cards)
    # ties on sharpe broken by lowest drawdown
    assert winner.strategy_id == "c"


def test_select_winner_ignores_errored():
    cards = [
        Scorecard(strategy_id="a", error="boom"),
        Scorecard(strategy_id="b", sharpe=0.5, max_drawdown=0.2),
    ]
    winner = select_winner(cards)
    assert winner.strategy_id == "b"


def test_select_winner_raises_when_all_errored():
    import pytest
    cards = [Scorecard(strategy_id="a", error="boom"), Scorecard(strategy_id="b", error="boom2")]
    with pytest.raises(ValueError, match="no successful backtests"):
        select_winner(cards)
