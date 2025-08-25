"""
Database Utilities - Các utility functions cho PostgreSQL operations
"""

import logging
from typing import Optional, List, Dict, Any
from initialize import get_postgres_pool

logger = logging.getLogger(__name__)

async def db_execute(query: str, params: tuple = None):
    """Thực thi query database"""
    try:
        pool = get_postgres_pool()
        conn = await pool.acquire()
        try:
            await conn.execute(query, *params if params else ())
        finally:
            await pool.release(conn)
    except Exception as e:
        logger.error(f"Database execute error: {str(e)}")
        raise

async def db_fetch_all(query: str, params: tuple = None) -> List[Dict[str, Any]]:
    """Lấy tất cả kết quả từ database"""
    try:
        pool = get_postgres_pool()
        conn = await pool.acquire()
        try:
            records = await conn.fetch(query, *params if params else ())
            return [dict(record) for record in records]
        finally:
            await pool.release(conn)
    except Exception as e:
        logger.error(f"Database fetch_all error: {str(e)}")
        raise

async def db_fetch_one(query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
    """Lấy một kết quả từ database"""
    try:
        pool = get_postgres_pool()
        conn = await pool.acquire()
        try:
            record = await conn.fetchrow(query, *params if params else ())
            return dict(record) if record else None
        finally:
            await pool.release(conn)
    except Exception as e:
        logger.error(f"Database fetch_one error: {str(e)}")
        raise

async def db_execute_many(query: str, params_list: List[tuple]):
    """Thực thi nhiều queries cùng lúc"""
    try:
        pool = get_postgres_pool()
        conn = await pool.acquire()
        try:
            await conn.executemany(query, params_list)
        finally:
            await pool.release(conn)
    except Exception as e:
        logger.error(f"Database execute_many error: {str(e)}")
        raise

async def db_transaction():
    """Tạo database transaction context"""
    pool = get_postgres_pool()
    conn = await pool.acquire()
    return conn, pool
