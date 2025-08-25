"""
Utils Package - Các utility functions chung
"""

# Database utilities
from .database_utils import (
    db_execute,
    db_fetch_all,
    db_fetch_one,
    db_execute_many,
    db_transaction
)

# Redis utilities
from .redis_utils import (
    redis_set,
    redis_get,
    redis_delete,
    redis_exists,
    redis_set_json,
    redis_get_json,
    redis_expire,
    redis_ttl
)

__all__ = [
    # Database
    'db_execute',
    'db_fetch_all', 
    'db_fetch_one',
    'db_execute_many',
    'db_transaction',
    
    # Redis
    'redis_set',
    'redis_get',
    'redis_delete',
    'redis_exists',
    'redis_set_json',
    'redis_get_json',
    'redis_expire',
    'redis_ttl'
]
