# Rime Evidence

## VoiceGuard Rime Integration

VoiceGuard uses Rime as the primary spoken-output path.

### Production Configuration

| Setting | Value |
|---|---|
| Model | `coda` |
| Speaker | `astra` |
| Transport | WebSocket |
| Segmentation | `immediate` |
| Sample rate | `22050 Hz` |
| Authentication | Server-side `RIME_API_KEY` |
| Plugin | `livekit.plugins.rime` |

The Rime API key is stored only in the local `.env` file and is not committed to the repository.

## Preflight Verification

The project includes:

```text
scripts/rime_preflight.py