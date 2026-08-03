"""In-process pub/sub for live run events (the SSE fan-out).

The runner publishes each pipeline/gate/webhook event here; ``GET /runs/{id}/
events`` subscribes and relays them over SSE. Events are ALSO persisted to the
``events`` table (db.py), so a late subscriber first replays the durable log and
then live-tails from this hub — no event is missed regardless of connect timing.

Single event loop (FastAPI's) → ``asyncio.Queue`` is the right primitive; this is
the same shape as the WEEX bot's ailog fan-out referenced in ARCHITECTURE.
"""

from __future__ import annotations

import asyncio
from typing import Any

# sentinel pushed to every subscriber when a run reaches a terminal event
END = {"type": "__end__"}


class EventHub:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = {}
        self._done: set[str] = set()

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.setdefault(run_id, set()).add(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        subs = self._subs.get(run_id)
        if subs and q in subs:
            subs.discard(q)
            if not subs:
                self._subs.pop(run_id, None)

    def publish(self, run_id: str, event: dict[str, Any]) -> None:
        for q in list(self._subs.get(run_id, ())):
            q.put_nowait(event)

    def mark_done(self, run_id: str) -> None:
        """Signal end-of-stream: wake every current subscriber with END."""
        self._done.add(run_id)
        self.publish(run_id, END)

    def is_done(self, run_id: str) -> bool:
        return run_id in self._done

    def reset(self, run_id: str) -> None:
        self._subs.pop(run_id, None)
        self._done.discard(run_id)


# process-wide singleton
hub = EventHub()
