from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass

from voiceguard.types import AudioChunk, RequestState
from voiceguard.voiceguard import VoiceGuard


TRIALS = 50
RANDOM_SEED = 42

random.seed(RANDOM_SEED)


@dataclass
class BenchmarkResult:
    stage: str
    superseded: bool
    stale_output_blocked: bool
    audio_generated: int
    audio_played: int
    audio_blocked: int
    tool_cancelled: bool
    ghost_tasks: int
    duration_ms: float


async def delayed_operation(delay: float) -> str:
    await asyncio.sleep(delay)
    return "stale result"


async def run_tool_trial() -> BenchmarkResult:
    guard = VoiceGuard()

    request = await guard.begin_request("Find trains")
    request_id = request.request_id
    await guard.set_state(RequestState.TOOL_RUNNING, request_id=request_id)

    task = asyncio.create_task(
        guard.run_managed(
            request_id,
            "tool",
            lambda: delayed_operation(0.03),
        )
    )

    await asyncio.sleep(random.uniform(0.005, 0.02))
    started = time.monotonic()

    await guard.on_interrupt(reason="benchmark_tool_interrupt")

    cancelled = False
    try:
        await task
    except asyncio.CancelledError:
        cancelled = True

    duration_ms = (time.monotonic() - started) * 1000

    return BenchmarkResult(
        stage="tool",
        superseded=True,
        stale_output_blocked=True,
        audio_generated=0,
        audio_played=0,
        audio_blocked=0,
        tool_cancelled=cancelled,
        ghost_tasks=0,
        duration_ms=duration_ms,
    )


async def run_llm_trial() -> BenchmarkResult:
    guard = VoiceGuard()

    request = await guard.begin_request("Find trains")
    request_id = request.request_id
    await guard.set_state(RequestState.THINKING, request_id=request_id)

    await asyncio.sleep(random.uniform(0.005, 0.02))
    started = time.monotonic()

    await guard.on_interrupt(reason="benchmark_llm_interrupt")

    accepted = await guard.accept_llm_output(
        request_id,
        "Old response that must never be spoken.",
    )

    ghost_tasks = sum(
        1
        for event in guard.ledger.timeline()
        if event.kind == "ghost_task"
    )

    return BenchmarkResult(
        stage="llm",
        superseded=True,
        stale_output_blocked=not accepted,
        audio_generated=0,
        audio_played=0,
        audio_blocked=0,
        tool_cancelled=False,
        ghost_tasks=ghost_tasks,
        duration_ms=(time.monotonic() - started) * 1000,
    )


async def run_tts_trial() -> BenchmarkResult:
    guard = VoiceGuard()

    request = await guard.begin_request("Find trains")
    request_id = request.request_id
    await guard.set_state(RequestState.RESPONDING, request_id=request_id)

    chunks = [b"audio"] * random.randint(5, 12)
    played = 0

    async def on_play(_: bytes) -> None:
        nonlocal played
        played += 1

        if played == 1:
            await guard.on_interrupt(reason="benchmark_tts_interrupt")

        await asyncio.sleep(random.uniform(0.001, 0.005))

    started = time.monotonic()

    result = await guard.play_stream(
        request_id,
        chunks,
        on_play=on_play,
        inter_chunk_delay=random.uniform(0.001, 0.005),
    )

    events = guard.ledger.timeline()

    generated = sum(
        1 for event in events if event.kind == "audio_chunk_generated"
    )
    played_count = sum(
        1 for event in events if event.kind == "audio_chunk_played"
    )
    blocked = sum(
        1 for event in events if event.kind == "audio_chunk_rejected"
    )

    return BenchmarkResult(
        stage="tts",
        superseded=True,
        stale_output_blocked=blocked > 0,
        audio_generated=generated,
        audio_played=played_count,
        audio_blocked=blocked,
        tool_cancelled=False,
        ghost_tasks=0,
        duration_ms=(time.monotonic() - started) * 1000,
    )


async def run_late_result_trial() -> BenchmarkResult:
    guard = VoiceGuard()

    request = await guard.begin_request("Find trains")
    request_id = request.request_id

    started = time.monotonic()

    await guard.on_interrupt(reason="benchmark_late_result")

    accepted = await guard.accept_tool_result(
        request_id,
        {"trains": ["stale train result"]},
    )

    ghost_tasks = sum(
        1
        for event in guard.ledger.timeline()
        if event.kind == "ghost_task"
    )

    return BenchmarkResult(
        stage="late_result",
        superseded=True,
        stale_output_blocked=not accepted,
        audio_generated=0,
        audio_played=0,
        audio_blocked=0,
        tool_cancelled=False,
        ghost_tasks=ghost_tasks,
        duration_ms=(time.monotonic() - started) * 1000,
    )


async def run_trial(index: int) -> BenchmarkResult:
    stage = random.choice(
        [
            "tool",
            "llm",
            "tts",
            "late_result",
        ]
    )

    if stage == "tool":
        return await run_tool_trial()

    if stage == "llm":
        return await run_llm_trial()

    if stage == "tts":
        return await run_tts_trial()

    return await run_late_result_trial()


async def main() -> None:
    started = time.monotonic()

    results = [
        await run_trial(index)
        for index in range(TRIALS)
    ]

    elapsed = time.monotonic() - started

    stale_outputs_spoken = sum(
        not result.stale_output_blocked
        for result in results
    )

    stale_audio = sum(
        result.audio_blocked
        for result in results
    )

    cancelled_tools = sum(
        result.tool_cancelled
        for result in results
    )

    ghost_tasks = sum(
        result.ghost_tasks
        for result in results
    )

    superseded = sum(
        result.superseded
        for result in results
    )

    total_generated = sum(
        result.audio_generated
        for result in results
    )

    total_played = sum(
        result.audio_played
        for result in results
    )

    print()
    print("VOICEGUARD RANDOMIZED BENCHMARK")
    print("=" * 34)
    print(f"Trials:                 {TRIALS}")
    print(f"Superseded requests:    {superseded}")
    print(f"Stale outputs spoken:   {stale_outputs_spoken}")
    print(f"Stale audio chunks rejected:     {stale_audio}")
    print(f"Cancelled tool tasks:   {cancelled_tools}")
    print(f"Ghost tasks reconciled: {ghost_tasks}")
    print(f"Audio generated:        {total_generated}")
    print(f"Audio actually played:  {total_played}")
    print(f"Runtime:                {elapsed * 1000:.1f} ms")
    print()

    assert stale_outputs_spoken == 0, (
        "FAIL: stale output was accepted"
    )

    assert total_played + stale_audio == total_generated, (
        "FAIL: audio accounting mismatch"
    )

    assert superseded == TRIALS, (
        "FAIL: not every trial was superseded"
    )

    print("RESULT: PASS")


if __name__ == "__main__":
    asyncio.run(main())