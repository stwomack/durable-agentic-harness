from shared.models import DriftInput
from worker.activities.drift import _check_drift_pure


def test_no_drift_when_close():
    res = _check_drift_pure(DriftInput(baseline_sharpe=1.5, live_roi=0.18, backtest_roi=0.20, threshold=0.20))
    assert res.drifted is False


def test_drift_when_live_roi_lags():
    res = _check_drift_pure(DriftInput(baseline_sharpe=1.5, live_roi=0.10, backtest_roi=0.30, threshold=0.20))
    assert res.drifted is True
    assert "lag" in res.reason.lower() or "drift" in res.reason.lower()
