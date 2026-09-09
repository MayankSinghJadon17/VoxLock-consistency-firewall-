from __future__ import annotations

import pytest

from voiceguard.continuity import ConversationalContinuity
from voiceguard.types import RequestState
from voiceguard.voiceguard import VoiceGuard


@pytest.mark.asyncio
async def test_active_request_gets_progress_message():
    guard = VoiceGuard()
    continuity = ConversationalContinuity(guard)

    request = await guard.begin_request("Find trains to Delhi")

    message = await continuity.progress_message(
        request.request_id,
        state=RequestState.TOOL_RUNNING,
    )

    assert message is not None
    assert message.request_id == request.request_id
    assert message.text == "Let me check that for you."
    assert message.stage == "TOOL_RUNNING"


@pytest.mark.asyncio
async def test_interrupted_request_cannot_generate_continuity_message():
    guard = VoiceGuard()
    continuity = ConversationalContinuity(guard)

    request = await guard.begin_request("Find trains to Delhi")

    await guard.on_interrupt()

    message = await continuity.progress_message(
        request.request_id,
        state=RequestState.TOOL_RUNNING,
    )

    assert message is None


@pytest.mark.asyncio
async def test_replacement_request_gets_new_continuity_message():
    guard = VoiceGuard()
    continuity = ConversationalContinuity(guard)

    request_1 = await guard.begin_request("Find trains to Delhi")

    await guard.on_interrupt()

    request_2 = await guard.begin_request("Find trains to Mumbai")

    message = await continuity.progress_message(
        request_2.request_id,
        state=RequestState.TOOL_RUNNING,
    )

    assert message is not None
    assert message.request_id == request_2.request_id

    assert message is not None
    assert message.request_id == request_2.request_id
    assert message.request_id != request_1.request_id
    assert message.text == "Let me check that for you."


@pytest.mark.asyncio
async def test_interrupted_request_cannot_generate_backchannel():
    guard = VoiceGuard()
    continuity = ConversationalContinuity(guard)

    request = await guard.begin_request("Find trains to Delhi")

    await guard.on_interrupt()

    message = await continuity.backchannel(
        request.request_id,
        state=RequestState.TOOL_RUNNING,
    )

    assert message is None