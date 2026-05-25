"""Temporal worker entrypoint.

Uses the `temporalio.contrib.openai_agents` plugin so that workflows can use
the OpenAI Agents SDK (`Agent`, `Runner`) directly inside workflow code — every
LLM call is auto-dispatched as a durable activity by the plugin.
"""
import asyncio
import logging
from datetime import timedelta

# Mute OpenAI SDK's own logging — the plugin handles trace/observability via Temporal.
logging.getLogger("openai").setLevel(logging.ERROR)
logging.getLogger("openai.agents").setLevel(logging.CRITICAL)

import structlog
from temporalio.client import Client
from temporalio.common import RetryPolicy
# OpenAIAgentsPlugin is the bridge between the OpenAI Agents SDK and Temporal.
# Once installed on the Client, any `Agent` + `Runner.run(...)` invoked inside
# workflow code transparently dispatches every LLM call as a Temporal activity —
# durable, retried, and recorded in the workflow's event history.
from temporalio.contrib.openai_agents import ModelActivityParameters, OpenAIAgentsPlugin
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from shared.settings import settings
from worker.workflows.hello import HelloWorkflow
from worker.workflows.backtest import BacktestSandboxWorkflow
from worker.workflows.parent import SelfEvolvingStockAgentWorkflow
from worker.activities.backtest import run_backtest_in_sandbox
from worker.activities.persist import persist_strategy, write_trade_record
from worker.activities.ui import notify_ui
from worker.activities.market import fetch_historical_data, fetch_market_snapshot
from worker.activities.news import fetch_news_snapshot
from worker.activities.risk import risk_check
from worker.activities.broker import place_order

# `call_agent` activity is gone — the trade-intent LLM call is now done inside
# the workflow via `Agent` + `Runner.run()`, dispatched as an activity by the plugin.

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(
    getattr(logging, settings.log_level.upper(), logging.INFO)))
log = structlog.get_logger("worker")


async def main() -> None:
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
        data_converter=pydantic_data_converter,
        plugins=[
            # `model_params` controls how each LLM call from the Agent is executed
            # as a Temporal activity: per-call timeout (60s), end-to-end deadline
            # including retries (180s), and an exponential-backoff retry policy.
            # Worker crash mid-LLM-call → Temporal replays the workflow and the
            # plugin re-dispatches only the incomplete LLM call, not the full agent loop.
            OpenAIAgentsPlugin(
                model_params=ModelActivityParameters(
                    start_to_close_timeout=timedelta(seconds=60),
                    schedule_to_close_timeout=timedelta(seconds=180),
                    retry_policy=RetryPolicy(
                        backoff_coefficient=2.0,
                        initial_interval=timedelta(seconds=1),
                        maximum_interval=timedelta(seconds=10),
                        maximum_attempts=3,
                    ),
                ),
            ),
        ],
    )
    log.info("worker.connected", address=settings.temporal_address,
             namespace=settings.temporal_namespace, task_queue=settings.temporal_task_queue)

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[HelloWorkflow, BacktestSandboxWorkflow, SelfEvolvingStockAgentWorkflow],
        activities=[
            # These two are dual-purpose: the workflow calls them directly each tick
            # AND the trade-intent Agent gets them as tools (via `activity_as_tool`
            # in parent.py). Either path produces a normal `ActivityTaskScheduled`
            # event in workflow history — durable and replayable.
            fetch_market_snapshot,
            fetch_news_snapshot,
            # Plain workflow activities — deterministic side effects, not LLM tools.
            run_backtest_in_sandbox,
            persist_strategy,
            write_trade_record,
            notify_ui,
            fetch_historical_data,
            risk_check,
            place_order,
        ],
    )
    log.info("worker.starting")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
