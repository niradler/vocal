from enum import Enum


class ModelBackend(str, Enum):
    CHATTERBOX = "chatterbox"
    CTRANSLATE2 = "ctranslate2"
    CUSTOM = "custom"
    DIA = "dia"
    FASTER_QWEN3_TTS = "faster_qwen3_tts"
    FASTER_WHISPER = "faster_whisper"
    FISH_SPEECH = "fish_speech"
    KOKORO = "kokoro"
    NEMO = "nemo"
    ONNX = "onnx"
    ORPHEUS = "orpheus"
    PIPER = "piper"
    TRANSFORMERS = "transformers"
    WHISPERX = "whisperx"
    XTTS = "xtts"

    def __str__(self) -> str:
        return str(self.value)
