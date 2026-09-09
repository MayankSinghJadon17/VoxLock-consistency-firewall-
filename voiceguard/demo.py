from __future__ import annotations

import asyncio
import logging

from .tool import search_trains
from .types import RequestState
from .voiceguard import VoiceGuard

logging.basicConfig(level=logging.INFO, format="%(message)s")


async def main() -> None:
    guard = VoiceGuard()

    first = await guard.begin_request("Find a train from Chennai to Bengaluru")
    await guard.set_state(RequestState.THINKING, request_id=first.request_id)

    async def work() -> object:
        await guard.set_state(RequestState.TOOL_RUNNING, request_id=first.request_id)
        return await guard.run_managed(
            first.request_id,
            "tool",
            lambda: search_trains(
                "Chennai", "Bengaluru", min_delay=0.8, max_delay=1.2
            ),
        )

    task = asyncio.create_task(work())
    await asyncio.sleep(0.2)

    # In a real LiveKit adapter, transport audio stopping and this call are separate.
    replacement = await guard.on_interrupt(reason="keyboard_demo_interrupt")

    try:
        await task
    except asyncio.CancelledError:
        logging.info("Cancelled in-flight task for request %s", first.request_id)

    logging.info("Replacement active request: %s", replacement)
    logging.info("Ghost/ledger events: %s", len(guard.ledger.events))


if __name__ == "__main__":
    asyncio.run(main())
