from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    RunContext,
    cli,
    function_tool,
)
from livekit.plugins import groq, silero

from .continuity import ConversationalContinuity
from .livekit_adapter import LiveKitInterruptionBridge
from .rime_adapter import VoiceGuardRimeTTS
from .tool import search_trains, simulate_transfer
from .types import RequestState
from .voiceguard import VoiceGuard
from .ui_api import start_ui_server


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voiceguard.livekit_agent")

server = AgentServer()


class VoiceGuardAgent(Agent):
    def __init__(self, *, guard, continuity, tts, session=None):
        self._guard = guard
        self._continuity = continuity
        self._voiceguard_tts = tts
        self._agent_session = session

        super().__init__(
            instructions=(
                "You are VoiceGuard, a concise voice assistant. "
                "Answer the user's request directly. "
                "If the user changes their request, always follow the newest request. "
                "When a train search is required, use the search_train tool. "
                "When the user requests a transfer, use the transfer_money tool. "
                "Never claim that a real financial transaction occurred. "
                "Do not invent train availability."
            )
        )

    async def on_user_turn_completed(
        self,
        turn_ctx,
        new_message,
    ) -> None:
        text = getattr(new_message, "text_content", None) or ""

        if not text.strip():
            return

        request = await self._guard.begin_request(text)
        self._voiceguard_tts.set_request_id(request.request_id)

        logger.info(
            "VOICEGUARD REQUEST: id=%s text=%r source=on_user_turn_completed",
            request.request_id,
            text,
        )

    async def _speak_guarded(self, request_id, text):
        if self._guard.active_id != request_id:
            logger.info(
                "VOICEGUARD: conversational message skipped "
                "request=%s active=%s text=%r",
                request_id,
                self._guard.active_id,
                text,
            )
            return

        self._voiceguard_tts.set_request_id(request_id)

        if self._agent_session is None:
            return

        try:
            speech_handle = self._agent_session.say(
                text,
                allow_interruptions=True,
                add_to_chat_ctx=False,
            )
            await speech_handle.wait_for_playout()

        except asyncio.CancelledError:
            logger.info(
                "VOICEGUARD: conversational speech cancelled "
                "request=%s text=%r",
                request_id,
                text,
            )
            raise

    @function_tool
    async def search_train(
        self,
        context: RunContext,
        origin: str,
        destination: str,
    ) -> str:
        request_id = self._guard.active_id

        if request_id == 0:
            raise RuntimeError(
                "search_train called before a VoiceGuard request was created"
            )

        logger.info(
            "VOICEGUARD: train search starting request=%s %s -> %s",
            request_id,
            origin,
            destination,
        )

        await self._guard.set_state(
            RequestState.TOOL_RUNNING,
            request_id=request_id,
        )

        progress = await self._continuity.progress_message(
            request_id,
            state=RequestState.TOOL_RUNNING,
        )

        if progress is not None:
            logger.info(
                "VOICEGUARD: continuity request=%s text=%r",
                request_id,
                progress.text,
            )
            await self._speak_guarded(
                request_id,
                progress.text,
            )

        tool_delay = float(
            os.getenv("VOICEGUARD_TOOL_DELAY", "5.0")
        )

        if tool_delay < 0:
            raise ValueError(
                "VOICEGUARD_TOOL_DELAY must be >= 0"
            )

        logger.info(
            "VOICEGUARD: TOOL_STARTED request=%s delay=%.2fs",
            request_id,
            tool_delay,
        )

        async def operation():
            return await search_trains(
                origin,
                destination,
                min_delay=tool_delay,
                max_delay=tool_delay,
            )

        try:
            result = await self._guard.run_managed(
                request_id,
                "tool",
                operation,
            )

        except asyncio.CancelledError:
            logger.info(
                "VOICEGUARD: TOOL_CANCELLED request=%s",
                request_id,
            )
            raise

        if result is None:
            logger.info(
                "VOICEGUARD: stale train result rejected "
                "request=%s",
                request_id,
            )
            return (
                "The previous train search was superseded "
                "by a newer request."
            )

        logger.info(
            "VOICEGUARD: TOOL_RESULT_ACCEPTED request=%s",
            request_id,
        )

        logger.info(
            "VOICEGUARD: train search accepted request=%s",
            request_id,
        )

        trains = ", ".join(result.trains)

        return (
            f"Trains from {result.origin} "
            f"to {result.destination}: {trains}."
        )

    @function_tool
    async def transfer_money(
        self,
        context: RunContext,
        amount: int,
        recipient: str,
    ) -> str:
        request_id = self._guard.active_id

        if request_id == 0:
            raise RuntimeError(
                "transfer_money called before a VoiceGuard request was created"
            )

        logger.info(
            "VOICEGUARD: transfer starting request=%s amount=%s recipient=%s",
            request_id,
            amount,
            recipient,
        )

        await self._guard.set_state(
            RequestState.TOOL_RUNNING,
            request_id=request_id,
        )

        progress = await self._continuity.progress_message(
            request_id,
            state=RequestState.TOOL_RUNNING,
        )

        if progress is not None:
            await self._speak_guarded(
                request_id,
                progress.text,
            )

        tool_delay = float(
            os.getenv("VOICEGUARD_TOOL_DELAY", "5.0")
        )

        async def operation():
            return await simulate_transfer(
                amount,
                recipient,
                min_delay=tool_delay,
                max_delay=tool_delay,
            )

        try:
            result = await self._guard.run_managed(
                request_id,
                "tool",
                operation,
            )

        except asyncio.CancelledError:
            logger.info(
                "VOICEGUARD: TRANSFER_CANCELLED request=%s",
                request_id,
            )
            raise

        if result is None:
            logger.info(
                "VOICEGUARD: transfer result rejected request=%s",
                request_id,
            )
            return (
                "The previous transfer request was superseded "
                "by a newer request."
            )

        return (
            f"Simulated transfer of ₹{result.amount:,} "
            f"to {result.recipient} completed."
        )


