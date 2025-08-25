import redis.asyncio as redis
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

class RedisInitializer:
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self.host = os.getenv('REDIS_HOST', 'localhost')
        self.port = int(os.getenv('REDIS_PORT', 6379))
        self.password = os.getenv('REDIS_PASSWORD')
        self.db = int(os.getenv('REDIS_DB', 0))
    
    async def initialize(self):
        """Initialize Redis connection"""
        try:
            # Create Redis client
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                decode_responses=True,
                max_connections=20
            )
            
            # Test connection
            await self._test_connection()
            
            # Setup key prefixes and configurations
            await self._setup_configurations()
            
            logger.info("Redis initialized successfully")
            return self.client
            
        except Exception as e:
            logger.error(f"Error initializing Redis: {str(e)}")
            raise
    
    async def _test_connection(self):
        """Test Redis connection"""
        try:
            await self.client.ping()
            info = await self.client.info()
            logger.info(f"Redis connection successful. Version: {info['redis_version']}")
            
        except Exception as e:
            logger.error(f"Redis connection failed: {str(e)}")
            raise
    
    async def _setup_configurations(self):
        """Setup Redis configurations and default values"""
        try:
            # Set default configurations
            config_keys = {
                'chatbot:config:max_conversation_length': '50',
                'chatbot:config:default_model': 'llama2-7b',
                'chatbot:config:rate_limit_per_minute': '60',
                'chatbot:config:session_timeout': '3600'
            }
            
            for key, value in config_keys.items():
                # Only set if key doesn't exist
                exists = await self.client.exists(key)
                if not exists:
                    await self.client.set(key, value)
                    
            logger.info("Redis configurations setup completed")
            
        except Exception as e:
            logger.error(f"Error setting up Redis configurations: {str(e)}")
            raise
    
    async def close(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")