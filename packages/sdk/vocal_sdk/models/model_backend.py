from enum import Enum


class ModelBackend(str, Enum):
    CTRANSLATE2 = "ctranslate2"
    CUSTOM = "custom"
    FASTER_WHISPER = "faster_whisper"
    KOKORO = "kokoro"
    NEMO = "nemo"
    ONNX = "onnx"
    TRANSFORMERS = "transformers"

    def __str__(self) -> str:
        return str(self.value)
