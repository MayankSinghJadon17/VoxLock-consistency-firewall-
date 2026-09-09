# VoiceGuard



> VoiceGuard is a consistency layer for voice agents that tracks what the user actually heard, not just what the system generated, and guarantees no superseded work becomes spoken reality.



## The problem



Voice agents can be interrupted while they are:



- waiting for a tool,

- generating an LLM response,

- producing TTS audio,

- or already streaming audio toward playback.



Cancelling the visible response is not enough.



A stale tool result or already-buffered TTS chunk can still arrive after the user has changed their request.



VoiceGuard treats interruption as a \*\*semantic supersession event\*\* and applies the same request version to every downstream operation.



```text

INTERRUPTION

\&#x20;    ↓

SUPERSESSION

\&#x20;    ↓

OBSOLETE WORK

\&#x20;    ↓

STALE AUDIO

\&#x20;    ↓

❌ SPOKEN LEAK
