from __future__ import annotations

import json
import os
import sys
from urllib.request import Request, urlopen

CATALOG_URL = "https://users.rime.ai/data/voices/all-v2.json"


def main() -> None:
    target_model = os.getenv("RIME_MODEL", "coda")
    target_voice = os.getenv("RIME_VOICE", "astra")

    request = Request(CATALOG_URL, headers={"User-Agent": "VoiceGuard-preflight/0.1"})
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
    except Exception as exc:
        print(f"Rime preflight FAILED: unable to fetch {CATALOG_URL}: {exc}", file=sys.stderr)
        raise SystemExit(1)

    try:
        catalog = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Rime preflight FAILED: invalid JSON: {exc}", file=sys.stderr)
        raise SystemExit(1)

    text = json.dumps(catalog).lower()
    model_ok = target_model.lower() in text
    voice_ok = target_voice.lower() in text

    print(f"catalog_url={CATALOG_URL}")
    print(f"target_model={target_model}")
    print(f"target_voice={target_voice}")
    print(f"model_present={model_ok}")
    print(f"voice_present={voice_ok}")

    if not (model_ok and voice_ok):
        print("Rime preflight FAILED: target model/voice not found.", file=sys.stderr)
        raise SystemExit(1)

    print("Rime preflight PASSED")


if __name__ == "__main__":
    main()
