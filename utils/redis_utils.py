"""
Redis Utilities - Các utility functions cho Redis operations
"""

import logging
from typing import Optional
from initialize import get_redis_client

logger = logging.getLogger(__name__)

async def redis_set(key: str, value: str, expire: int = None):
    """Set giá trị Redis"""
    try:
        client = get_redis_client()
        await client.set(key, value, ex=expire)
    except Exception as e:
        logger.error(f"Redis set error: {str(e)}")
        raise

async def redis_get(key: str) -> Optional[str]:
    """Lấy giá trị từ Redis"""
    try:
        client = get_redis_client()
        return await client.get(key)
    except Exception as e:
        logger.error(f"Redis get error: {str(e)}")
        raise

async def redis_delete(key: str):
    """Xóa key trong Redis"""
    try:
        client = get_redis_client()
        await client.delete(key)
    except Exception as e:
        logger.error(f"Redis delete error: {str(e)}")
        raise

async def redis_exists(key: str) -> bool:
    """Kiểm tra key có tồn tại trong Redis không"""
    try:
        client = get_redis_client()
        return bool(await client.exists(key))
    except Exception as e:
        logger.error(f"Redis exists error: {str(e)}")
        raise

async def redis_set_json(key: str, value: dict, expire: int = None):
    """Set JSON value vào Redis"""
    try:
        import json
        client = get_redis_client()
        json_value = json.dumps(value, ensure_ascii=False)
        await client.set(key, json_value, ex=expire)
    except Exception as e:
        logger.error(f"Redis set_json error: {str(e)}")
        raise

async def redis_get_json(key: str) -> Optional[dict]:
    """Lấy JSON value từ Redis"""
    try:
        import json
        client = get_redis_client()
        value = await client.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        logger.error(f"Redis get_json error: {str(e)}")
        raise

async def redis_expire(key: str, seconds: int):
    """Set thời gian hết hạn cho key"""
    try:
        client = get_redis_client()
        await client.expire(key, seconds)
    except Exception as e:
        logger.error(f"Redis expire error: {str(e)}")
        raise

async def redis_ttl(key: str) -> int:
    """Lấy thời gian còn lại của key (TTL)"""
    try:
        client = get_redis_client()
        return await client.ttl(key)
    except Exception as e:
        logger.error(f"Redis ttl error: {str(e)}")
        raise
