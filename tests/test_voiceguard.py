import asyncio

import pytest

from voiceguard import VoiceGuard
from voiceguard.types import AudioChunk, RequestState
from voiceguard.tool import search_trains

@pytest.mark.asyncio
async def test_interrupt_cancels_task_and_invalidates_request():
    guard = VoiceGuard()
    ctx = await guard.begin_request("old")
    await guard.set_state(RequestState.TOOL_RUNNING, request_id=ctx.request_id)

    async def operation():
        await asyncio.sleep(10)

    task = asyncio.create_task(
        guard.run_managed(ctx.request_id, "tool", operation)
    )
    await asyncio.sleep(0)
    assert guard.active_task is not None

    await guard.on_interrupt()

    assert guard.active_id == 0
    assert guard.active_task is None

    with pytest.raises(asyncio.CancelledError):
        await task

    replacement = await guard.begin_request("new")

    assert replacement.request_id == ctx.request_id + 1
    assert guard.active_id == replacement.request_id

@pytest.mark.asyncio
async def test_stale_tool_result_is_rejected():
    guard = VoiceGuard()
    old = await guard.begin_request("old")
    await guard.on_interrupt()
    assert await guard.accept_tool_result(old.request_id, {"stale": True}) is False


@pytest.mark.asyncio
async def test_stale_llm_result_is_rejected():
    guard = VoiceGuard()
    old = await guard.begin_request("old")
    await guard.on_interrupt()
    assert await guard.accept_llm_output(old.request_id, "do not speak") is False


@pytest.mark.asyncio
async def test_audio_fence_stops_stale_playback():
    guard = VoiceGuard()
    old = await guard.begin_request("old")
    played = []

    assert await guard.accept_audio_chunk(
        AudioChunk(old.request_id, 0, b"a", 0.0)
    )
    played.append(0)

    await guard.on_interrupt()

    assert not await guard.accept_audio_chunk(
        AudioChunk(old.request_id, 1, b"b", 0.0)
    )

    assert guard.ledger.played_sequences(old.request_id) == [0]


@pytest.mark.asyncio
async def test_ghost_log_for_late_result():
    guard = VoiceGuard()
    old = await guard.begin_request("old")
    await guard.on_interrupt()

    assert await guard.accept_tool_result(old.request_id, "late") is False
    ghosts = [e for e in guard.ledger.events if e.kind == "ghost_task"]
    assert ghosts
    assert ghosts[-1].request_id == old.request_id


@pytest.mark.asyncio
async def test_late_tool_completion_is_rejected_as_ghost():
    guard = VoiceGuard()

    old = await guard.begin_request("Find trains to Delhi")

    tool_finished = asyncio.Event()

    async def late_tool():
        # Simulate backend work that continues independently
        # even after the request that started it is superseded.
        await asyncio.sleep(0.05)
        tool_finished.set()
        return "Delhi train results"

    # Run the tool directly so the simulated backend can finish
    # even after VoiceGuard invalidates request #1.
    async def run_late_tool():
        result = await late_tool()
        return result

    task = asyncio.create_task(run_late_tool())

    # User changes their mind before the old tool finishes.
    await guard.on_interrupt()

    assert guard.active_id == 0

    new_request = await guard.begin_request("new request")

    assert new_request.request_id == old.request_id + 1
    assert guard.active_id == new_request.request_id

    # The old backend operation eventually finishes.
    result = await task

    assert tool_finished.is_set()
    assert result == "Delhi train results"

    # But the old result must not become valid application state.
    accepted = await guard.accept_tool_result(
        old.request_id,
        result,
    )

    assert accepted is False

    # VoiceGuard should have recorded the stale result.
    ghosts = [
        event
        for event in guard.ledger.events
        if event.kind == "ghost_task"
    ]

    assert ghosts
    assert ghosts[-1].request_id == old.request_id
    assert ghosts[-1].payload["stage"] == "tool_result"


