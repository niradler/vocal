from typing import Optional, AsyncIterator
from pathlib import Path
from .model_info import ModelInfo, ModelStatus, ModelProvider as ModelProviderEnum
from .providers.base import ModelProvider
from .providers.huggingface import HuggingFaceProvider


class ModelRegistry:
    """
    Central registry for managing models across different providers
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize model registry
        
        Args:
            storage_path: Base path for storing downloaded models
        """
        self.storage_path = storage_path or Path.home() / ".cache" / "vocal" / "models"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.providers: dict[str, ModelProvider] = {
            "huggingface": HuggingFaceProvider(cache_dir=self.storage_path / "hf"),
        }
        
        self._local_models: dict[str, ModelInfo] = {}
    
    def add_provider(self, name: str, provider: ModelProvider) -> None:
        """Add a custom model provider"""
        self.providers[name] = provider
    
    async def list_models(
        self,
        provider: Optional[str] = None,
        task: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> list[ModelInfo]:
        """
        List all available models
        
        Args:
            provider: Filter by provider name
            task: Filter by task type ('stt', 'tts')
            status_filter: Filter by status ('available', 'downloading', 'not_downloaded')
            
        Returns:
            List of ModelInfo objects
        """
        all_models = []
        
        providers_to_query = (
            [self.providers[provider]] if provider and provider in self.providers
            else self.providers.values()
        )
        
        for prov in providers_to_query:
            try:
                models = await prov.list_models(task=task)
                
                for model in models:
                    model_path = self._get_model_path(model.id)
                    if model_path.exists():
                        model.status = ModelStatus.AVAILABLE
                        model.local_path = str(model_path)
                
                all_models.extend(models)
            except Exception as e:
                print(f"Error listing models from provider {prov.get_provider_name()}: {e}")
        
        if status_filter:
            all_models = [m for m in all_models if m.status == status_filter]
        
        return all_models
    
    async def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """
        Get detailed information about a specific model
        
        Args:
            model_id: Model identifier
            
        Returns:
            ModelInfo object or None
        """
        for provider in self.providers.values():
            try:
                model = await provider.get_model_info(model_id)
                if model:
                    model_path = self._get_model_path(model_id)
                    if model_path.exists():
                        model.status = ModelStatus.AVAILABLE
                        model.local_path = str(model_path)
                    return model
            except Exception as e:
                print(f"Error getting model {model_id} from {provider.get_provider_name()}: {e}")
        
        return None
    
    async def download_model(
        self,
        model_id: str,
        provider_name: str = "huggingface",
        quantization: Optional[str] = None
    ) -> AsyncIterator[tuple[int, int, ModelStatus]]:
        """
        Download a model from specified provider
        
        Args:
            model_id: Model identifier
            provider_name: Provider to download from
            quantization: Optional quantization format
            
        Yields:
            Tuples of (downloaded_bytes, total_bytes, status)
        """
        if provider_name not in self.providers:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        provider = self.providers[provider_name]
        destination = self._get_model_path(model_id)
        
        try:
            yield (0, 0, ModelStatus.DOWNLOADING)
            
            async for downloaded, total in provider.download_model(
                model_id,
                destination,
                quantization
            ):
                yield (downloaded, total, ModelStatus.DOWNLOADING)
            
            is_valid = await provider.verify_model(model_id, destination)
            
            if is_valid:
                yield (total, total, ModelStatus.AVAILABLE)
            else:
                yield (0, 0, ModelStatus.ERROR)
                
        except Exception as e:
            print(f"Download error: {e}")
            yield (0, 0, ModelStatus.ERROR)
    
    async def delete_model(self, model_id: str) -> bool:
        """
        Delete a downloaded model
        
        Args:
            model_id: Model identifier
            
        Returns:
            True if deleted successfully
        """
        model_path = self._get_model_path(model_id)
        
        if not model_path.exists():
            return False
        
        try:
            import shutil
            shutil.rmtree(model_path)
            return True
        except Exception as e:
            print(f"Error deleting model {model_id}: {e}")
            return False
    
    def _get_model_path(self, model_id: str) -> Path:
        """Get local storage path for a model"""
        safe_id = model_id.replace("/", "--")
        return self.storage_path / safe_id
    
    def get_model_path(self, model_id: str) -> Optional[Path]:
        """Get path to downloaded model, or None if not downloaded"""
        path = self._get_model_path(model_id)
        return path if path.exists() else None
