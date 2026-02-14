from abc import ABC, abstractmethod
from typing import Optional, Any, BinaryIO, Union
from pathlib import Path


class BaseAdapter(ABC):
    """Base interface for model adapters (STT, TTS, etc.)"""
    
    @abstractmethod
    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        """
        Load model from local path
        
        Args:
            model_path: Path to model files
            device: Device to load model on ('cpu', 'cuda', 'auto')
            **kwargs: Additional backend-specific parameters
        """
        pass
    
    @abstractmethod
    async def unload_model(self) -> None:
        """Unload model from memory"""
        pass
    
    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if model is currently loaded"""
        pass
    
    @abstractmethod
    def get_model_info(self) -> dict[str, Any]:
        """Get information about the loaded model"""
        pass
