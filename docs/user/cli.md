# CLI Reference

All CLI commands are available via `vocal <command>`. Run `vocal --help` or `vocal <command> --help` for full options.

## Server

```bash
vocal serve                          # Start API on http://0.0.0.0:8000
vocal serve --host localhost         # Bind to localhost only
vocal serve --port 9000              # Custom port
vocal serve --reload                 # Auto-reload on code changes (dev)
```

## Transcription

```bash
vocal transcribe audio.mp3                           # Transcribe a file
vocal transcribe audio.wav --model Systran/faster-whisper-tiny
vocal transcribe audio.mp3 --language en             # Force language (skips detection)
vocal transcribe audio.mp3 --task translate          # Translate to English
vocal transcribe audio.mp3 --format text             # Output as plain text
vocal transcribe audio.mp3 --format srt              # Output as SRT subtitles
vocal transcribe audio.mp3 --format vtt              # Output as WebVTT
```

## Text-to-Speech

```bash
vocal speak "Hello, world!"                         # Synthesize to default output
vocal speak "Hello" --model pyttsx3
vocal speak "Hello" --voice af_heart                # Use specific voice
vocal speak "Hello" --format mp3 --output out.mp3   # Save to file
vocal speak "Hello" --speed 1.5                     # 1.5× speed
```

## Voice Listing

```bash
vocal voices                           # List voices for default TTS model
vocal voices --model pyttsx3
vocal voices --model hexgrad/Kokoro-82M
```

## Voice Cloning

```bash
vocal clone "Text to synthesize in your voice." \
  --reference speaker.wav \
  --output clone_out.wav

vocal clone "Hello" \
  --reference speaker.wav \
  --model Qwen/Qwen3-TTS-12Hz-0.6B-Base \
  --output clone_out.wav \
  --format wav
```

`--reference` must be a 3–30 second clean speech recording (wav, mp3, m4a).
Requires a voice-cloning-capable model (see [Models](models.md)).

## Real-time Transcription

Three modes with different latency trade-offs:

| Command | Transport | Latency | Best for |
|---------|-----------|---------|----------|
| `vocal listen` | REST (chunk-based) | 1–2 s | Simple, reliable |
| `vocal live` | WebSocket streaming | ~200 ms | Low-latency transcription |
| `vocal chat` | WebSocket (Realtime) | 1–2 s | Full voice agent |

### `vocal listen` — Chunk-based

```bash
vocal listen                              # Default microphone
vocal listen --device "Razer"            # Select mic by name substring
vocal listen --device 3                  # Select mic by index
vocal listen --task translate            # Translate to English
vocal listen --language en               # Force language
vocal listen --silence-duration 2.0      # Seconds of silence before flush
vocal listen --max-chunk-duration 15.0   # Max chunk length
vocal listen --silence-threshold 300     # Manual RMS threshold (skip calibration)
vocal listen --verbose                   # Show API latency per chunk
```

Calibrates noise floor for ~1.5 s on startup (stay quiet). Shows a live energy bar.

### `vocal live` — WebSocket streaming

```bash
vocal live                               # Stream mic via WebSocket
vocal live --device "Razer" --model Systran/faster-whisper-tiny
vocal live --task translate
vocal live --verbose                     # Show event trace
```

Raw PCM16 frames stream to `/v1/audio/stream`. Server-side VAD + faster-whisper returns partial tokens at ~200 ms.

### `vocal chat` — Voice agent

```bash
vocal chat                               # Full STT → LLM → TTS loop
vocal chat --device "Razer"             # Select mic
vocal chat --output-device 1            # Select speaker (see vocal output-devices)
vocal chat --language en                # Force STT language
vocal chat --system-prompt "You are a pirate."
vocal chat --verbose                    # Show WebSocket event trace
```

Requires an OpenAI-compatible LLM running locally (Ollama default) or configured via env vars. See [Configuration](configuration.md).

## Audio Devices

```bash
vocal devices          # List microphone/input devices
vocal output-devices   # List speaker/output devices
```

## Model Management

```bash
vocal models list                               # List all models
vocal models list --task stt                    # Filter by task
vocal models list --task tts
vocal models show Systran/faster-whisper-tiny   # Detailed model info
vocal models pull Systran/faster-whisper-tiny   # Download a model
vocal models delete Systran/faster-whisper-tiny # Delete downloaded model
vocal models delete ... --force                 # Skip confirmation
```

## Global Options

```bash
vocal --version   # Print version
vocal --help      # List all commands
```
