from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RequestState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    TOOL_RUNNING = "TOOL_RUNNING"
    RESPONDING = "RESPONDING"


@dataclass(frozen=True)
class RequestContext:
    request_id: int
    user_text: str
    created_at: float


@dataclass(frozen=True)
class AudioChunk:
    request_id: int
    sequence: int
    audio: bytes
    generated_at: float


@dataclass(frozen=True)
class FirewallDecision:
    accepted: bool
    request_id: int
    checkpoint: str
    reason: str


@dataclass
class InterruptEvent:
    interrupted_request_id: int
    replacement_request_id: int
    at: float
    reason: str


@dataclass
class RequestStats:
    generated_text: str = ""
    generated_chunks: int = 0
    played_chunks: int = 0
    rejected_chunks: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
