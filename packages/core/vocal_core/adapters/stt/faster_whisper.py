from typing import Optional, Union, BinaryIO, Any
from pathlib import Path
import tempfile

from faster_whisper import WhisperModel

from .base import (
    STTAdapter,
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionWord,
)


class FasterWhisperAdapter(STTAdapter):
    """faster-whisper implementation for Whisper models"""
    
    def __init__(self):
        self.model: Optional[WhisperModel] = None
        self.model_path: Optional[Path] = None
        self.device: str = "auto"
    
    async def load_model(
        self,
        model_path: Path,
        device: str = "auto",
        compute_type: str = "default",
        **kwargs
    ) -> None:
        """
        Load Whisper model using faster-whisper
        
        Args:
            model_path: Path to model files
            device: Device to use ('cpu', 'cuda', 'auto')
            compute_type: Compute type ('int8', 'int8_float16', 'float16', 'float32', 'default')
            **kwargs: Additional faster-whisper parameters
        """
        if self.model is not None:
            await self.unload_model()
        
        self.model_path = model_path
        self.device = device
        
        self.model = WhisperModel(
            str(model_path),
            device=device,
            compute_type=compute_type if compute_type != "default" else "auto",
            **kwargs
        )
    
    async def unload_model(self) -> None:
        """Unload model from memory"""
        if self.model is not None:
            del self.model
            self.model = None
            self.model_path = None
    
    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None
    
    def get_model_info(self) -> dict[str, Any]:
        """Get model information"""
        return {
            "model_path": str(self.model_path) if self.model_path else None,
            "device": self.device,
            "loaded": self.is_loaded(),
        }
    
    async def transcribe(
        self,
        audio: Union[str, Path, BinaryIO],
        language: Optional[str] = None,
        task: str = "transcribe",
        temperature: float = 0.0,
        word_timestamps: bool = False,
        **kwargs
    ) -> TranscriptionResult:
        """
        Transcribe audio using faster-whisper
        
        Args:
            audio: Audio file path or file-like object
            language: Language code or None for auto-detect
            task: 'transcribe' or 'translate'
            temperature: Sampling temperature
            word_timestamps: Enable word-level timestamps
            **kwargs: Additional faster-whisper parameters
            
        Returns:
            TranscriptionResult
        """
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load_model() first.")
        
        temp_file = None
        try:
            if isinstance(audio, (str, Path)):
                audio_path = str(audio)
            else:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".audio")
                temp_file.write(audio.read())
                temp_file.close()
                audio_path = temp_file.name
            
            segments, info = self.model.transcribe(
                audio_path,
                language=language,
                task=task,
                temperature=temperature,
                word_timestamps=word_timestamps,
                **kwargs
            )
            
            segments_list = []
            words_list = []
            full_text = []
            
            for idx, segment in enumerate(segments):
                full_text.append(segment.text)
                
                seg = TranscriptionSegment(
                    id=idx,
                    start=segment.start,
                    end=segment.end,
                    text=segment.text,
                    avg_logprob=segment.avg_logprob,
                    no_speech_prob=segment.no_speech_prob,
                )
                segments_list.append(seg)
                
                if word_timestamps and hasattr(segment, 'words'):
                    for word in segment.words:
                        words_list.append(TranscriptionWord(
                            word=word.word,
                            start=word.start,
                            end=word.end,
                            probability=word.probability if hasattr(word, 'probability') else None,
                        ))
            
            return TranscriptionResult(
                text=" ".join(full_text).strip(),
                language=info.language,
                duration=info.duration if hasattr(info, 'duration') else 0.0,
                segments=segments_list if segments_list else None,
                words=words_list if words_list else None,
            )
            
        finally:
            if temp_file and Path(temp_file.name).exists():
                Path(temp_file.name).unlink()
