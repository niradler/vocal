from fastapi import APIRouter

from vocal_core.utils import get_device_info

router = APIRouter(prefix="/v1/system", tags=["system"])


@router.get("/device")
async def get_device():
    """
    Get device and hardware information

    Returns information about available compute devices (CPU, GPU)
    and optimization settings being used.
    """
    return get_device_info()