@server.rtc_session(agent_name="voiceguard")
async def entrypoint(ctx: JobContext):
    await ctx.connect()

    guard = VoiceGuard()

    demo_start_event = asyncio.Event()
    intro_complete = asyncio.Event()

    session_holder: dict[str, AgentSession | None] = {
        "session": None
    }

    # ---------------------------------------------------------
    # Persistent LiveKit session.
    #
    # IMPORTANT:
    # Do NOT destroy/recreate AgentSession on every START/STOP.
    # The LiveKit session stays alive for the lifetime of the job.
    # START/STOP only enables/disables the demo interaction.
    # ---------------------------------------------------------

    bridge = LiveKitInterruptionBridge(guard)

    tts = VoiceGuardRimeTTS(guard)
    tts.prewarm()

    logger.info(
        "VOICEGUARD RIME: WebSocket prewarm requested"
    )

    continuity = ConversationalContinuity(guard)

    session = AgentSession(
        stt=groq.STT(
            model="whisper-large-v3-turbo",
            language="en",
        ),
        llm=groq.LLM(
            model="openai/gpt-oss-20b",
        ),
        tts=tts,
        vad=silero.VAD.load(),
        allow_interruptions=True,
        min_interruption_duration=0.2,
        min_interruption_words=0,
    )

    session_holder["session"] = session

    agent = VoiceGuardAgent(
        guard=guard,
        continuity=continuity,
        tts=tts,
        session=session,
    )

    # ---------------------------------------------------------
    # STOP DEMO
    # ---------------------------------------------------------

    async def stop_demo():
        logger.info("VOICEGUARD: STOP DEMO received")

        try:
            await session.interrupt(force=True)
        except Exception:
            pass

        try:
            session.input.set_audio_enabled(False)
        except Exception:
            pass

        intro_complete.clear()

        await guard.reset_for_demo()

        logger.info(
            "VOICEGUARD: microphone disabled"
        )

        logger.info(
            "VOICEGUARD: demo reset; ready for START DEMO"
        )

    # ---------------------------------------------------------
    # LIVEKIT EVENTS
    # ---------------------------------------------------------

    @session.on("speech_created")
    def on_speech_created(event):
        """
        Bind LiveKit's automatic response SpeechHandle to the
        VoiceGuard request that is currently active.

        generate_reply is the normal AgentSession response path.
        session.say() is used separately for guarded progress
        messages and should not be rebound here.
        """
        if getattr(event, "source", None) != "generate_reply":
            return

        speech_handle = getattr(event, "speech_handle", None)

        if speech_handle is None:
            logger.warning(
                "VOICEGUARD: speech_created without SpeechHandle"
            )
            return

        request_id = guard.active_id

        if request_id == 0:
            logger.info(
                "VOICEGUARD: speech_created ignored; "
                "no active request"
            )
            return

        logger.info(
            "VOICEGUARD: speech_created "
            "source=%s request=%s",
            getattr(event, "source", None),
            request_id,
        )

        bridge.bind_speech(
            speech_handle,
            request_id,
        )


    @session.on("user_state_changed")
    def on_user_state_changed(event):
        if getattr(event, "new_state", None) != "speaking":
            return

        logger.info(
            "VOICEGUARD: LiveKit user_state_changed -> speaking"
        )

        asyncio.create_task(
            bridge.on_user_speaking(event)
        )

    @session.on("overlapping_speech")
    def on_overlapping_speech(event):
        if not getattr(event, "is_interruption", False):
            return

        logger.info(
            "VOICEGUARD: LiveKit overlapping speech "
            "is_interruption=%s",
            getattr(event, "is_interruption", None),
        )

        asyncio.create_task(
            bridge.on_vad_interrupt(event)
        )

    @session.on("user_input_transcribed")
    def on_user_input(event):
        # Keep this log BEFORE the intro gate.
        # It proves whether STT is still producing events
        # after a STOP -> START cycle.
        logger.info(
            "VOICEGUARD STT EVENT: final=%s transcript=%r",
            getattr(event, "is_final", False),
            getattr(event, "transcript", ""),
        )

        if not intro_complete.is_set():
            return

        if not getattr(event, "is_final", False):
            return

        text = getattr(event, "transcript", "") or ""

        if not text.strip():
            return

        logger.info(
            "USER INPUT: %s",
            text,
        )

        @session.on("user_input_transcribed")
        def on_user_input(event):
            logger.info(
                "VOICEGUARD STT EVENT: final=%s transcript=%r",
                getattr(event, "is_final", False),
                getattr(event, "transcript", ""),
            )

    # ---------------------------------------------------------
    # START THE LIVEKIT SESSION ONCE
    # ---------------------------------------------------------

    await session.start(
        room=ctx.room,
        agent=agent,
    )

    session.input.set_audio_enabled(False)

    logger.info(
        "VOICEGUARD: persistent session started"
    )

    logger.info(
        "VOICEGUARD: microphone disabled until START DEMO"
    )

    # ---------------------------------------------------------
    # START/STOP DEMO LOOP
    # ---------------------------------------------------------

    await start_ui_server(
        guard,
        demo_start_event,
        stop_demo,
    )

    logger.info(
        "VOICEGUARD UI: server started on "
        "http://127.0.0.1:8765"
    )

    while True:
        logger.info(
            "VOICEGUARD: waiting for START DEMO"
        )

        await demo_start_event.wait()
        demo_start_event.clear()

        logger.info(
            "VOICEGUARD: START DEMO received"
        )

        # Reset VoiceGuard state but KEEP the LiveKit session alive.
        await guard.reset_for_demo()

        intro_complete.clear()

        bridge.reset_interruption()

        # Enable microphone for the new demo cycle.
        session.input.set_audio_enabled(True)

        logger.info(
            "VOICEGUARD: microphone enabled"
        )

        # -----------------------------------------------------
        # Intro request
        # -----------------------------------------------------

        request = await guard.begin_request(
            "Introduce yourself and explain what VoiceGuard does."
        )

        logger.info(
            "VOICEGUARD: initial request id=%s",
            request.request_id,
        )

        tts.set_request_id(
            request.request_id
        )

        logger.info(
            "VOICEGUARD: calling generate_reply"
        )

        try:
            await session.generate_reply(
                instructions=(
                    "Say exactly: "
                    "VoiceGuard prevents outdated work "
                    "from becoming spoken reality."
                )
            )

            intro_complete.set()

            logger.info(
                "VOICEGUARD: demo intro complete; "
                "listening enabled"
            )

        except asyncio.CancelledError:
            logger.info(
                "VOICEGUARD: demo intro cancelled"
            )

        # -----------------------------------------------------
        # Do NOT wait for/close the session here.
        #
        # The outer loop simply waits for STOP -> START.
        # The persistent AgentSession continues receiving STT
        # events and processing normal user turns.
        # -----------------------------------------------------


if __name__ == "__main__":
    cli.run_app(server)
