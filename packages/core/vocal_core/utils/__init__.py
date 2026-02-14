"""Utility functions for vocal-core"""

from .device import (
    detect_device,
    get_device_info,
    get_optimal_compute_type,
    get_optimal_threads,
    optimize_inference_settings,
)

__all__ = [
    "detect_device",
    "get_optimal_compute_type",
    "get_optimal_threads",
    "get_device_info",
    "optimize_inference_settings",
]
