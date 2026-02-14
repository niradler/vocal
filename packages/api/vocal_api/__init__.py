from .config import settings
from .main import app

__version__ = settings.VERSION

__all__ = [
    "app",
    "settings",
]
