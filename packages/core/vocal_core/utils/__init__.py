"""Utility functions for vocal-core"""

from .device import (
    ComputeType,
    DeviceType,
    detect_device,
    get_device_info,
    get_optimal_compute_type,
    get_optimal_threads,
    optimize_inference_settings,
)

__all__ = [
    "ComputeType",
    "DeviceType",
    "detect_device",
    "get_optimal_compute_type",
    "get_optimal_threads",
    "get_device_info",
    "optimize_inference_settings",
]
