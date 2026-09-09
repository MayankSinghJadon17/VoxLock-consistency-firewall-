# VoxLock

> VoxLock is a consistency firewall for voice agents that tracks what the user actually heard, not just what the system generated, and guarantees no superseded work becomes spoken reality.

## The problem

Voice agents can be interrupted while they are:

- waiting for a tool,
- generating an LLM response,
- producing TTS audio,
- or already streaming audio toward playback.

Cancelling the visible response is not enough.

A stale tool result or already-buffered TTS chunk can still arrive after the user has changed their request.

VoxLock treats interruption as a **semantic supersession event** and applies the same request version to every downstream operation.

```text
INTERRUPTION
     ↓
SUPERSESSION
     ↓
OBSOLETE WORK
     ↓
STALE AUDIO
     ↓
✕ SPOKEN LEAK





<img width="1206" height="768" alt="Gemini_Generated_Image_doxz7pdoxz7pdoxz" src="https://github.com/user-attachments/assets/bb551cc1-ac40-4aae-9e28-d21138747766" />
