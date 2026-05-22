from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from shared.models import BacktestInput, Scorecard
    from worker.activities.backtest import run_backtest_in_sandbox


@workflow.defn
class BacktestSandboxWorkflow:
    @workflow.run
    async def run(self, inp: BacktestInput) -> Scorecard:
        try:
            return await workflow.execute_activity(
                run_backtest_in_sandbox,
                inp,
                start_to_close_timeout=timedelta(seconds=180),
                retry_policy=RetryPolicy(maximum_attempts=2),
                heartbeat_timeout=timedelta(seconds=30),
            )
        except Exception as e:
            return Scorecard(strategy_id=inp.strategy_spec.id, error=str(e)[:300])
