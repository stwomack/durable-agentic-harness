from .models import Scorecard


def select_winner(scorecards: list[Scorecard]) -> Scorecard:
    """Pick highest Sharpe; tiebreak by lowest max_drawdown."""
    valid = [s for s in scorecards if s.error is None]
    if not valid:
        raise ValueError("no successful backtests to choose from")
    valid.sort(key=lambda s: (-s.sharpe, s.max_drawdown))
    return valid[0]
