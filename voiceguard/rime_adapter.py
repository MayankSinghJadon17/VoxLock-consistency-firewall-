from __future__ import annotations

import asyncio
import logging
import time

from livekit.agents import APIConnectOptions
from livekit.agents.tts import AudioEmitter, SynthesizeStream
from livekit.plugins import rime

from .types import AudioChunk
from .voiceguard import VoiceGuard

log = logging.getLogger(__name__)




class VoiceGuardRimeStream(SynthesizeStream):
    def __init__(self, *, tts, inner, request_id, conn_options):
        super().__init__(tts=tts, conn_options=conn_options)
        self._inner = inner
        self._request_id = request_id
        self._sequence = 0

    def push_text(self, token: str) -> None:
        """Forward LiveKit TTS text into the real Rime stream."""
        self._inner.push_text(token)

    def flush(self) -> None:
        """Forward segment boundary to Rime."""
        self._inner.flush()

    def end_input(self) -> None:
        """Forward end-of-input to Rime."""
        self._inner.end_input()

    async def _run(self, output_emitter):
        request_id = self._request_id

        output_emitter.initialize(
            request_id=str(request_id),
            sample_rate=self._tts.sample_rate,
            num_channels=1,
            mime_type="audio/pcm",
            stream=True,
        )

        output_emitter.start_segment(segment_id=f"voiceguard-{request_id}")

        try:
            async for synthesized in self._inner:
                frame = synthesized.frame

                sequence = self._sequence
                self._sequence += 1

                chunk = AudioChunk(
                    request_id=request_id,
                    sequence=sequence,
                    audio=bytes(frame.data),
                    generated_at=time.monotonic(),
                )

                accepted = await self._tts.guard.accept_audio_chunk(chunk)

                if not accepted:
                    log.info(
                        "VOICEGUARD: rejected stale Rime audio "
                        "request=%s sequence=%s",
                        request_id,
                        sequence,
                    )
                    break

                output_emitter.push(bytes(frame.data))

        except asyncio.CancelledError:
            log.info(
                "VOICEGUARD: Rime stream cancelled request=%s",
                request_id,
            )
            raise

        except Exception:
            if request_id != self._tts.guard.active_id:
                log.info(
                    "VOICEGUARD: stale Rime stream terminated "
                    "request=%s active=%s",
                    request_id,
                    self._tts.guard.active_id,
                )
                return
            raise

        finally:
            await self._inner.aclose()

class VoiceGuardRimeTTS(rime.TTS):
    """
    Official Rime TTS with VoiceGuard audio fencing.

    Rime remains the actual speech provider.
    VoiceGuard only controls whether generated audio is allowed
    to reach LiveKit playback.
    """

    def __init__(
        self,
        guard: VoiceGuard,
    ) -> None:
        super().__init__(
            model="coda",
            speaker="astra",
            use_websocket=True,
            segment="immediate",
            sample_rate=22050,
        )

        self.guard = guard
        self._request_id: int | None = None

    def set_request_id(self, request_id: int) -> None:
        self._request_id = request_id

    def stream(self, *, conn_options=APIConnectOptions()):
        request_id = self._request_id or self.guard.active_id

        log.info(
            "VOICEGUARD RIME: stream requested request_id=%s active_id=%s",
            request_id,
            self.guard.active_id,
        )

        if request_id == 0:
            raise RuntimeError(
                "Rime TTS stream created before a VoiceGuard request was started"
            )

        inner = super().stream(conn_options=conn_options)

        log.info(
            "VOICEGUARD RIME: underlying Rime stream created request_id=%s",
            request_id,
        )

        return VoiceGuardRimeStream(
            tts=self,
            inner=inner,
            request_id=request_id,
            conn_options=conn_options,
        )
