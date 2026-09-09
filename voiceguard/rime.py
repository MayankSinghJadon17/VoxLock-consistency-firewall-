from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Awaitable, Callable

from .types import AudioChunk
from .voiceguard import VoiceGuard


@dataclass(frozen=True)
class RimeConfig:
    endpoint: str = "wss://users.rime.ai/v1/rime-tts"
    model: str = "coda"
    voice: str = "astra"
    language: str = "en"
    audio_format: str = "pcm_s16le"
    sample_rate: int = 22050

    @classmethod
    def from_env(cls) -> "RimeConfig":
        return cls(
            endpoint=os.getenv("RIME_ENDPOINT", cls.endpoint),
            model=os.getenv("RIME_MODEL", cls.model),
            voice=os.getenv("RIME_VOICE", cls.voice),
            language=os.getenv("RIME_LANGUAGE", cls.language),
            audio_format=os.getenv("RIME_AUDIO_FORMAT", cls.audio_format),
            sample_rate=int(os.getenv("RIME_SAMPLE_RATE", str(cls.sample_rate))),
        )


class RimeStreamingClient:
    """
    Thin Rime WebSocket adapter.

    The exact provider message schema is isolated here. The consistency core does
    not know anything about WebSockets, bearer tokens, or provider payloads.
    """

    def __init__(self, guard: VoiceGuard, config: RimeConfig | None = None) -> None:
        self.guard = guard
        self.config = config or RimeConfig.from_env()

    async def stream(
        self,
        request_id: int,
        text: str,
        *,
        on_play: Callable[[bytes], Awaitable[None]],
    ) -> int:
        token = os.getenv("RIME_API_TOKEN")
        if not token:
            raise RuntimeError("RIME_API_TOKEN is required for live Rime streaming")

        try:
            import websockets
        except ImportError as exc:
            raise RuntimeError(
                'Install the Rime extra first: pip install -e ".[rime]"'
            ) from exc

        headers = {"Authorization": f"Bearer {token}"}
        played = 0

        async with websockets.connect(self.config.endpoint, additional_headers=headers) as ws:
            # Keep provider-specific schema in this file only.
            request = {
                "model": self.config.model,
                "voice": self.config.voice,
                "text": text,
                "language": self.config.language,
                "audio_format": self.config.audio_format,
            }
            await ws.send(json.dumps(request))

            sequence = 0
            async for message in ws:
                audio = self._extract_audio(message)
                if audio is None:
                    continue

                chunk = AudioChunk(
                    request_id=request_id,
                    sequence=sequence,
                    audio=audio,
                    generated_at=asyncio.get_running_loop().time(),
                )
                sequence += 1

                # Third independent firewall checkpoint: every audio chunk.
                if not await self.guard.accept_audio_chunk(chunk):
                    break

                await on_play(audio)
                played += 1

        return played

    @staticmethod
    def _extract_audio(message: str | bytes) -> bytes | None:
        # Provider response formats can evolve. Keep parsing localized.
        if isinstance(message, bytes):
            return message

        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return None

        for key in ("audio", "audio_chunk", "data"):
            value = payload.get(key)
            if isinstance(value, str):
                import base64
                try:
                    return base64.b64decode(value)
                except Exception:
                    return None
        return None
