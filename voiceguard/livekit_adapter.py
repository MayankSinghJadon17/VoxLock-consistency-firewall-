from __future__ import annotations

import asyncio
import time
import logging
from typing import Any

from .voiceguard import VoiceGuard
from .types import RequestState

log = logging.getLogger(__name__)


class LiveKitInterruptionBridge:
    """
    Boundary between LiveKit's transport/turn detection and VoiceGuard.

    LiveKit owns:
      - VAD
      - overlap/interruption detection
      - stopping agent speech

    VoiceGuard owns:
      - request invalidation
      - asyncio.Task cancellation
      - request fencing
      - stale-result rejection
      - Heard-State Ledger

    The bridge additionally binds a LiveKit SpeechHandle to the
    VoiceGuard request that created it.

    voiceguard.py itself must never import LiveKit.
    """

    def __init__(self, guard: VoiceGuard) -> None:
        self.guard = guard

        # Prevent user_state_changed + overlapping_speech
        # from committing two interruptions for the same user turn.
        self._interruption_committed = False

        # LiveKit speech currently associated with the active
        # VoiceGuard request.
        self._speech_handle: Any | None = None
        self._speech_request_id: int = 0

    @property
    def interruption_committed(self) -> bool:
        return self._interruption_committed

    def reset_interruption(self) -> None:
        """Allow the next user turn to commit a new interruption."""
        self._interruption_committed = False

    def bind_speech(
        self,
        speech_handle: Any,
        request_id: int,
    ) -> None:
        """
        Bind one LiveKit SpeechHandle to one VoiceGuard request.

        A new request always replaces the bridge's previous speech
        ownership. The previous handle may still finish internally,
        but it must never be considered interruptible speech for the
        new request.
        """
        if request_id == 0:
            return

        if request_id != self.guard.active_id:
            log.info(
                "VOICEGUARD: refusing speech binding "
                "request=%s active=%s",
                request_id,
                self.guard.active_id,
            )
            return

        # Retire any handle belonging to an older request.
        previous_handle = self._speech_handle
        previous_request_id = self._speech_request_id

        if previous_handle is not None and previous_request_id != request_id:
            self._speech_handle = None
            self._speech_request_id = 0

            log.info(
                "VOICEGUARD: retired stale speech handle "
                "old_request=%s new_request=%s",
                previous_request_id,
                request_id,
            )

        # New handle now owns the bridge.
        self._speech_handle = speech_handle
        self._speech_request_id = request_id

        log.info(
            "VOICEGUARD: speech handle bound "
            "request=%s",
            request_id,
        )

        def clear_handle(_task: Any) -> None:
            if self._speech_handle is speech_handle:
                self._speech_handle = None
                self._speech_request_id = 0

                log.info(
                    "VOICEGUARD: speech handle cleared "
                    "request=%s",
                    request_id,
                )

        async def watch_completion() -> None:
            try:
                await speech_handle.wait_for_playout()
            except Exception:
                pass
            finally:
                clear_handle(None)

        asyncio.create_task(watch_completion())

    async def _interrupt_bound_speech(
        self,
        request_id: int,
    ) -> None:
        """
        Stop the exact LiveKit speech handle belonging to request_id.
        """
        speech_handle = self._speech_handle
        speech_request_id = self._speech_request_id

        if speech_handle is None:
            return

        if speech_request_id != request_id:
            log.info(
                "VOICEGUARD: speech handle ownership mismatch "
                "handle_request=%s interrupt_request=%s",
                speech_request_id,
                request_id,
            )
            return

        self._speech_handle = None
        self._speech_request_id = 0

        log.info(
            "VOICEGUARD: interrupting bound speech "
            "request=%s",
            request_id,
        )

        try:
            speech_handle.interrupt(force=True)
        except Exception:
            log.exception(
                "VOICEGUARD: failed to interrupt "
                "speech handle request=%s",
                request_id,
            )

    async def _commit_interrupt(
        self,
        *,
        reason: str,
        source: str,
    ) -> None:
        active_id = self.guard.active_id
        state = self.guard.state

        if active_id == 0:
            return

        if self._interruption_committed:
            log.info(
                "VOICEGUARD: duplicate interruption ignored "
                "source=%s active_request=%s",
                source,
                active_id,
            )
            return

        cancellable_states = {
            RequestState.THINKING,
            RequestState.TOOL_RUNNING,
            RequestState.RESPONDING,
        }

        if state not in cancellable_states:
            return

        self._interruption_committed = True

        started_at = time.monotonic()

        log.info(
            "VOICEGUARD: committing interruption "
            "source=%s old_request=%s state=%s",
            source,
            active_id,
            state.value,
        )

        # Stop LiveKit's exact speech object first.
        await self._interrupt_bound_speech(active_id)

        # Then invalidate the application-level request.
        await self.guard.on_interrupt(
            reason=reason,
        )

        completed_at = time.monotonic()

        self.guard.ledger.interruption_latency(
            active_id,
            started_at,
            completed_at,
        )

        latency_ms = (completed_at - started_at) * 1000.0

        log.info(
            "VOICEGUARD: interruption committed "
            "old_request=%s latency_ms=%.2f",
            active_id,
            latency_ms,
        )

    async def on_user_speaking(
        self,
        event: Any | None = None,
    ) -> None:
        await self._commit_interrupt(
            reason="livekit_user_speech",
            source="user_state_changed",
        )

    async def on_vad_interrupt(
        self,
        event: Any | None = None,
    ) -> None:
        await self._commit_interrupt(
            reason="livekit_vad",
            source="overlapping_speech",
        )