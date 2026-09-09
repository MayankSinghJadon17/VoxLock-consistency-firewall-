from __future__ import annotations

from dataclasses import dataclass

from .types import RequestState
from .voiceguard import VoiceGuard


@dataclass(frozen=True)
class ContinuityMessage:
    request_id: int
    text: str
    stage: str


class ConversationalContinuity:
    """
    Generates controlled progress/backchannel speech for a VoiceGuard request.

    Continuity messages are treated as versioned output. A message is only
    valid while its request_id remains the active VoiceGuard generation.

    Deliberately contains NO LiveKit imports.
    """

    def __init__(self, guard: VoiceGuard) -> None:
        self.guard = guard

    async def progress_message(
        self,
        request_id: int,
        *,
        state: RequestState,
    ) -> ContinuityMessage | None:
        """
        Return a state-appropriate progress message.

        The message is fenced before being returned. If the request has already
        been superseded, no stale continuity speech is produced.
        """

        decision = await self.guard.fence(
            request_id,
            "continuity_message",
        )

        if not decision.accepted:
            return None

        text = self._message_for_state(state)

        if text is None:
            return None

        return ContinuityMessage(
            request_id=request_id,
            text=text,
            stage=state.value,
        )

    async def backchannel(
        self,
        request_id: int,
        *,
        state: RequestState,
    ) -> ContinuityMessage | None:
        """
        Return a short acknowledgement appropriate for the current state.

        This is intentionally deterministic. We do not want random filler
        becoming another source of inconsistent speech.
        """

        decision = await self.guard.fence(
            request_id,
            "continuity_backchannel",
        )

        if not decision.accepted:
            return None

        text = self._backchannel_for_state(state)

        if text is None:
            return None

        return ContinuityMessage(
            request_id=request_id,
            text=text,
            stage=state.value,
        )

    @staticmethod
    def _message_for_state(
        state: RequestState,
    ) -> str | None:
        messages = {
            RequestState.THINKING: "Sure, give me a second while I check.",
            RequestState.TOOL_RUNNING: "Let me check that for you.",
            RequestState.RESPONDING: "One moment, I'm still checking.",
            RequestState.LISTENING: None,
            RequestState.IDLE: None,
        }

        return messages.get(state)

    @staticmethod
    def _backchannel_for_state(
        state: RequestState,
    ) -> str | None:
        messages = {
            RequestState.LISTENING: "Got it.",
            RequestState.THINKING: "Okay.",
            RequestState.TOOL_RUNNING: "I’m on it.",
            RequestState.RESPONDING: None,
            RequestState.IDLE: None,
        }

        return messages.get(state)