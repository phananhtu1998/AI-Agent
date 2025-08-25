import asyncpg
import logging
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class PostgresInitializer:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        
    async def initialize(self) -> asyncpg.Pool:
        try:
            self.pool = await asyncpg.create_pool(
                user='admin',
                password='123',
                database='chatbot',
                host='localhost',
                port=5432,
                min_size=10,  # Tăng min_size để có sẵn connections
                max_size=50,  # Tăng max_size cho high load
                command_timeout=30,  # Timeout cho commands
                statement_cache_size=100,  # Cache prepared statements
                max_cached_statement_lifetime=300,  # Lifetime của cached statements
                max_queries=50000,  # Reset connection sau số queries này
                max_inactive_connection_lifetime=300.0,  # Close inactive connections
                setup=self._setup_connection  # Custom setup cho mỗi connection
            )
            return self.pool
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL connection pool: {str(e)}")
            raise
    async def _setup_connection(self, conn):
        # Tối ưu connection settings
        await conn.execute('''
            SET SESSION synchronous_commit = OFF;
            SET SESSION work_mem = '64MB';
            SET SESSION maintenance_work_mem = '256MB';
            SET SESSION effective_cache_size = '4GB';
        ''')
    async def close(self):
        """Close PostgreSQL connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL connection pool closed")

# Global pool instance
_pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    """Get or create database connection pool"""
    global _pool
    if _pool is None:
        initializer = PostgresInitializer()
        _pool = await initializer.initialize()
    return _pool

@asynccontextmanager
async def get_db_cursor():
    """Get a database cursor"""
    pool = await get_pool()
    conn = await pool.acquire()
    try:
        yield conn
    finally:
        await pool.release(conn)

async def execute_query(query: str, params: tuple = None):
    """Execute a query without returning results"""
    pool = await get_pool()
    conn = await pool.acquire()
    try:
        await conn.execute(query, *params if params else ())
    finally:
        await pool.release(conn)

async def fetch_all(query: str, params: tuple = None) -> List[Dict[str, Any]]:
    """Execute a query and return all results"""
    pool = await get_pool()
    conn = await pool.acquire()
    try:
        records = await conn.fetch(query, *params if params else ())
        return [dict(record) for record in records]
    finally:
        await pool.release(conn)

async def fetch_one(query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
    """Execute a query and return one result"""
    pool = await get_pool()
    conn = await pool.acquire()
    try:
        record = await conn.fetchrow(query, *params if params else ())
        return dict(record) if record else None
    finally:
        await pool.release(conn)
