import logging
from colorama import Fore, Style, init
import platform
import sys
from contextlib import asynccontextmanager
from typing import Optional

# Import các module khởi tạo
from .postgres import PostgresInitializer, get_pool
from .redis import RedisInitializer

init(autoreset=True)

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors"""
    
    def format(self, record):
        if record.levelno == logging.INFO:
            record.msg = f"{Fore.GREEN}{record.msg}{Style.RESET_ALL}"
        elif record.levelno == logging.WARNING:
            record.msg = f"{Fore.YELLOW}{record.msg}{Style.RESET_ALL}"
        elif record.levelno == logging.ERROR:
            record.msg = f"{Fore.RED}{record.msg}{Style.RESET_ALL}"
        return super().format(record)

# Configure logging
handlers = []

# Configure file handler with UTF-8 encoding to be safe
file_handler = logging.FileHandler('app.log', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
handlers.append(file_handler)

# Use a simpler console formatter on Windows to avoid UnicodeEncodeError
console_handler = logging.StreamHandler()
if platform.system() != "Windows":
    console_handler.setFormatter(ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
else:
    # On Windows, use a simple formatter and force UTF-8 encoding
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
handlers.append(console_handler)

logging.basicConfig(
    level=logging.INFO,
    handlers=handlers
)
logger = logging.getLogger(__name__)

class ApplicationRunner:
    def __init__(self):
        self.postgres_initializer: Optional[PostgresInitializer] = None
        self.redis_initializer: Optional[RedisInitializer] = None
        self.is_initialized = False
    
    async def initialize_services(self):
        """Khởi tạo tất cả các services"""
        if self.is_initialized:
            logger.info("Services already initialized")
            return
            
        logger.info("Initializing core services...")
        
        try:
            # Khởi tạo PostgreSQL
            logger.info("Initializing PostgreSQL...")
            self.postgres_initializer = PostgresInitializer()
            await self.postgres_initializer.initialize()
            logger.info("PostgreSQL initialized successfully")
            
            # Khởi tạo Redis
            logger.info("Initializing Redis...")
            self.redis_initializer = RedisInitializer()
            await self.redis_initializer.initialize()
            logger.info("Redis initialized successfully")
            
            self.is_initialized = True
            logger.info("All services initialized successfully")
            
        except Exception as e:
            logger.error(f"Error during service initialization: {str(e)}")
            await self.cleanup_services()
            raise
    
    async def cleanup_services(self):
        """Dọn dẹp các services"""
        logger.info("Cleaning up services...")
        
        try:
            if self.redis_initializer:
                await self.redis_initializer.close()
                logger.info("Redis connection closed")
                
            if self.postgres_initializer:
                await self.postgres_initializer.close()
                logger.info("PostgreSQL connection closed")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
        finally:
            self.is_initialized = False
    
    def get_postgres_pool(self):
        """Lấy PostgreSQL connection pool"""
        if not self.is_initialized:
            raise RuntimeError("Services not initialized. Call initialize_services() first.")
        return get_pool()
    
    def get_redis_client(self):
        """Lấy Redis client"""
        if not self.is_initialized or not self.redis_initializer:
            raise RuntimeError("Services not initialized. Call initialize_services() first.")
        return self.redis_initializer.client

# Global instance
_app_runner: Optional[ApplicationRunner] = None

def get_app_runner() -> ApplicationRunner:
    """Lấy global application runner instance"""
    global _app_runner
    if _app_runner is None:
        _app_runner = ApplicationRunner()
    return _app_runner

async def initialize_all_services():
    """Khởi tạo tất cả services"""
    runner = get_app_runner()
    await runner.initialize_services()

async def cleanup_all_services():
    """Dọn dẹp tất cả services"""
    global _app_runner
    if _app_runner:
        await _app_runner.cleanup_services()
        _app_runner = None

def get_postgres_pool():
    """Lấy PostgreSQL connection pool"""
    runner = get_app_runner()
    return runner.get_postgres_pool()

def get_redis_client():
    """Lấy Redis client"""
    runner = get_app_runner()
    return runner.get_redis_client()
