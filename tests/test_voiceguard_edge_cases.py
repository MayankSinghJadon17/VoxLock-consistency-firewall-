from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from voiceguard.types import AudioChunk, RequestState
from voiceguard.voiceguard import VoiceGuard


async def delayed_result(delay: float = 0.05) -> str:
    await asyncio.sleep(delay)
    return "stale result"


@pytest.mark.asyncio
async def test_interrupt_cancels_tool_task():
    guard = VoiceGuard()

    request = await guard.begin_request("Find trains")
    request_id = request.request_id
    await guard.set_state(RequestState.TOOL_RUNNING, request_id=request_id)

    task = asyncio.create_task(
        guard.run_managed(
            request_id,
            "tool",
            lambda: delayed_result(),
        )
    )

    await asyncio.sleep(0.005)
    await guard.on_interrupt()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert guard.active_id == 0
    assert any(
        event.kind == "tool_cancelled"
        for event in guard.ledger.timeline()
    )


@pytest.mark.asyncio
async def test_stale_tool_result_is_rejected():
    guard = VoiceGuard()

    request = await guard.begin_request("Find trains")
    request_id = request.request_id

    await guard.on_interrupt()

    accepted = await guard.accept_tool_result(
        request_id,
        {"trains": ["stale result"]},
    )

    assert accepted is False

    assert any(
        event.kind == "ghost_task"
        and event.request_id == request_id
        for event in guard.ledger.timeline()
    )


@pytest.mark.asyncio
async def test_stale_llm_output_is_rejected():
    guard = VoiceGuard()

    request = await guard.begin_request("Find trains")
    request_id = request.request_id

    await guard.on_interrupt()

    accepted = await guard.accept_llm_output(
        request_id,
        "This response must never be spoken.",
    )

    assert accepted is False

    events = guard.ledger.timeline()

    assert not any(
        event.kind == "generated"
        and event.request_id == request_id
        for event in events
    )

    assert any(
        event.kind == "ghost_task"
        and event.request_id == request_id
        for event in events
    )


@pytest.mark.asyncio
async def test_stale_audio_chunk_is_rejected():
    guard = VoiceGuard()

    request = await guard.begin_request("Find trains")
    request_id = request.request_id

    await guard.on_interrupt()

    chunk = AudioChunk(
        request_id=request_id,
        sequence=0,
        audio=b"stale-audio",
        generated_at=0.0
    )

    accepted = await guard.accept_audio_chunk(chunk)

    assert accepted is False

    stats = guard.stats(request_id)

    assert stats.generated_chunks == 1
    assert stats.played_chunks == 0
    assert stats.rejected_chunks == 1

    events = guard.ledger.timeline()

    assert any(
        event.kind == "audio_chunk_rejected"
        and event.request_id == request_id
        for event in events
    )


@pytest.mark.asyncio
async def test_request_ids_are_monotonic():
    guard = VoiceGuard()

    first = await guard.begin_request("First")
    await guard.on_interrupt()

    second = await guard.begin_request("Second")
    await guard.on_interrupt()

    third = await guard.begin_request("Third")

    assert first.request_id < second.request_id < third.request_id
    assert first.request_id == 1
    assert second.request_id == 2
    assert third.request_id == 3


@pytest.mark.asyncio
async def test_late_tool_completion_cannot_be_accepted():
    guard = VoiceGuard()

    request = await guard.begin_request("Old request")
    request_id = request.request_id

    task = asyncio.create_task(
        guard.run_managed(
            request_id,
            "tool",
            lambda: delayed_result(0.01),
        )
    )

    await asyncio.sleep(0.002)
    await guard.on_interrupt()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert guard.active_id == 0

    accepted = await guard.accept_tool_result(
        request_id,
        "late result",
    )

    assert accepted is False


@pytest.mark.asyncio
async def test_new_request_fences_old_audio():
    guard = VoiceGuard()

    old = await guard.begin_request("Old request")
    old_id = old.request_id

    await guard.on_interrupt()

    new = await guard.begin_request("New request")
    new_id = new.request_id

    old_chunk = AudioChunk(
        request_id=old_id,
        sequence=0,
        audio=b"old",
        generated_at=0.0
    )

    new_chunk = AudioChunk(
        request_id=new_id,
        sequence=0,
        audio=b"new",
        generated_at=0.0
    )

    old_accepted = await guard.accept_audio_chunk(old_chunk)
    new_accepted = await guard.accept_audio_chunk(new_chunk)

    assert old_accepted is False
    assert new_accepted is True

    assert guard.stats(old_id).played_chunks == 0
    assert guard.stats(old_id).rejected_chunks == 1

    assert guard.stats(new_id).played_chunks == 1
    assert guard.stats(new_id).rejected_chunks == 0


@pytest.mark.asyncio
async def test_interrupt_from_tool_state_invalidates_request():
    guard = VoiceGuard()

    request = await guard.begin_request("Find trains")
    request_id = request.request_id

    await guard.set_state(
        RequestState.TOOL_RUNNING,
        request_id=request_id,
    )

    assert guard.state == RequestState.TOOL_RUNNING

    await guard.on_interrupt()

    assert guard.active_id == 0
    assert guard.state == RequestState.LISTENING

    assert any(
        event.kind == "interrupt"
        and event.request_id == request_id
        for event in guard.ledger.timeline()
    )


def test_voiceguard_has_no_livekit_imports():
    source = Path("voiceguard/voiceguard.py").read_text(
        encoding="utf-8"
    )

    import_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]

    assert not any(
        "livekit" in line.lower()
        for line in import_lines
    )