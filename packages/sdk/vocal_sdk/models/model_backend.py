from enum import Enum


class ModelBackend(str, Enum):
    CTRANSLATE2 = "ctranslate2"
    CUSTOM = "custom"
    FASTER_QWEN3_TTS = "faster_qwen3_tts"
    FASTER_WHISPER = "faster_whisper"
    KOKORO = "kokoro"
    NEMO = "nemo"
    ONNX = "onnx"
    PIPER = "piper"
    TRANSFORMERS = "transformers"

    def __str__(self) -> str:
        return str(self.value)
