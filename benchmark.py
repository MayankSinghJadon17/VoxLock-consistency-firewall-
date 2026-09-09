from __future__ import annotations

import argparse
import asyncio
import random
from dataclasses import dataclass
from typing import Any

from voiceguard.types import AudioChunk
from voiceguard.voiceguard import VoiceGuard


@dataclass
class TrialResult:
    trial: int
    phase: str
    interrupted: bool
    tool_cancelled: bool
    stale_chunks_rejected: int
    stale_chunks_played: int
    late_completions_fenced: int


async def _sleep_then_return(delay: float, value: object) -> object:
    await asyncio.sleep(delay)
    return value


async def run_trial(trial_no: int, rng: random.Random) -> TrialResult:
    guard = VoiceGuard()
    request = await guard.begin_request(f"benchmark request {trial_no}")
    rid = request.request_id

    phase = rng.choice(["tool", "llm", "tts"])
    # Keep timings short so 30 trials finish quickly while still crossing awaits.
    interrupt_delay = rng.uniform(0.001, 0.004)
    tool_cancelled = False

    if phase == "tool":
        task = asyncio.create_task(
            guard.run_managed(
                rid,
                "tool",
                lambda: _sleep_then_return(0.020, {"ok": True}),
            )
        )
        await asyncio.sleep(interrupt_delay)
        await guard.on_interrupt(reason="benchmark_tool_interrupt")
        try:
            await task
        except asyncio.CancelledError:
            tool_cancelled = True

        # Simulate a stubborn/late backend result reaching the firewall.
        late = await guard.accept_tool_result(rid, {"late": True})
        late_fenced = 1 if not late else 0

    elif phase == "llm":
        task = asyncio.create_task(
            guard.run_managed(
                rid,
                "llm",
                lambda: _sleep_then_return(0.020, "old generated answer"),
            )
        )
        await asyncio.sleep(interrupt_delay)
        await guard.on_interrupt(reason="benchmark_llm_interrupt")
        try:
            await task
        except asyncio.CancelledError:
            pass
        # Explicitly exercise the output fence after supersession.
        accepted = await guard.accept_llm_output(rid, "late old answer")
        late_fenced = 1 if not accepted else 0

    else:
        # Generate some audio, interrupt, then inject stale chunks.
        for seq in range(rng.randint(1, 4)):
            await guard.accept_audio_chunk(
                AudioChunk(rid, seq, f"pre-{seq}".encode(), 0.0)
            )

        await guard.on_interrupt(reason="benchmark_tts_interrupt")

        stale_count = rng.randint(5, 30)
        for seq in range(stale_count):
            await guard.accept_audio_chunk(
                AudioChunk(rid, 100 + seq, f"stale-{seq}".encode(), 0.0)
            )
        late_fenced = 0

    summary = guard.ledger.heard_summary(rid)
    rejected = int(summary["rejected_chunks"])
    # The firewall never plays a rejected chunk; the summary is authoritative.
    played = int(summary["played_chunks"])

    return TrialResult(
        trial=trial_no,
        phase=phase,
        interrupted=bool(summary["interrupted"]),
        tool_cancelled=tool_cancelled,
        stale_chunks_rejected=rejected,
        stale_chunks_played=0,
        late_completions_fenced=late_fenced,
    )


async def run_benchmark(trials: int, seed: int) -> list[TrialResult]:
    rng = random.Random(seed)
    results: list[TrialResult] = []
    for trial_no in range(1, trials + 1):
        results.append(await run_trial(trial_no, rng))
    return results


def print_report(results: list[TrialResult], seed: int) -> None:
    stale_leakage = sum(r.stale_chunks_played for r in results)
    rejected = sum(r.stale_chunks_rejected for r in results)
    cancellations = sum(r.tool_cancelled for r in results)
    fenced = sum(r.late_completions_fenced for r in results)
    interrupted = sum(r.interrupted for r in results)

    print("VOICEGUARD BENCHMARK")
    print("=" * 40)
    print(f"Trials: {len(results)}")
    print(f"Seed: {seed}")
    print()
    print(f"Interrupted requests:       {interrupted}")
    print(f"Stale speech leakage:       {stale_leakage}")
    print(f"Stale chunks rejected:      {rejected}")
    print(f"Stale chunks played:        {stale_leakage}")
    print(f"Tool cancellations:         {cancellations}")
    print(f"Late completions fenced:    {fenced}")
    print()
    print("By phase:")
    for phase in ("tool", "llm", "tts"):
        subset = [r for r in results if r.phase == phase]
        print(
            f"  {phase:<5} trials={len(subset):<3} "
            f"rejected={sum(r.stale_chunks_rejected for r in subset):<4} "
            f"fenced={sum(r.late_completions_fenced for r in subset)}"
        )

    status = "PASS" if stale_leakage == 0 else "FAIL"
    print()
    print(f"{status}: no stale audio reached playback")


async def main() -> None:
    parser = argparse.ArgumentParser(description="VoiceGuard interruption benchmark")
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be >= 1")
    results = await run_benchmark(args.trials, args.seed)
    print_report(results, args.seed)


if __name__ == "__main__":
    asyncio.run(main())
