import sys
import argparse
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from migration_manager import (
    migrate, 
    rollback, 
    migration_status, 
    create_migration
)

async def main():
    parser = argparse.ArgumentParser(
        description='Database Migration Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python migrations/cli.py status              # Show migration status
  python migrations/cli.py migrate             # Apply all pending migrations
  python migrations/cli.py rollback            # Rollback last migration
  python migrations/cli.py rollback --count 3  # Rollback last 3 migrations
  python migrations/cli.py create users        # Create new migration for users
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show migration status')
    
    # Migrate command
    migrate_parser = subparsers.add_parser('migrate', help='Apply all pending migrations')
    
    # Rollback command
    rollback_parser = subparsers.add_parser('rollback', help='Rollback migrations')
    rollback_parser.add_argument(
        'count', 
        type=int, 
        nargs='?', 
        default=1, 
        help='Number of migrations to rollback'
    )
    
    # Create migration command
    create_parser = subparsers.add_parser('create', help='Create new migration')
    create_parser.add_argument('name', help='Migration name')
    create_parser.add_argument(
        '--description', 
        '-d', 
        help='Migration description'
    )
    
    args = parser.parse_args()
    
    if args.command == 'migrate':
        print("Starting migration...")
        success = await migrate()
        print("✓ All migrations completed successfully" if success else "✗ Migration failed")
        sys.exit(0 if success else 1)
    elif args.command == 'rollback':
        print(f"Rolling back {args.count} migration(s)...")
        success = await rollback(args.count)
        print("✓ Rollback completed successfully" if success else "✗ Rollback failed")
        sys.exit(0 if success else 1)
    elif args.command == 'status':
        await migration_status()
    elif args.command == 'create':
        filename = create_migration(args.name, args.description or '')
        print(f"✓ Migration created: {filename}")
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())