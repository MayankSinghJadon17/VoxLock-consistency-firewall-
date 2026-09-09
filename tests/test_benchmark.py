import asyncio

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark import run_benchmark


def test_benchmark_is_reproducible_and_has_no_stale_audio_leakage():
    results = asyncio.run(run_benchmark(30, 42))
    assert len(results) == 30
    assert sum(r.stale_chunks_played for r in results) == 0
    assert sum(r.stale_chunks_rejected for r in results) > 0
    assert sum(r.tool_cancelled for r in results) > 0
    assert sum(r.late_completions_fenced for r in results) > 0


def test_benchmark_seed_is_deterministic():
    a = asyncio.run(run_benchmark(10, 42))
    b = asyncio.run(run_benchmark(10, 42))
    assert [(r.phase, r.stale_chunks_rejected, r.late_completions_fenced) for r in a] == [
        (r.phase, r.stale_chunks_rejected, r.late_completions_fenced) for r in b
    ]
