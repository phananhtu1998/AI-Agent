"""
Redis Utilities - Các utility functions cho Redis operations
"""

import logging
from typing import Optional
# from initialize import get_redis_client

logger = logging.getLogger(__name__)

async def redis_set(key: str, value: str, expire: int = None):
    """Set giá trị Redis"""
    logger.warning("Redis functions temporarily disabled - install redis first")
    return None

async def redis_get(key: str) -> Optional[str]:
    """Lấy giá trị từ Redis"""
    logger.warning("Redis functions temporarily disabled - install redis first")
    return None

async def redis_delete(key: str):
    """Xóa key trong Redis"""
    logger.warning("Redis functions temporarily disabled - install redis first")
    return None

async def redis_exists(key: str) -> bool:
    """Kiểm tra key có tồn tại trong Redis không"""
    logger.warning("Redis functions temporarily disabled - install redis first")
    return False

async def redis_set_json(key: str, value: dict, expire: int = None):
    """Set JSON value vào Redis"""
    logger.warning("Redis functions temporarily disabled - install redis first")
    return None

async def redis_get_json(key: str) -> Optional[dict]:
    """Lấy JSON value từ Redis"""
    logger.warning("Redis functions temporarily disabled - install redis first")
    return None

async def redis_expire(key: str, seconds: int):
    """Set thời gian hết hạn cho key"""
    logger.warning("Redis functions temporarily disabled - install redis first")
    return None

async def redis_ttl(key: str) -> int:
    """Lấy thời gian còn lại của key (TTL)"""
    logger.warning("Redis functions temporarily disabled - install redis first")
    return -1
