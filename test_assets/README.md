# Test Assets

Audio files and expected transcriptions for E2E testing.

## Current Assets

### `Recording.m4a`
- **Format**: M4A (AAC audio)
- **Expected**: "Hello, what is your name and what can you do?"
- **Purpose**: Test short voice input

### `en-AU-WilliamNeural.mp3`
- **Format**: MP3
- **Expected**: "The sun was setting slowly, casting long shadows across the empty field."
- **Purpose**: Test TTS-generated audio

## Adding Your Own

Place audio files in `audio/` and create matching expected text:

```bash
# Add your audio
cp recording.m4a test_assets/audio/

# Add expected transcription
echo "Your expected text" > test_assets/expected/recording.m4a.txt
```

**Supported formats**: wav, mp3, m4a, flac, ogg, webm

## Testing

```bash
# Test single file
uv run vocal run test_assets/audio/Recording.m4a

# Run full test suite
uv run python scripts/run_tests.py
```
