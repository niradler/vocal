# Configuration

All settings come from `vocal_core/config.py` (`VocalSettings`) and can be overridden by:
1. Environment variables (same name, uppercase)
2. A `.env` file in the directory where you run Vocal

## LLM (for `vocal chat` / `/v1/realtime`)

```env
LLM_BASE_URL=http://localhost:11434/v1   # OpenAI-compatible endpoint (Ollama default)
LLM_MODEL=gemma3n:latest                 # Model to use
LLM_API_KEY=ollama                       # "ollama" = no auth; set sk-... for OpenAI
```

Point at OpenAI:
```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...
```

## STT Defaults

```env
STT_DEFAULT_MODEL=Systran/faster-whisper-tiny
STT_DEFAULT_LANGUAGE=                    # empty = auto-detect language
STT_SAMPLE_RATE=16000                    # internal processing sample rate (Hz)
```

## TTS Defaults

```env
TTS_DEFAULT_MODEL=pyttsx3
TTS_DEFAULT_VOICE=                       # empty = model default
TTS_DEFAULT_CLONE_MODEL=Qwen/Qwen3-TTS-12Hz-0.6B-Base
```

## VAD (Voice Activity Detection)

Applies to `vocal live`, `vocal chat`, `/v1/audio/stream` and `/v1/realtime`.
Turn detection is millisecond-based, so it behaves the same regardless of the
client's chunk size. The backend is Silero VAD (ONNX Runtime when available,
PyTorch otherwise) with an RMS fallback.

```env
VAD_SPEECH_THRESHOLD=0.5         # Silero speech probability to open a turn
VAD_ONSET_MS=180                 # Confirmed speech before speech_started fires
VAD_PREROLL_MS=300               # Audio kept before onset (no clipped phonemes)
VAD_SILENCE_MS=600               # Dictation: silence before committing a turn
VAD_COMMIT_GRACE_MS=0            # Dictation: extra wait before committing
REALTIME_AGENT_SILENCE_MS=700    # Voice agent: silence before committing a turn
REALTIME_AGENT_COMMIT_GRACE_MS=400  # Extra wait: a ~1 s pause stays in the same turn
REALTIME_MAX_UTTERANCE_S=30      # Hard cap on one utterance
VAD_SILENCE_DURATION_S=0.8       # /v1/audio/stream default silence before flush
VAD_THRESHOLD=400.0              # RMS energy threshold for the fallback adapter
```

The two endpointing profiles exist because the jobs differ:

- **Dictation** wants the transcript as soon as you stop; a long pause usually
  means "new sentence", so 600 ms is enough.
- **A voice agent** must not split one sentence into two LLM turns. Natural
  pauses inside a sentence reach ~1 s, so the agent profile waits 700 ms, then
  gives speech another 400 ms to resume before committing.

**Tuning tips:**
- The agent cuts you off mid-sentence → raise `REALTIME_AGENT_COMMIT_GRACE_MS`
- Replies feel sluggish after you stop → lower `REALTIME_AGENT_SILENCE_MS`
- Background noise opens turns → raise `VAD_SPEECH_THRESHOLD`
- First words are clipped → raise `VAD_PREROLL_MS`
- Echo from speakers activates the mic → raise `PLAYBACK_COOLDOWN`

## Audio / CLI

```env
AUDIO_FRAME_SIZE=1600            # Mic capture frame size (samples)
AUDIO_CHANNELS=1                 # Mono (1) or stereo (2)
PLAYBACK_COOLDOWN=0.5            # Seconds mic stays muted after TTS playback
REALTIME_DEFAULT_INPUT_RATE=24000  # Sample rate expected from Realtime API clients
```

## Voice Chat System Prompt

```env
CHAT_SYSTEM_PROMPT=You are a helpful voice assistant. Keep answers short and conversational, 1 sentence max, no symbols or punctuation.
```

## Logging

```env
LOG_LEVEL=INFO       # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT=%(asctime)s %(name)-30s %(levelname)-8s %(message)s
```

## Example `.env` File

```env
# .env — place in your working directory
STT_DEFAULT_MODEL=Systran/faster-whisper-tiny
TTS_DEFAULT_MODEL=pyttsx3
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=gemma3n:latest
LLM_API_KEY=ollama
LOG_LEVEL=INFO
VAD_THRESHOLD=500.0
```

## Model Storage Location

Models are cached at `~/.cache/vocal/models/` by default. This is not currently configurable via env var — see the [model storage note](models.md#model-storage) in the models guide for cross-platform symlink instructions.
