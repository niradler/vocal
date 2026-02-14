import logging
from typing import Optional
import platform

logger = logging.getLogger(__name__)


def detect_device() -> str:
    """
    Detect the best available device for model inference

    Priority:
    1. CUDA (NVIDIA GPU)
    2. CPU

    Returns:
        Device string: "cuda" or "cpu"
    """
    try:
        import torch

        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            device_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)

            logger.info(
                f"CUDA available: {device_count} GPU(s) detected - "
                f"{device_name} ({vram_gb:.1f}GB VRAM)"
            )
            return "cuda"
    except ImportError:
        logger.debug("PyTorch not installed, skipping CUDA detection")
    except Exception as e:
        logger.warning(f"Error detecting CUDA: {e}")

    logger.info("Using CPU for inference")
    return "cpu"


def get_optimal_compute_type(device: str, model_size: str = "base") -> str:
    """
    Get optimal compute type based on device and model size

    Args:
        device: Device string ("cuda" or "cpu")
        model_size: Model size hint ("tiny", "base", "small", "medium", "large")

    Returns:
        Compute type string for faster-whisper
    """
    if device == "cuda":
        try:
            import torch

            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)

            if vram_gb >= 8:
                return "float16"
            elif vram_gb >= 4:
                return "int8_float16"
            else:
                return "int8"
        except Exception:
            return "float16"

    return "int8"


def get_optimal_threads() -> int:
    """
    Get optimal number of threads for CPU inference

    Returns:
        Number of threads to use
    """
    import os

    cpu_count = os.cpu_count() or 4

    if cpu_count >= 8:
        return max(4, cpu_count // 2)

    return max(2, cpu_count - 1)


def get_device_info() -> dict:
    """
    Get comprehensive device information

    Returns:
        Dictionary with device details
    """
    info = {
        "platform": platform.system(),
        "processor": platform.processor(),
        "cpu_count": None,
        "cuda_available": False,
        "cuda_version": None,
        "gpu_count": 0,
        "gpu_devices": [],
    }

    import os

    info["cpu_count"] = os.cpu_count()

    try:
        import torch

        if torch.cuda.is_available():
            info["cuda_available"] = True
            info["cuda_version"] = torch.version.cuda
            info["gpu_count"] = torch.cuda.device_count()

            for i in range(info["gpu_count"]):
                props = torch.cuda.get_device_properties(i)
                info["gpu_devices"].append(
                    {
                        "index": i,
                        "name": props.name,
                        "vram_gb": props.total_memory / (1024**3),
                        "compute_capability": f"{props.major}.{props.minor}",
                    }
                )
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Error getting GPU info: {e}")

    return info


def optimize_inference_settings(
    device: Optional[str] = None,
    model_size: str = "base",
) -> dict:
    """
    Get optimized inference settings

    Args:
        device: Specific device or None for auto-detection
        model_size: Model size for optimization hints

    Returns:
        Dictionary with optimized settings
    """
    if device is None or device == "auto":
        device = detect_device()

    settings = {
        "device": device,
        "compute_type": get_optimal_compute_type(device, model_size),
    }

    if device == "cpu":
        settings["num_workers"] = get_optimal_threads()
        settings["cpu_threads"] = get_optimal_threads()
    else:
        settings["num_workers"] = 1

    logger.info(
        f"Optimized settings: device={settings['device']}, "
        f"compute_type={settings['compute_type']}"
    )

    return settings
