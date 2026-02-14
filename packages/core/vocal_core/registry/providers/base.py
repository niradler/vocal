from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator
from pathlib import Path
from ..model_info import ModelInfo


class ModelProvider(ABC):
    """Base interface for model providers"""
    
    @abstractmethod
    async def list_models(self, task: Optional[str] = None) -> list[ModelInfo]:
        """
        List available models from this provider
        
        Args:
            task: Optional filter by task type ('stt', 'tts')
            
        Returns:
            List of ModelInfo objects
        """
        pass
    
    @abstractmethod
    async def get_model_info(self, model_id: str) -> Optional[ModelInfo]:
        """
        Get detailed information about a specific model
        
        Args:
            model_id: Model identifier
            
        Returns:
            ModelInfo object or None if not found
        """
        pass
    
    @abstractmethod
    async def download_model(
        self,
        model_id: str,
        destination: Path,
        quantization: Optional[str] = None
    ) -> AsyncIterator[tuple[int, int]]:
        """
        Download a model to local storage
        
        Args:
            model_id: Model identifier
            destination: Local path to save model
            quantization: Optional quantization format
            
        Yields:
            Tuples of (downloaded_bytes, total_bytes) for progress tracking
        """
        pass
    
    @abstractmethod
    async def verify_model(self, model_id: str, local_path: Path) -> bool:
        """
        Verify model integrity after download
        
        Args:
            model_id: Model identifier
            local_path: Path to downloaded model
            
        Returns:
            True if model is valid, False otherwise
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name"""
        pass
