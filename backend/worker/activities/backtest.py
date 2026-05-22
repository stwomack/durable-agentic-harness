import asyncio
import json
import re

import docker
from temporalio import activity
from temporalio.exceptions import ApplicationError

from shared.models import BacktestInput, Scorecard
from shared.openai_client import make_openai_client
from shared.prompts import BACKTEST_PROMPT
from shared.settings import settings


@activity.defn
async def run_backtest_in_sandbox(inp: BacktestInput) -> Scorecard:
    activity.heartbeat({"strategy_id": inp.strategy_spec.id, "stage": "writing_code"})

    code = await _generate_backtest_code(inp)
    activity.heartbeat({"strategy_id": inp.strategy_spec.id, "stage": "executing"})

    try:
        stdout = await asyncio.get_event_loop().run_in_executor(
            None, _run_code_in_container, code, inp.historical_data_ref.path
        )
    except Exception as e:
        raise ApplicationError(f"sandbox execution failed: {e}", type="SandboxError")

    return _parse_scorecard(stdout, inp.strategy_spec.id, code)


async def _generate_backtest_code(inp: BacktestInput) -> str:
    client = make_openai_client()
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": BACKTEST_PROMPT},
            {"role": "user", "content": inp.strategy_spec.to_prompt()},
        ],
        temperature=0.3,
    )
    raw = response.choices[0].message.content or ""
    code = _extract_python_block(raw)
    if not code:
        raise ApplicationError("LLM did not produce a python code block",
                               type="LLMOutputError", non_retryable=True)
    return code


def _extract_python_block(text: str) -> str:
    m = re.search(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


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
