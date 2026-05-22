"""Run a backtest in an isolated Docker sandbox.

For demo reliability we use deterministic hand-written backtest scripts (see
`backtest_template.build_backtest_code`) instead of LLM-generated code. The
sandbox container, volume mount, and Scorecard contract are unchanged, so the
War Room UI behaviour is identical.
"""
import asyncio
import json

import docker
from temporalio import activity
from temporalio.exceptions import ApplicationError

from shared.models import BacktestInput, Scorecard
from shared.settings import settings
from worker.activities.backtest_template import build_backtest_code


@activity.defn
async def run_backtest_in_sandbox(inp: BacktestInput) -> Scorecard:
    activity.heartbeat({"strategy_id": inp.strategy_spec.id, "stage": "building_code"})
    try:
        code = build_backtest_code(inp.strategy_spec, inp.historical_data_ref.path)
    except ValueError as e:
        raise ApplicationError(str(e), type="UnknownStrategyFamily", non_retryable=True)

    activity.heartbeat({"strategy_id": inp.strategy_spec.id, "stage": "executing"})
    try:
        stdout = await asyncio.get_event_loop().run_in_executor(
            None, _run_code_in_container, code, inp.historical_data_ref.path
        )
    except Exception as e:
        raise ApplicationError(f"sandbox execution failed: {e}", type="SandboxError")

    return _parse_scorecard(stdout, inp.strategy_spec.id, code)


def _run_code_in_container(code: str, data_host_path: str) -> str:
    client = docker.from_env()
    container = client.containers.run(
        image=settings.sandbox_image,
        command=["python", "-c", code],
        volumes={"sandbox-data": {"bind": "/data", "mode": "ro"}},
        network_disabled=settings.sandbox_network_disabled,
        mem_limit="512m",
        nano_cpus=500_000_000,
        detach=True,
        remove=False,
    )
    try:
        result = container.wait(timeout=90)
        logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
        if result.get("StatusCode", 1) != 0:
            raise RuntimeError(f"sandbox exited non-zero: {result}\n{logs[-2000:]}")
        return logs
    finally:
        try:
            container.remove(force=True)
        except Exception:
            pass


def _parse_scorecard(stdout: str, strategy_id: str, generated_code: str) -> Scorecard:
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
            return Scorecard(
                strategy_id=str(data.get("strategy_id") or strategy_id),
                roi=float(data.get("roi", 0)),
                sharpe=float(data.get("sharpe", 0)),
                max_drawdown=float(data.get("max_drawdown", 0)),
                win_rate=float(data.get("win_rate", 0)),
                num_trades=int(data.get("num_trades", 0)),
                generated_code=generated_code,
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    return Scorecard(strategy_id=strategy_id, generated_code=generated_code,
                     error="no parseable scorecard in stdout")
