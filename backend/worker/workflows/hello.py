from datetime import timedelta
from temporalio import workflow


@workflow.defn
class HelloWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        await workflow.sleep(timedelta(seconds=0))
        return f"Hello, {name} — from a durable workflow"
