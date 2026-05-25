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
            # Tools the trade-intent Agent can call (via `activity_as_tool`):
            fetch_market_snapshot,
            fetch_news_snapshot,
            # Other workflow activities (deterministic, not exposed as tools):
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
