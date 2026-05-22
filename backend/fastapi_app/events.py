import asyncio
from collections import defaultdict
from typing import AsyncIterator


class EventBus:
    """In-process pub/sub: workflow_id -> set of asyncio.Queues."""

    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)

    async def publish(self, workflow_id: str, event: dict) -> None:
        for q in list(self._subs.get(workflow_id, ())):
            await q.put(event)

    async def subscribe(self, workflow_id: str) -> AsyncIterator[dict]:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subs[workflow_id].add(q)
        try:
            while True:
                event = await q.get()
                yield event
        finally:
            self._subs[workflow_id].discard(q)


bus = EventBus()
