from enum import StrEnum


class ModelBackend(StrEnum):
    CHATTERBOX = "chatterbox"
    CTRANSLATE2 = "ctranslate2"
    CUSTOM = "custom"
    FASTER_QWEN3_TTS = "faster_qwen3_tts"
    FASTER_WHISPER = "faster_whisper"
    KOKORO = "kokoro"
    NEMO = "nemo"
    OMNIVOICE = "omnivoice"
    ONNX = "onnx"
    PHONON = "phonon"
    PIPER = "piper"
    QWEN3_OMNI_STT = "qwen3_omni_stt"
    QWEN3_OMNI_TTS = "qwen3_omni_tts"
    SUPERTONIC = "supertonic"
    TRANSFORMERS = "transformers"
    VOXCPM = "voxcpm"
    VOXTRAL_STT = "voxtral_stt"
    VOXTRAL_TTS = "voxtral_tts"
    WHISPERX = "whisperx"

    def __str__(self) -> str:
        return str(self.value)
