from temporalio import activity

from shared.models import DriftInput, DriftResult


def _check_drift_pure(inp: DriftInput) -> DriftResult:
    if inp.backtest_roi <= 0:
        return DriftResult(drifted=False, reason="no backtest ROI baseline")
    gap = (inp.backtest_roi - inp.live_roi) / abs(inp.backtest_roi)
    if gap > inp.threshold:
        return DriftResult(drifted=True,
                           reason=f"live ROI lags backtest by {gap*100:.0f}% (threshold {inp.threshold*100:.0f}%)")
    return DriftResult(drifted=False, reason=f"within tolerance ({gap*100:.0f}%)")


@activity.defn
async def check_drift(inp: DriftInput) -> DriftResult:
    return _check_drift_pure(inp)
