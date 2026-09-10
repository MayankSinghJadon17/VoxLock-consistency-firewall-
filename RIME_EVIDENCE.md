# Rime Evidence — VoxLock

## Hard Voice Claim

**VoxLock prevents superseded voice-agent intent from becoming spoken reality during interruption and recovery.**

The system separates:

**Generated work → consistency firewall → actually heard output**

A request receives a monotonic `request_id`. When the user interrupts, the active request is invalidated. Running work is cancelled when possible, and stale tool results, LLM outputs, and Rime audio chunks are rejected before they can become accepted spoken output.

## Acceptance Test

1. Start the VoxLock voice agent.
2. Issue a transfer request using the synthetic banking demo.
3. Allow the assistant to begin processing and speaking.
4. Interrupt with a changed amount.
5. Verify that the old request becomes superseded.
6. Verify that active old tool work is cancelled when possible.
7. Verify that stale output/audio is fenced.
8. Verify that the new request receives the active request ID.
9. Verify that Rime speaks only the updated confirmation.

### Expected Result

The user hears only the current instruction.

```text
Transfer ₹50,000 to Alex.
        ↓
request #2
        ↓
INTERRUPT
        ↓
request #2 SUPERSEDED
        ↓
old work cancelled / reconciled / blocked
        ↓
Transfer ₹5,000 to Alex.
        ↓
request #3
        ↓
Rime speaks current confirmation
```

## Application-Level Enforcement

1. **Tool result** — managed tools are tagged with `request_id`; stale results are rejected.
2. **LLM output** — output is checked against the active request before speech.
3. **Rime audio** — streaming audio is checked per chunk.
4. **Interruption** — the LiveKit/VAD boundary signals interruption; the VoxLock bridge commits invalidation and cancels active managed work when possible.
5. **Heard-state ledger** — generated and actually played audio are tracked separately.

## Latest Randomized Benchmark

```text
VOICEGUARD RANDOMIZED BENCHMARK
Trials: 50
Superseded requests: 50
Stale outputs spoken: 0
Stale audio chunks rejected: 16
Cancelled tool tasks: 15
Ghost tasks reconciled: 19
Audio generated: 32
Audio actually played: 16
Runtime: 972.8 ms
RESULT: PASS
```

Across 50 randomized interruption trials, 0 stale outputs were spoken. The benchmark also records rejected stale audio chunks, cancelled tool tasks, and reconciled ghost tasks.

## Rime Configuration

Rime is the primary spoken-output provider.

| Field | Value |
|---|---|
| Model | `coda` |
| Speaker | `astra` |
| Language | English |
| Endpoint | `https://users.rime.ai/v1/rime-tts` |
| Audio | PCM16 |
| Transport | WebSocket streaming |

## Reproducibility

```powershell
python preflight/rime_preflight.py
pytest -q
python -m benchmark.randomized_interruption
cd ui
npm run build
cd ..
```

## Demo Evidence

```text
demo/video/VoxLock-demo.mp4

demo/screenshots/01-main-interface.png
demo/screenshots/02-interruption.png
demo/screenshots/03-superseded-request.png
demo/screenshots/04-tool-cancelled.png
demo/screenshots/05-final-result.png
```

## Failure Behavior

- **SUPERSEDED** — request invalidated before managed work exists or begins.
- **TOOL_CANCELLED** — running managed tool work is cancelled.
- **GHOST_TASK** — late work resolves after invalidation and is reconciled as stale.
- **AUDIO_BLOCKED** — stale generated audio is rejected before playback.

The system does not artificially create ghost tasks; they are recorded only when late work actually resolves after invalidation.

## Security and Scope

The transfer scenario is synthetic.

- No real banking transfer is performed.
- No payment credentials are used.
- No production financial system is connected.
- API secrets remain in environment variables.
- `.env` is excluded from Git.

## Limitations

- Task cancellation is best-effort.
- External model/network latency varies.
- Application-level interruption timing is not equivalent to physical audio transport stop latency.
- The benchmark is an application-level consistency test, not a universal latency benchmark.

## Core Invariant

> **Superseded computation may finish. Superseded intent must not become reality.**
