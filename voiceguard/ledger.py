from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


@dataclass
class LedgerEvent:
    kind: str
    request_id: int
    at: float
    payload: dict[str, Any]


class HeardStateLedger:
    """Append-only in-memory ledger; optionally exportable as JSON."""

    def __init__(self) -> None:
        self.events: list[LedgerEvent] = []

    def record(self, kind: str, request_id: int, **payload: Any) -> None:
        self.events.append(
            LedgerEvent(kind=kind, request_id=request_id, at=time.monotonic(), payload=payload)
        )


    def request_started(self, request_id: int, user_text: str) -> None:
        self.record("request_started", request_id, user_text=user_text)

    def constraint_diff(
        self,
        old_request_id: int,
        new_request_id: int,
        old_text: str,
        new_text: str,
    ) -> None:
        old_words = old_text.split()
        new_words = new_text.split()

        matcher = SequenceMatcher(None, old_words, new_words)
        changes: list[dict[str, Any]] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue

            changes.append(
                {
                    "operation": tag,
                    "old": " ".join(old_words[i1:i2]),
                    "new": " ".join(new_words[j1:j2]),
                }
            )

        self.record(
            "constraint_diff",
            new_request_id,
            previous_request_id=old_request_id,
            old_text=old_text,
            new_text=new_text,
            changes=changes,
        )

    def generated(self, request_id: int, text: str) -> None:
        self.record("generated_text", request_id, text=text)

    def completed(self, request_id: int) -> None:
        self.record("request_completed", request_id)

    def chunk_generated(self, request_id: int, sequence: int) -> None:
        self.record("audio_chunk_generated", request_id, sequence=sequence)

    def chunk_played(self, request_id: int, sequence: int) -> None:
        self.record("audio_chunk_played", request_id, sequence=sequence)

    def chunk_rejected(self, request_id: int, sequence: int, reason: str) -> None:
        self.record("audio_chunk_rejected", request_id, sequence=sequence, reason=reason)

    def interrupted(self, request_id: int, replacement_request_id: int, reason: str) -> None:
        self.record(
            "interrupt",
            request_id,
            replacement_request_id=replacement_request_id,
            reason=reason,
        )

    def interruption_latency(
        self,
        request_id: int,
        started_at: float,
        completed_at: float,
    ) -> None:
        latency_ms = max(0.0, (completed_at - started_at) * 1000.0)

        self.record(
            "interrupt_latency",
            request_id,
            latency_ms=latency_ms,
        )

    def ghost(self, request_id: int, stage: str, reason: str) -> None:
        self.record("ghost_task", request_id, stage=stage, reason=reason)

    def tool_started(self, request_id: int) -> None:
        self.record("tool_started", request_id)

    def tool_completed(self, request_id: int) -> None:
        self.record("tool_completed", request_id)

    def tool_cancelled(self, request_id: int) -> None:
        self.record("tool_cancelled", request_id)

    def tool_result_accepted(self, request_id: int) -> None:
        self.record("tool_result_accepted", request_id)

    def export(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([asdict(event) for event in self.events], indent=2),
            encoding="utf-8",
        )

    def events_for(self, request_id: int) -> list[LedgerEvent]:
        return [e for e in self.events if e.request_id == request_id]

    def played_sequences(self, request_id: int) -> list[int]:
        return [
            int(e.payload["sequence"])
            for e in self.events_for(request_id)
            if e.kind == "audio_chunk_played"
        ]

    def ghost_tasks(self, request_id: int | None = None) -> list[LedgerEvent]:
        events = [event for event in self.events if event.kind == "ghost_task"]
        if request_id is not None:
            events = [event for event in events if event.request_id == request_id]
        return events

    def timeline(self, request_id: int | None = None) -> list[LedgerEvent]:
        events = self.events
        if request_id is not None:
            events = [
                event for event in events
                if event.request_id == request_id
            ]
        return sorted(events, key=lambda event: event.at)

    def heard_summary(self, request_id: int) -> dict[str, Any]:
        events = self.events_for(request_id)

        started = next(
            (event for event in events if event.kind == "request_started"),
            None,
        )
        generated_text = [
            event.payload["text"]
            for event in events
            if event.kind == "generated_text"
        ]
        generated_chunks = [
            event for event in events if event.kind == "audio_chunk_generated"
        ]
        played_chunks = [
            event for event in events if event.kind == "audio_chunk_played"
        ]
        rejected_chunks = [
            event for event in events if event.kind == "audio_chunk_rejected"
        ]
        interrupts = [event for event in events if event.kind == "interrupt"]
        completed = any(event.kind == "request_completed" for event in events)
        cancelled = any(event.kind == "tool_cancelled" for event in events)

        if interrupts:
            status = "SUPERSEDED"
        elif cancelled:
            status = "CANCELLED"
        elif completed:
            status = "COMPLETED"
        else:
            status = "ACTIVE"

        return {
            "request_id": request_id,
            "user_text": (started.payload.get("user_text", "") if started else ""),
            "generated_text": generated_text[-1] if generated_text else "",
            "generated_chunks": len(generated_chunks),
            "played_chunks": len(played_chunks),
            "rejected_chunks": len(rejected_chunks),
            "played_sequences": [int(event.payload["sequence"]) for event in played_chunks],
            "rejected_sequences": [int(event.payload["sequence"]) for event in rejected_chunks],
            "interrupted": bool(interrupts),
            "interrupt_at": interrupts[-1].at if interrupts else None,
            "status": status,
        }

    def request_entry(self, request_id: int) -> dict[str, Any]:
        """Return the compact per-request Heard-State Ledger entry."""
        summary = self.heard_summary(request_id)
        return {
            "request_id": request_id,
            "generated_text": summary["generated_text"],
            "played_chunks": summary["played_chunks"],
            "rejected_chunks": summary["rejected_chunks"],
            "interrupted": summary["interrupted"],
            "interrupt_at": summary["interrupt_at"],
            "status": summary["status"],
        }

    def request_entries(self) -> list[dict[str, Any]]:
        """Return one compact Heard-State entry per request, in request order."""
        request_ids = sorted({event.request_id for event in self.events})
        return [self.request_entry(request_id) for request_id in request_ids]

    def format_heard_summary(self, request_id: int) -> str:
        summary = self.heard_summary(request_id)

        lines = [
            f"REQUEST #{request_id}",
            f"Generated chunks : {summary['generated_chunks']}",
            f"Played chunks    : {summary['played_chunks']}",
            f"Rejected chunks  : {summary['rejected_chunks']}",
            f"Played sequences : {summary['played_sequences']}",
            f"Rejected seqs    : {summary['rejected_sequences']}",
        ]

        if summary["generated_text"]:
            lines.append(f"Generated text   : {summary['generated_text']}")

        if summary["interrupted"]:
            lines.append("Interrupted      : YES")
            lines.append(f"Interrupt at     : {summary['interrupt_at']:.6f}")

        return "\n".join(lines)


    def format_timeline(self, request_id: int | None = None) -> str:
        lines = []

        for event in self.timeline(request_id):
            payload = event.payload

            if event.kind == "interrupt":
                lines.append(
                    f"[{event.request_id}] INTERRUPT "
                    f"-> replacement={payload['replacement_request_id']}"
                )

            elif event.kind == "ghost_task":
                lines.append(
                    f"[{event.request_id}] GHOST_TASK "
                    f"-> {payload['stage']} / {payload['reason']}"
                )

            elif event.kind == "tool_started":
                lines.append(f"[{event.request_id}] TOOL_STARTED")

            elif event.kind == "tool_completed":
                lines.append(f"[{event.request_id}] TOOL_COMPLETED")

            elif event.kind == "tool_cancelled":
                lines.append(f"[{event.request_id}] TOOL_CANCELLED")

            elif event.kind == "tool_result_accepted":
                lines.append(
                    f"[{event.request_id}] TOOL_RESULT_ACCEPTED"
                )

            elif event.kind == "generated_text":
                lines.append(f"[{event.request_id}] LLM_GENERATED")

            elif event.kind == "audio_chunk_generated":
                lines.append(
                    f"[{event.request_id}] AUDIO_GENERATED "
                    f"chunk={payload['sequence']}"
                )

            elif event.kind == "audio_chunk_played":
                lines.append(
                    f"[{event.request_id}] AUDIO_PLAYED "
                    f"chunk={payload['sequence']}"
                )

            elif event.kind == "audio_chunk_rejected":
                lines.append(
                    f"[{event.request_id}] AUDIO_REJECTED "
                    f"chunk={payload['sequence']}"
                )

        return "\n".join(lines)
