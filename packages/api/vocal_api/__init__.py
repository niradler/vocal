from .main import app
from .config import settings

__version__ = settings.VERSION

__all__ = [
    "app",
    "settings",
]
