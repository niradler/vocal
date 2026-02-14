# Quick Start Guide

## Installation

### Option 1: uvx (Fastest - No Install!)

```bash
uvx vocal serve
```

### Option 2: PyPI

```bash
pip install vocal-ai
vocal serve
```

### Option 3: Docker

```bash
docker compose up
```

### Option 4: From Source

```bash
git clone https://github.com/niradler/vocal
cd vocal
make install
make serve
```

## First Steps

1. **Start the API**:

   ```bash
   vocal serve
   ```

2. **Open API Docs**: http://localhost:8000/docs

3. **List Models**:

   ```bash
   uvx vocal models list
   # or if installed: vocal models list
   ```

4. **Pull a Model**:

   ```bash
   uvx vocal models pull Systran/faster-whisper-tiny
   # or if installed: vocal models pull Systran/faster-whisper-tiny
   ```

5. **Transcribe Audio**:
   ```bash
   uvx vocal run audio.mp3
   # or if installed: vocal run audio.mp3
   ```

## Using the SDK

```python
from vocal import VocalSDK

client = VocalSDK()

# Transcribe
result = client.audio.transcribe(
    file="audio.mp3",
    model="Systran/faster-whisper-tiny"
)
print(result['text'])

# Text-to-Speech
audio = client.audio.text_to_speech(
    text="Hello!",
    model="pyttsx3"
)
```

## API Examples

### Transcribe Audio

```bash
curl -X POST "http://localhost:8000/v1/audio/transcriptions" \
  -F "file=@audio.mp3" \
  -F "model=Systran/faster-whisper-tiny"
```

### Text-to-Speech

```bash
curl -X POST "http://localhost:8000/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{"model":"pyttsx3","input":"Hello world"}' \
  --output speech.wav
```

## Docker Usage

### Basic

```bash
docker compose up
```

### With GPU

```bash
docker compose --profile gpu up
```

### Custom Port

```bash
docker run -p 9000:8000 niradler/vocal-api
```

## Troubleshooting

### Port Already in Use

```bash
# Windows
netstat -ano | findstr :8000
taskkill /F /PID <PID>

# Linux/Mac
lsof -ti:8000 | xargs kill
```

### GPU Not Detected

```bash
# Check CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Check device info
curl http://localhost:8000/v1/system/device
```

## Next Steps

- Read the [full README](README.md)
- Check [API documentation](http://localhost:8000/docs)
- Join our [Discord community](#)
- Report issues on [GitHub](#)
