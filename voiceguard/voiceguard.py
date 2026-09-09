from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

from .ledger import HeardStateLedger
from .types import AudioChunk, FirewallDecision, InterruptEvent, RequestContext, RequestState, RequestStats

log = logging.getLogger(__name__)


@dataclass
class ActiveTask:
    request_id: int
    task: asyncio.Task
    stage: str


class VoiceGuard:
    """
    Application-level consistency firewall.

    Deliberately contains NO LiveKit imports.
    Transport-level interruption and application-level invalidation are separate.
    """

    def __init__(self, *, ledger: HeardStateLedger | None = None) -> None:
        self._lock = asyncio.Lock()
        self._next_request_id = 0
        self._active_id = 0
        self._state = RequestState.IDLE
        self._active_task: ActiveTask | None = None
        self._context: RequestContext | None = None
        self._stats: dict[int, RequestStats] = {}
        self.ledger = ledger or HeardStateLedger()
        self.interrupts: list[InterruptEvent] = []


    async def reset_for_demo(self) -> None:
        """Reset active execution state so a new demo can start cleanly."""
        async with self._lock:
            if self._active_task and not self._active_task.task.done():
                self._active_task.task.cancel()

            self._active_task = None
            self._active_id = 0
            self._state = RequestState.IDLE
            self._context = None
            self._stats.clear()
            self.interrupts.clear()
    @property
    def active_id(self) -> int:
        return self._active_id

    @property
    def state(self) -> RequestState:
        return self._state

    @property
    def active_task(self) -> ActiveTask | None:
        return self._active_task

    async def begin_request(self, user_text: str) -> RequestContext:
        async with self._lock:
            previous_id = self._active_id
            previous_context = self._context

            self._next_request_id += 1
            self._active_id = self._next_request_id
            self._state = RequestState.LISTENING

            self._context = RequestContext(
                request_id=self._active_id,
                user_text=user_text,
                created_at=time.monotonic(),
            )

            self._stats[self._active_id] = RequestStats()

            self.ledger.request_started(
                self._active_id,
                user_text,
            )

            if previous_id != 0 and previous_context is not None:
                self.ledger.constraint_diff(
                    previous_id,
                    self._active_id,
                    previous_context.user_text,
                    user_text,
                )

            self.ledger.record(
                "state_changed",
                self._active_id,
                state=self._state.value,
            )

            return self._context

    async def set_state(self, state: RequestState, *, request_id: int | None = None) -> None:
        async with self._lock:
            rid = self._active_id if request_id is None else request_id
            if rid == self._active_id and self._state != state:
                self._state = state
                self.ledger.record("state_changed", rid, state=state.value)

    async def register_task(self, task: asyncio.Task, *, request_id: int, stage: str) -> None:
        async with self._lock:
            if request_id != self._active_id:
                task.cancel()
                return
            self._active_task = ActiveTask(request_id=request_id, task=task, stage=stage)

    async def clear_task(self, task: asyncio.Task) -> None:
        async with self._lock:
            if self._active_task and self._active_task.task is task:
                self._active_task = None

    async def on_interrupt(self, *, reason: str = "user_interrupt") -> None:
        """
        Invalidate the current request and explicitly cancel its in-flight task.

        An interruption does NOT create a new request ID.
        The next finalized user transcript creates the new request.
        """
        async with self._lock:
            interrupted_id = self._active_id

            if interrupted_id == 0:
                return

            self._active_id = 0
            self._state = RequestState.LISTENING

            old_task = self._active_task
            self._active_task = None

            event = InterruptEvent(
                interrupted_request_id=interrupted_id,
                replacement_request_id=0,
                at=time.monotonic(),
                reason=reason,
            )

            self.interrupts.append(event)
            self.ledger.interrupted(
                interrupted_id,
                0,
                reason,
            )

            if old_task and not old_task.task.done():
                old_task.task.cancel()

    async def fence(
        self,
        request_id: int,
        checkpoint: str,
        *,
        detail: str = "",
    ) -> FirewallDecision:
        async with self._lock:
            accepted = request_id == self._active_id
            decision = FirewallDecision(
                accepted=accepted,
                request_id=request_id,
                checkpoint=checkpoint,
                reason="active" if accepted else "superseded",
            )
            if not accepted:
                self.ledger.ghost(request_id, checkpoint, detail or "superseded request rejected")
            return decision

    async def accept_tool_result(self, request_id: int, result: object) -> bool:
        decision = await self.fence(request_id, "tool_result")

        if decision.accepted:
            self.ledger.tool_result_accepted(request_id)

        return decision.accepted

    async def accept_llm_output(self, request_id: int, text: str) -> bool:
        decision = await self.fence(request_id, "llm_output")
        if decision.accepted:
            self._stats[request_id].generated_text = text
            self.ledger.generated(request_id, text)
        return decision.accepted

    async def accept_audio_chunk(self, chunk: AudioChunk) -> bool:
        decision = await self.fence(chunk.request_id, "audio_chunk", detail=f"sequence={chunk.sequence}")
        self._stats.setdefault(chunk.request_id, RequestStats()).generated_chunks += 1
        self.ledger.chunk_generated(chunk.request_id, chunk.sequence)
        if decision.accepted:
            self._stats[chunk.request_id].played_chunks += 1
            self.ledger.chunk_played(chunk.request_id, chunk.sequence)
            return True

        self._stats[chunk.request_id].rejected_chunks += 1
        self.ledger.chunk_rejected(chunk.request_id, chunk.sequence, decision.reason)
        return False

    def stats(self, request_id: int) -> RequestStats:
        return self._stats.setdefault(request_id, RequestStats())

    async def run_managed(
        self,
        request_id: int,
        stage: str,
        operation: Callable[[], Awaitable[object]],
    ) -> object | None:
        """Run an operation as the current cancellable task and fence its result."""
        task = asyncio.current_task()
        assert task is not None
        await self.register_task(task, request_id=request_id, stage=stage)

        try:
            if stage == "tool":
                self.ledger.tool_started(request_id)

            result = await operation()

            if stage == "tool":
                self.ledger.tool_completed(request_id)
                accepted = await self.accept_tool_result(request_id, result)
            elif stage == "llm":
                accepted = await self.accept_llm_output(request_id, str(result))
            else:
                decision = await self.fence(request_id, stage)
                accepted = decision.accepted

            if accepted:
                self.ledger.completed(request_id)
            return result if accepted else None


        except asyncio.CancelledError:
            if stage == "tool":
                self.ledger.tool_cancelled(request_id)

            # Expected path on user interruption.
            raise

        except Exception:
            if request_id != self.active_id:
                self.ledger.ghost(request_id, stage, "late exception from superseded task")
            raise
        finally:
            await self.clear_task(task)

    async def play_stream(
        self,
        request_id: int,
        chunks: list[bytes],
        *,
        on_play: Callable[[bytes], Awaitable[None]],
        inter_chunk_delay: float = 0.0,
    ) -> int:
        played = 0
        for sequence, audio in enumerate(chunks):
            chunk = AudioChunk(
                request_id=request_id,
                sequence=sequence,
                audio=audio,
                generated_at=time.monotonic(),
            )
            if not await self.accept_audio_chunk(chunk):
                break
            await on_play(audio)
            played += 1
            if inter_chunk_delay:
                await asyncio.sleep(inter_chunk_delay)
        return played