@pytest.mark.asyncio
async def test_backend_completion_after_interrupt_is_fenced():
    guard = VoiceGuard()

    old = await guard.begin_request("Find trains to Delhi")

    backend_finished = asyncio.Event()

    async def backend_operation():
        await asyncio.sleep(0.05)
        backend_finished.set()
        return "Delhi train results"

    backend_task = asyncio.create_task(backend_operation())

    async def managed_operation():
        try:
            return await asyncio.shield(backend_task)
        except asyncio.CancelledError:
            # The VoiceGuard task is cancelled, but the backend operation
            # continues independently.
            raise

    managed_task = asyncio.create_task(
        guard.run_managed(
            old.request_id,
            "tool",
            managed_operation,
        )
    )

    await asyncio.sleep(0)

    # User changes their mind.

    await guard.on_interrupt()

    assert guard.active_id == 0

    new_request = await guard.begin_request("replacement")

    assert new_request.request_id == old.request_id + 1

    # The VoiceGuard-managed task is cancelled.
    with pytest.raises(asyncio.CancelledError):
        await managed_task

    # The backend itself is still alive.
    result = await backend_task

    assert backend_finished.is_set()
    assert result == "Delhi train results"

    # The late backend result must be fenced before it can become
    # valid VoiceGuard state.
    accepted = await guard.accept_tool_result(
        old.request_id,
        result,
    )

    assert accepted is False

    ghosts = [
        event
        for event in guard.ledger.events
        if event.kind == "ghost_task"
    ]

    assert ghosts
    assert ghosts[-1].request_id == old.request_id
    assert ghosts[-1].payload["stage"] == "tool_result"

@pytest.mark.asyncio
async def test_real_search_trains_stale_result_is_fenced():
    guard = VoiceGuard()

    # User's first request.
    old = await guard.begin_request("Find trains to Delhi")

    # Start the real tool independently so we can demonstrate that
    # backend work may finish even after the application request is superseded.
    old_tool = asyncio.create_task(
        search_trains(
            "Mumbai",
            "Delhi",
            min_delay=0.05,
            max_delay=0.05,
        )
    )

    # Give the tool a chance to start.
    await asyncio.sleep(0)

    # User interrupts and changes the request.
    new = await guard.begin_request("Find trains to Jaipur")

    assert new.request_id == old.request_id + 1
    assert guard.active_id == new.request_id

    # The old backend operation is allowed to finish.
    old_result = await old_tool

    assert old_result.destination == "Delhi"

    # But the old result is no longer valid.
    accepted_old = await guard.accept_tool_result(
        old.request_id,
        old_result,
    )

    assert accepted_old is False

    # New request runs the same real tool.
    new_result = await search_trains(
        "Mumbai",
        "Jaipur",
        min_delay=0.01,
        max_delay=0.01,
    )

    assert new_result.destination == "Jaipur"

    # Current request's result is accepted.
    accepted_new = await guard.accept_tool_result(
        new.request_id,
        new_result,
    )

    assert accepted_new is True

    # The stale result must appear in the ghost log.
    ghosts = [
        event
        for event in guard.ledger.events
        if event.kind == "ghost_task"
    ]

    assert ghosts
    assert ghosts[-1].request_id == old.request_id
    assert ghosts[-1].payload["stage"] == "tool_result"



@pytest.mark.asyncio
async def test_ghost_observatory_records_superseded_and_accepted_results():
    guard = VoiceGuard()

    # Request #1 is active.
    old = await guard.begin_request("Find trains to Delhi")

    old_tool = asyncio.create_task(
        search_trains(
            "Mumbai",
            "Delhi",
            min_delay=0.05,
            max_delay=0.05,
        )
    )

    await asyncio.sleep(0)

    # User interrupts request #1.
    # on_interrupt() creates request #2 and records the interrupt.
    await guard.on_interrupt()

    assert guard.active_id == 0

    new_request = await guard.begin_request("replacement")

    assert new_request.request_id == old.request_id + 1

    # The old backend operation is allowed to finish.
    old_result = await old_tool

    assert old_result.destination == "Delhi"

    # Old result must be rejected.
    assert await guard.accept_tool_result(
        old.request_id,
        old_result,
    ) is False

    # Request #2 uses the replacement ID created by on_interrupt().
    new_result = await search_trains(
        "Mumbai",
        "Jaipur",
        min_delay=0.01,
        max_delay=0.01,
    )

    assert new_result.destination == "Jaipur"

    # Current request's result must be accepted.
    assert await guard.accept_tool_result(
        new_request.request_id,
        new_result,
    ) is True

    timeline = guard.ledger.format_timeline()

    # Interrupt was recorded.
    assert f"[{old.request_id}] INTERRUPT" in timeline

    # Old result was rejected and logged as a ghost.
    assert f"[{old.request_id}] GHOST_TASK" in timeline

    # New result was accepted.
    assert f"[{new_request.request_id}] TOOL_RESULT_ACCEPTED" in timeline



