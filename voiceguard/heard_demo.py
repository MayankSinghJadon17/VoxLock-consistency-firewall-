from __future__ import annotations

import asyncio

from .types import AudioChunk
from .voiceguard import VoiceGuard


def print_request_report(guard: VoiceGuard, request_id: int) -> None:
    summary = guard.ledger.heard_summary(request_id)
    events = guard.ledger.events_for(request_id)

    interrupted = summary["interrupted"]
    status = summary["status"]

    print()
    print(f"REQUEST #{request_id}   {status}")
    print("─" * 60)

    if summary["generated_text"]:
        print()
        print("Generated")
        print(f'  "{summary["generated_text"]}"')

    print()
    print("Actually Heard")
    if summary["played_sequences"]:
        first = summary["played_sequences"][0]
        last = summary["played_sequences"][-1]
        print(f"  chunks {first} → {last}")
        print(f"  {summary['played_chunks']} chunk(s) actually played")
    else:
        print("  none")

    if interrupted:
        print()
        print("After Interrupt")
        rejected = summary["rejected_sequences"]

        if rejected:
            first = rejected[0]
            last = rejected[-1]
            print(f"  chunks {first} → {last}   REJECTED")
            print(f"  {summary['rejected_chunks']} stale chunk(s) blocked")
        else:
            print("  no stale audio generated")

    ghosts = guard.ledger.ghost_tasks(request_id)

    print()
    print("Ghost Work")
    if ghosts:
        by_stage: dict[str, int] = {}

        for event in ghosts:
            stage = str(event.payload.get("stage", "unknown"))
            by_stage[stage] = by_stage.get(stage, 0) + 1

        for stage, count in by_stage.items():
            print(f"  {stage:<16} {count} rejected")
    else:
        print("  none")

    generated = summary["generated_chunks"]
    played = summary["played_chunks"]
    rejected = summary["rejected_chunks"]

    print()
    print("Consistency")
    print(f"  generated chunks : {generated}")
    print(f"  played chunks    : {played}")
    print(f"  rejected chunks  : {rejected}")

    if interrupted:
        print("  status            : FENCED")
    else:
        print("  status            : ACCEPTED")


def print_guarantee(guard: VoiceGuard, request_ids: list[int]) -> None:
    superseded_ok = True
    stale_audio_ok = True
    replacement_ok = True

    for request_id in request_ids:
        summary = guard.ledger.heard_summary(request_id)

        if summary["interrupted"] and summary["rejected_chunks"] == 0:
            stale_audio_ok = False

        if summary["interrupted"]:
            if summary["played_chunks"] > summary["generated_chunks"]:
                superseded_ok = False

    if len(request_ids) >= 2:
        replacement = guard.ledger.heard_summary(request_ids[-1])
        replacement_ok = (
            not replacement["interrupted"]
            and replacement["played_chunks"] > 0
        )

    print()
    print("─" * 60)
    print("CONSISTENCY GUARANTEE")
    print("─" * 60)

    print(
        f"{'✓' if superseded_ok else '✗'} "
        "Superseded requests remain fenced"
    )
    print(
        f"{'✓' if stale_audio_ok else '✗'} "
        "Stale audio is rejected after interrupt"
    )
    print(
        f"{'✓' if replacement_ok else '✗'} "
        "Replacement request becomes active"
    )


async def main() -> None:
    guard = VoiceGuard()

    # ---------------------------------------------------------
    # REQUEST #1
    # ---------------------------------------------------------

    request_1 = await guard.begin_request("Find a train from Delhi")

    await guard.accept_llm_output(
        request_1.request_id,
        "Your train leaves at 08:10 from Delhi.",
    )

    for sequence in range(4):
        await guard.accept_audio_chunk(
            AudioChunk(
                request_id=request_1.request_id,
                sequence=sequence,
                audio=f"chunk-{sequence}".encode(),
                generated_at=0.0,
            )
        )

    # ---------------------------------------------------------
    # INTERRUPT → REQUEST #2
    # ---------------------------------------------------------

    request_2_id = await guard.on_interrupt()

    # Old request continues generating audio.
    # The firewall must reject every stale chunk.
    for sequence in range(4, 8):
        await guard.accept_audio_chunk(
            AudioChunk(
                request_id=request_1.request_id,
                sequence=sequence,
                audio=f"stale-{sequence}".encode(),
                generated_at=0.0,
            )
        )

    # ---------------------------------------------------------
    # REQUEST #2
    # ---------------------------------------------------------

    await guard.accept_llm_output(
        request_2_id,
        "The Mumbai train leaves at 09:30.",
    )

    for sequence in range(6):
        await guard.accept_audio_chunk(
            AudioChunk(
                request_id=request_2_id,
                sequence=sequence,
                audio=f"new-{sequence}".encode(),
                generated_at=0.0,
            )
        )

    # ---------------------------------------------------------
    # OBSERVATORY
    # ---------------------------------------------------------

    print()
    print("=" * 60)
    print("VOICEGUARD — HEARD-STATE OBSERVATORY")
    print("=" * 60)

    request_ids = [
        request_1.request_id,
        request_2_id,
    ]

    for request_id in request_ids:
        print_request_report(guard, request_id)

    print_guarantee(guard, request_ids)

    print()
    print("─" * 60)
    print("INTENT TIMELINE")
    print("─" * 60)
    print(guard.ledger.format_timeline())

    print()
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())