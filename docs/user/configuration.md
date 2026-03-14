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

Applies to `vocal live`, `vocal chat`, and `/v1/audio/stream`.

```env
VAD_THRESHOLD=400.0              # RMS energy threshold (0–32768 scale)
VAD_SILENCE_FRAMES=15            # Silence frames before end-of-speech
VAD_MAX_BUFFER_FRAMES=150        # Max buffer before forced commit
VAD_SPEECH_ONSET_FRAMES=3        # Consecutive loud frames to trigger speech_started
VAD_MIN_SPEECH_FRAMES=4          # Min speech frames before sending to STT
VAD_SILENCE_DURATION_S=1.5       # vocal live: silence length before flushing chunk
```

**Tuning tips:**
- Background noise triggers too often → raise `VAD_THRESHOLD` or `VAD_SPEECH_ONSET_FRAMES`
- Short words are missed → lower `VAD_MIN_SPEECH_FRAMES`
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