@pytest.mark.asyncio
async def test_heard_state_summary_distinguishes_generated_and_played():
    guard = VoiceGuard()

    request = await guard.begin_request("Find trains to Delhi")

    await guard.accept_llm_output(
        request.request_id,
        "The next train leaves at 08:10.",
    )

    assert await guard.accept_audio_chunk(
        AudioChunk(request.request_id, 0, b"a", 0.0)
    )

    assert await guard.accept_audio_chunk(
        AudioChunk(request.request_id, 1, b"b", 0.0)
    )

    await guard.on_interrupt()

    # These chunks were generated by the old request after the interrupt,
    # but must not count as actually played.
    assert not await guard.accept_audio_chunk(
        AudioChunk(request.request_id, 2, b"c", 0.0)
    )

    assert not await guard.accept_audio_chunk(
        AudioChunk(request.request_id, 3, b"d", 0.0)
    )

    summary = guard.ledger.heard_summary(request.request_id)

    assert summary["generated_text"] == "The next train leaves at 08:10."
    assert summary["generated_chunks"] == 4
    assert summary["played_chunks"] == 2
    assert summary["rejected_chunks"] == 2
    assert summary["played_sequences"] == [0, 1]
    assert summary["rejected_sequences"] == [2, 3]
    assert summary["interrupted"] is True



@pytest.mark.asyncio
async def test_stale_audio_injection_never_reaches_playback():
    guard = VoiceGuard()

    old = await guard.begin_request("Find trains to Delhi")

    played_audio = []

    async def on_play(audio: bytes) -> None:
        played_audio.append(audio)

    # These chunks legitimately belong to the active request.
    played = await guard.play_stream(
        old.request_id,
        [b"chunk-0", b"chunk-1"],
        on_play=on_play,
    )

    assert played == 2
    assert played_audio == [b"chunk-0", b"chunk-1"]

    # User interrupts before the next chunk reaches playback.
    await guard.on_interrupt()

    assert guard.active_id == 0

    new_request = await guard.begin_request("replacement")

    assert new_request.request_id == old.request_id + 1
    # Simulate stale audio arriving from the old TTS stream.
    stale_audio = [
        b"stale-chunk-2",
        b"stale-chunk-3",
        b"stale-chunk-4",
    ]

    for sequence, audio in enumerate(stale_audio, start=2):
        accepted = await guard.accept_audio_chunk(
            AudioChunk(
                request_id=old.request_id,
                sequence=sequence,
                audio=audio,
                generated_at=0.0,
            )
        )

        if accepted:
            await on_play(audio)

    # No stale audio crossed the playback boundary.
    assert played_audio == [b"chunk-0", b"chunk-1"]

    summary = guard.ledger.heard_summary(old.request_id)

    assert summary["generated_chunks"] == 5
    assert summary["played_chunks"] == 2
    assert summary["rejected_chunks"] == 3
    assert summary["played_sequences"] == [0, 1]
    assert summary["rejected_sequences"] == [2, 3, 4]


@pytest.mark.asyncio
async def test_late_tool_completion_is_recorded_as_ghost_and_replacement_is_accepted():
    guard = VoiceGuard()

    # 1. Start request #1.
    old = await guard.begin_request("Find trains to Delhi")

    # 2. Deliberately make the backend ignore asyncio cancellation.
    async def stubborn_tool():
        try:
            await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            # Simulate a backend operation that cannot be stopped immediately.
            await asyncio.sleep(0.05)

        return "Delhi trains found"

    old_task = asyncio.create_task(
        guard.run_managed(
            old.request_id,
            "tool",
            stubborn_tool,
        )
    )

    # Give run_managed() time to register the task.
    await asyncio.sleep(0)

    # 3. Interrupt: request #1 becomes stale.
    await guard.on_interrupt()

    assert guard.active_id == 0

    new_request = await guard.begin_request("replacement")

    assert new_request.request_id == old.request_id + 1
    # 4. The backend ignores cancellation and eventually completes.
    result = await old_task

    # VoiceGuard must reject the stale result.
    assert result is None

    old_events = guard.ledger.events_for(old.request_id)
    old_kinds = [event.kind for event in old_events]

    # 5. Old request completed, but its result was rejected.
    assert "tool_completed" in old_kinds
    assert "ghost_task" in old_kinds
    assert "tool_result_accepted" not in old_kinds

    ghosts = guard.ledger.ghost_tasks(old.request_id)

    assert len(ghosts) >= 1
    assert ghosts[-1].payload["stage"] == "tool_result"

    # 6. Use replacement request #2.
    async def replacement_tool():
        return "Mumbai trains found"

    replacement_result = await guard.run_managed(
        new_request.request_id,
        "tool",
        replacement_tool,
    )

    # 7. Replacement result is accepted.
    assert replacement_result == "Mumbai trains found"

    new_events = guard.ledger.events_for(new_request.request_id)
    new_kinds = [event.kind for event in new_events]

    assert "tool_completed" in new_kinds
    assert "tool_result_accepted" in new_kinds
    assert "ghost_task" not in new_kinds