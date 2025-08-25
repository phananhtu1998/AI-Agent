import os
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import importlib.util
import asyncio

# Import postgres connection
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from initialize.postgres import get_db_cursor, execute_query, fetch_all, fetch_one

logger = logging.getLogger(__name__)

class MigrationManager:
    """
    Quản lý database migrations
    """
    
    def __init__(self, migrations_dir: str = None):
        if migrations_dir is None:
            self.migrations_dir = Path(__file__).parent / "files"
        else:
            self.migrations_dir = Path(migrations_dir)
        
        self.migrations_dir.mkdir(exist_ok=True)
    
    async def initialize(self):
        """Initialize migration manager"""
        await self.ensure_migration_table()
    
    async def ensure_migration_table(self):
        """
        Tạo bảng để tracking migrations
        """
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS migration_history (
            id SERIAL PRIMARY KEY,
            migration_name VARCHAR(255) NOT NULL UNIQUE,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            checksum VARCHAR(64)
        );
        """
        try:
            await execute_query(create_table_sql)
            logger.info("Migration table đã được tạo/kiểm tra")
        except Exception as e:
            logger.error(f"Lỗi tạo migration table: {e}")
            raise
    
    def get_migration_files(self) -> List[str]:
        """
        Lấy danh sách file migration theo thứ tự
        """
        migration_files = []
        pattern = re.compile(r'^\d{14}_.*\.py$')
        
        for file in self.migrations_dir.glob("*.py"):
            if pattern.match(file.name) and not file.name.startswith('__'):
                migration_files.append(file.name)
        
        return sorted(migration_files)
    
    async def get_applied_migrations(self) -> List[str]:
        """
        Lấy danh sách migrations đã apply
        """
        try:
            async with get_db_cursor() as conn:
                records = await conn.fetch("SELECT migration_name FROM migration_history ORDER BY migration_name")
                return [record['migration_name'] for record in records]
        except Exception as e:
            logger.error(f"Lỗi lấy applied migrations: {e}")
            return []
    
    async def get_pending_migrations(self) -> List[str]:
        """
        Lấy danh sách migrations chưa apply
        """
        all_migrations = self.get_migration_files()
        applied_migrations = await self.get_applied_migrations()
        
        return [m for m in all_migrations if m not in applied_migrations]
    
    def load_migration_module(self, migration_file: str):
        """
        Load migration module từ file
        """
        file_path = self.migrations_dir / migration_file
        
        spec = importlib.util.spec_from_file_location(
            migration_file[:-3], file_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        return module
    
    async def apply_migration(self, migration_file: str) -> bool:
        """
        Apply một migration
        """
        try:
            logger.info(f"Applying migration: {migration_file}")
            
            # Load migration module
            module = self.load_migration_module(migration_file)
            
            # Kiểm tra có hàm upgrade không
            if not hasattr(module, 'upgrade'):
                logger.error(f"Migration {migration_file} không có hàm upgrade()")
                return False
            
            # Apply migration
            async with get_db_cursor() as conn:
                async with conn.transaction():
                    await module.upgrade(conn)
                    
                    # Ghi vào migration history
                    insert_sql = """
                    INSERT INTO migration_history (migration_name) 
                    VALUES ($1)
                    """
                    await conn.execute(insert_sql, migration_file)
            
            logger.info(f"Migration {migration_file} applied successfully")
            return True
            
        except Exception as e:
            logger.error(f"Lỗi apply migration {migration_file}: {e}")
            return False
    
    async def rollback_migration(self, migration_file: str) -> bool:
        """
        Rollback một migration
        """
        try:
            logger.info(f"Rolling back migration: {migration_file}")
            
            # Load migration module
            module = self.load_migration_module(migration_file)
            
            # Kiểm tra có hàm downgrade không
            if not hasattr(module, 'downgrade'):
                logger.error(f"Migration {migration_file} không có hàm downgrade()")
                return False
            
            # Rollback migration
            async with get_db_cursor() as conn:
                async with conn.transaction():
                    await module.downgrade(conn)
                    
                    # Xóa khỏi migration history
                    delete_sql = "DELETE FROM migration_history WHERE migration_name = $1"
                    await conn.execute(delete_sql, migration_file)
            
            logger.info(f"Migration {migration_file} rolled back successfully")
            return True
            
        except Exception as e:
            logger.error(f"Lỗi rollback migration {migration_file}: {e}")
            return False
    
    async def migrate(self) -> bool:
        """
        Apply tất cả pending migrations
        """
        pending_migrations = await self.get_pending_migrations()
        
        if not pending_migrations:
            logger.info("Không có migration nào cần apply")
            return True
        
        logger.info(f"Tìm thấy {len(pending_migrations)} pending migrations")
        
        success_count = 0
        for migration in pending_migrations:
            if await self.apply_migration(migration):
                success_count += 1
            else:
                logger.error(f"Dừng migration tại: {migration}")
                break
        
        logger.info(f"Applied {success_count}/{len(pending_migrations)} migrations")
        return success_count == len(pending_migrations)
    
    async def rollback_last(self, count: int = 1) -> bool:
        """
        Rollback n migrations gần nhất
        """
        applied_migrations = await self.get_applied_migrations()
        
        if not applied_migrations:
            logger.info("Không có migration nào để rollback")
            return True
        
        # Lấy n migrations gần nhất để rollback
        to_rollback = applied_migrations[-count:] if count <= len(applied_migrations) else applied_migrations
        to_rollback.reverse()  # Rollback theo thứ tự ngược lại
        
        success_count = 0
        for migration in to_rollback:
            if await self.rollback_migration(migration):
                success_count += 1
            else:
                logger.error(f"Dừng rollback tại: {migration}")
                break
        
        logger.info(f"Rolled back {success_count}/{len(to_rollback)} migrations")
        return success_count == len(to_rollback)
    
    async def status(self):
        """
        Hiển thị trạng thái migrations
        """
        all_migrations = self.get_migration_files()
        applied_migrations = await self.get_applied_migrations()
        
        if not all_migrations:
            print("Không có migration files nào")
            return
        
        print("\n=== MIGRATION STATUS ===")
        for migration in all_migrations:
            status = "✓ Applied" if migration in applied_migrations else "✗ Pending"
            print(f"{status:<12} {migration}")
        
        print(f"\nTổng: {len(all_migrations)} migrations")
        print(f"Applied: {len(applied_migrations)}")
        print(f"Pending: {len(all_migrations) - len(applied_migrations)}")
    
    def create_migration(self, name: str, description: str = ""):
        """
        Tạo file migration mới
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{name}.py"
        filepath = self.migrations_dir / filename
        
        template = f'''"""
Migration: {name}
Description: {description}
Created: {datetime.now().isoformat()}
"""

async def upgrade(conn):
    """
    Apply migration changes
    """
    # Viết SQL để tạo/thay đổi database schema
    sql = """
    -- Thêm SQL commands ở đây
    """
    
    await conn.execute(sql)


async def downgrade(conn):
    """
    Rollback migration changes
    """
    # Viết SQL để rollback changes
    sql = """
    -- Thêm SQL rollback commands ở đây
    """
    
    await conn.execute(sql)
'''
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(template)
        
        logger.info(f"Created migration file: {filename}")
        print(f"Migration file created: {filepath}")
        return filename

# Helper functions
async def get_migration_manager():
    """Get or create migration manager instance"""
    manager = MigrationManager()
    await manager.initialize()
    return manager

async def migrate():
    """Apply all pending migrations"""
    manager = await get_migration_manager()
    return await manager.migrate()

async def rollback(count=1):
    """Rollback last n migrations"""
    manager = await get_migration_manager()
    return await manager.rollback_last(count)

async def migration_status():
    """Show migration status"""
    manager = await get_migration_manager()
    await manager.status()

def create_migration(name: str, description: str = ""):
    """Create new migration file"""
    manager = MigrationManager()
    return manager.create_migration(name, description)