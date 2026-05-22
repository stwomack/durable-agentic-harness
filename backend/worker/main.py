import asyncio
import logging

import structlog
from temporalio.client import Client
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
from worker.activities.llm import call_agent
from worker.activities.risk import risk_check
from worker.activities.broker import place_order
from worker.activities.drift import check_drift


structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(
    getattr(logging, settings.log_level.upper(), logging.INFO)))
log = structlog.get_logger("worker")


async def main() -> None:
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
        data_converter=pydantic_data_converter,
    )
    log.info("worker.connected", address=settings.temporal_address,
             namespace=settings.temporal_namespace, task_queue=settings.temporal_task_queue)

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[HelloWorkflow, BacktestSandboxWorkflow, SelfEvolvingStockAgentWorkflow],
        activities=[
            run_backtest_in_sandbox, persist_strategy, write_trade_record,
            notify_ui, fetch_historical_data, fetch_market_snapshot,
            fetch_news_snapshot, call_agent, risk_check, place_order, check_drift,
        ],
    )
    log.info("worker.starting")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
