import json
from datetime import datetime
from pathlib import Path


class ModelMetadataCache:
    def __init__(self, cache_dir: Path | None = None):
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "vocal" / "metadata"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, model_id: str) -> Path:
        safe_name = model_id.replace("/", "--")
        return self.cache_dir / f"{safe_name}.json"

    def get(self, model_id: str) -> dict | None:
        cache_path = self._get_cache_path(model_id)
        if not cache_path.exists():
            return None

        try:
            with open(cache_path) as f:
                data = json.load(f)
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, model_id: str, metadata: dict) -> None:
        cache_path = self._get_cache_path(model_id)

        metadata_copy = metadata.copy()
        metadata_copy["model_id"] = model_id
        metadata_copy["cached_at"] = datetime.now().isoformat()

        try:
            with open(cache_path, "w") as f:
                json.dump(metadata_copy, f, indent=2, default=str)
        except OSError as e:
            raise RuntimeError(f"Failed to write metadata cache: {e}") from e

    def delete(self, model_id: str) -> bool:
        cache_path = self._get_cache_path(model_id)
        if cache_path.exists():
            try:
                cache_path.unlink()
                return True
            except OSError:
                return False
        return False

    def exists(self, model_id: str) -> bool:
        return self._get_cache_path(model_id).exists()

    def list_cached(self) -> list[str]:
        cached_models = []
        for cache_file in self.cache_dir.glob("*.json"):
            model_id = cache_file.stem.replace("--", "/")
            cached_models.append(model_id)
        return cached_models

    def clear(self) -> int:
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                count += 1
            except OSError:
                pass
        return count
