import asyncio
from dotenv import load_dotenv
from livekit.plugins import rime

load_dotenv()


async def main():
    tts = rime.TTS(
        model="coda",
        speaker="astra",
        use_websocket=True,
        segment="immediate",
        sample_rate=22050,
    )

    print("Provider:", tts.provider)
    print("Model:", tts.model)
    print("Rime TTS initialized successfully")

    await tts.aclose()


if __name__ == "__main__":
    asyncio.run(main())