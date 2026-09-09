import asyncio

from voiceguard.ledger import HeardStateLedger
from voiceguard.voiceguard import VoiceGuard


def test_constraint_diff_is_recorded():
    async def run():
        ledger = HeardStateLedger()
        guard = VoiceGuard(ledger=ledger)

        await guard.begin_request("Find trains from Delhi to Mumbai")
        await guard.begin_request("Find trains from Delhi to Jaipur")

        diffs = [
            event
            for event in ledger.events
            if event.kind == "constraint_diff"
        ]

        assert len(diffs) == 1

        event = diffs[0]

        assert event.request_id == 2
        assert event.payload["previous_request_id"] == 1
        assert event.payload["old_text"] == "Find trains from Delhi to Mumbai"
        assert event.payload["new_text"] == "Find trains from Delhi to Jaipur"

        changes = event.payload["changes"]

        assert changes
        assert any(
            change["old"] == "Mumbai"
            and change["new"] == "Jaipur"
            for change in changes
        )

    asyncio.run(run())


def test_interrupt_latency_is_recorded():
    async def run():
        ledger = HeardStateLedger()
        ledger.interruption_latency(
            request_id=1,
            started_at=10.0,
            completed_at=10.0125,
        )

        events = [
            event
            for event in ledger.events
            if event.kind == "interrupt_latency"
        ]

        assert len(events) == 1
        assert abs(events[0].payload["latency_ms"] - 12.5) < 0.01

    asyncio.run(run())