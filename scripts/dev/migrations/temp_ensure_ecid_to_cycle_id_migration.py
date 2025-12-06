#!/usr/bin/env python3
"""
Migration script: Ensure all ecid columns are renamed to cycle_id (SIP-0048)
Date: 2025-12-03
Purpose: Final migration to ensure all ecid columns are renamed to cycle_id
This migration is idempotent and safe to run multiple times
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime
from pathlib import Path

# Database connection
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://squadops:squadops123@localhost:5432/squadops")

# Get the migration SQL file path
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent
MIGRATION_FILE = REPO_ROOT / "infra" / "migrations" / "012_ensure_ecid_to_cycle_id_migration.sql"


async def check_current_state(pool):
    """Check the current state of the database"""
    async with pool.acquire() as conn:
        # Check if ecid column exists
        ecid_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'squad_mem_pool' 
                AND column_name = 'ecid'
                AND table_schema = 'public'
            )
        """)
        
        # Check if cycle_id column exists
        cycle_id_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'squad_mem_pool' 
                AND column_name = 'cycle_id'
                AND table_schema = 'public'
            )
        """)
        
        # Check if old index exists
        old_index_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes 
                WHERE indexname = 'idx_squad_mem_pool_ecid'
                AND schemaname = 'public'
            )
        """)
        
        # Check if new index exists
        new_index_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes 
                WHERE indexname = 'idx_squad_mem_pool_cycle_id'
                AND schemaname = 'public'
            )
        """)
        
        return {
            'ecid_exists': ecid_exists,
            'cycle_id_exists': cycle_id_exists,
            'old_index_exists': old_index_exists,
            'new_index_exists': new_index_exists
        }


async def apply_migration(pool):
    """Apply the migration SQL"""
    if not MIGRATION_FILE.exists():
        print(f"❌ Migration file not found: {MIGRATION_FILE}")
        return False
    
    async with pool.acquire() as conn:
        try:
            # Read the migration SQL file
            migration_sql = MIGRATION_FILE.read_text()
            
            # Execute the migration
            print("📝 Executing migration SQL...")
            await conn.execute(migration_sql)
            
            print("✅ Migration SQL executed successfully")
            return True
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            return False


async def verify_migration(pool):
    """Verify the migration completed successfully"""
    async with pool.acquire() as conn:
        try:
            # Check if cycle_id column exists
            cycle_id_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'squad_mem_pool' 
                    AND column_name = 'cycle_id'
                    AND table_schema = 'public'
                )
            """)
            
            # Check if ecid column still exists (should be False)
            ecid_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'squad_mem_pool' 
                    AND column_name = 'ecid'
                    AND table_schema = 'public'
                )
            """)
            
            # Check if new index exists
            new_index_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_indexes 
                    WHERE indexname = 'idx_squad_mem_pool_cycle_id'
                    AND schemaname = 'public'
                )
            """)
            
            # Check if old index still exists (should be False)
            old_index_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_indexes 
                    WHERE indexname = 'idx_squad_mem_pool_ecid'
                    AND schemaname = 'public'
                )
            """)
            
            print("\n🔍 Migration Verification:")
            print(f"  cycle_id column exists: {'✅' if cycle_id_exists else '❌'}")
            print(f"  ecid column removed: {'✅' if not ecid_exists else '❌'}")
            print(f"  cycle_id index exists: {'✅' if new_index_exists else '❌'}")
            print(f"  old ecid index removed: {'✅' if not old_index_exists else '❌'}")
            
            if cycle_id_exists and not ecid_exists and new_index_exists and not old_index_exists:
                print("\n✅ Migration verification passed!")
                return True
            else:
                print("\n⚠️  Migration verification found issues")
                return False
                
        except Exception as e:
            print(f"❌ Verification failed: {e}")
            return False


async def main():
    """Main migration function"""
    print("=== SquadOps ECID to Cycle ID Migration ===")
    print(f"Database: {POSTGRES_URL}")
    print(f"Migration file: {MIGRATION_FILE}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    # Create a single connection pool for all operations
    pool = None
    try:
        pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=2)
        
        # Check current state
        print("🔍 Checking current database state...")
        state = await check_current_state(pool)
        
        print("\n📊 Current State:")
        print(f"  ecid column exists: {'Yes' if state['ecid_exists'] else 'No'}")
        print(f"  cycle_id column exists: {'Yes' if state['cycle_id_exists'] else 'No'}")
        print(f"  old index exists: {'Yes' if state['old_index_exists'] else 'No'}")
        print(f"  new index exists: {'Yes' if state['new_index_exists'] else 'No'}")
        
        # Determine if migration is needed
        needs_migration = state['ecid_exists'] or state['old_index_exists'] or not state['cycle_id_exists']
        
        if not needs_migration and state['cycle_id_exists'] and state['new_index_exists']:
            print("\n✅ Database is already migrated. No changes needed.")
            await verify_migration(pool)
            return True
        
        # Apply migration
        print("\n🔄 Applying migration...")
        success = await apply_migration(pool)
        
        if not success:
            print("\n❌ Migration failed")
            return False
        
        # Verify migration
        print("\n🔍 Verifying migration...")
        verify_success = await verify_migration(pool)
        
        if not verify_success:
            print("\n⚠️  Migration completed but verification found issues")
            print("   Check the database manually to ensure everything is correct")
            return False
        
        print("\n✅ Migration completed successfully!")
        print("\n💡 Next steps:")
        print("   1. Restart agents to ensure they're using the new cycle_id column")
        print("   2. Verify that all code references cycle_id (not ecid)")
        print("   3. Test with a WarmBoot run to ensure everything works")
        
        return True
        
    except asyncpg.exceptions.InvalidPasswordError:
        print("❌ Database authentication failed. Check POSTGRES_URL environment variable.")
        return False
    except asyncpg.exceptions.ConnectionDoesNotExistError:
        print("❌ Could not connect to database. Is PostgreSQL running?")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if pool:
            await pool.close()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

