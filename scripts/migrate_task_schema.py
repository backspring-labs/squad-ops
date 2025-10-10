#!/usr/bin/env python3
"""
Migration script for Phase 1 Task Management implementation
Safely migrates from agent_task_logs to execution_cycle and agent_task_log tables
"""

import asyncio
import asyncpg
import os
import sys
from datetime import datetime

# Database connection
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://squadops:squadops123@localhost:5432/squadops")

async def check_existing_data():
    """Check what data exists in the current tables"""
    pool = await asyncpg.create_pool(POSTGRES_URL)
    async with pool.acquire() as conn:
        # Check if agent_task_logs exists and has data
        try:
            count = await conn.fetchval("SELECT COUNT(*) FROM agent_task_logs")
            print(f"Found {count} records in agent_task_logs table")
            return count > 0
        except Exception as e:
            print(f"agent_task_logs table doesn't exist or is empty: {e}")
            return False

async def backup_existing_data():
    """Backup existing data before migration"""
    pool = await asyncpg.create_pool(POSTGRES_URL)
    async with pool.acquire() as conn:
        try:
            # Create backup table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_task_logs_backup AS 
                SELECT * FROM agent_task_logs
            """)
            count = await conn.fetchval("SELECT COUNT(*) FROM agent_task_logs_backup")
            print(f"Backed up {count} records to agent_task_logs_backup")
            return True
        except Exception as e:
            print(f"Backup failed: {e}")
            return False

async def apply_schema_changes():
    """Apply the new schema changes"""
    pool = await asyncpg.create_pool(POSTGRES_URL)
    async with pool.acquire() as conn:
        try:
            # Drop old table (CASCADE will handle any dependencies)
            await conn.execute("DROP TABLE IF EXISTS agent_task_logs CASCADE")
            print("Dropped agent_task_logs table")
            
            # Create execution_cycle table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_cycle (
                    ecid TEXT PRIMARY KEY,
                    pid TEXT NOT NULL,
                    run_type TEXT CHECK (run_type IN ('warmboot','project','experiment','tuning')),
                    title TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT now(),
                    initiated_by TEXT,
                    status TEXT DEFAULT 'active',
                    notes TEXT
                )
            """)
            print("Created execution_cycle table")
            
            # Create agent_task_log table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_task_log (
                    task_id TEXT PRIMARY KEY,
                    pid TEXT,
                    ecid TEXT REFERENCES execution_cycle(ecid),
                    agent TEXT NOT NULL,
                    phase TEXT,
                    status TEXT NOT NULL,
                    priority TEXT,
                    description TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    duration INTERVAL,
                    artifacts JSONB,
                    dependencies TEXT[],
                    error_log TEXT,
                    delegated_by TEXT,
                    delegated_to TEXT,
                    created_at TIMESTAMP DEFAULT now()
                )
            """)
            print("Created agent_task_log table")
            
            # Create indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_task_log_ecid ON agent_task_log(ecid)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_task_log_agent ON agent_task_log(agent)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_task_log_status ON agent_task_log(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_execution_cycle_run_type ON execution_cycle(run_type)")
            print("Created indexes")
            
            return True
            
        except Exception as e:
            print(f"Schema migration failed: {e}")
            return False

async def verify_migration():
    """Verify the migration was successful"""
    pool = await asyncpg.create_pool(POSTGRES_URL)
    async with pool.acquire() as conn:
        try:
            # Check execution_cycle table
            exec_count = await conn.fetchval("SELECT COUNT(*) FROM execution_cycle")
            print(f"execution_cycle table has {exec_count} records")
            
            # Check agent_task_log table
            task_count = await conn.fetchval("SELECT COUNT(*) FROM agent_task_log")
            print(f"agent_task_log table has {task_count} records")
            
            # Check that old table is gone
            try:
                await conn.fetchval("SELECT COUNT(*) FROM agent_task_logs")
                print("ERROR: agent_task_logs table still exists!")
                return False
            except:
                print("✓ agent_task_logs table successfully removed")
            
            return True
            
        except Exception as e:
            print(f"Verification failed: {e}")
            return False

async def main():
    """Main migration function"""
    print("=== SquadOps Task Management Schema Migration ===")
    print(f"Database: {POSTGRES_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    # Check existing data
    has_data = await check_existing_data()
    
    if has_data:
        print("⚠️  Existing data found. Creating backup...")
        backup_success = await backup_existing_data()
        if not backup_success:
            print("❌ Backup failed. Aborting migration.")
            return False
    else:
        print("✓ No existing data to backup")
    
    # Apply schema changes
    print("\n🔄 Applying schema changes...")
    schema_success = await apply_schema_changes()
    if not schema_success:
        print("❌ Schema migration failed.")
        return False
    
    # Verify migration
    print("\n🔍 Verifying migration...")
    verify_success = await verify_migration()
    if not verify_success:
        print("❌ Migration verification failed.")
        return False
    
    print("\n✅ Migration completed successfully!")
    print("\nNext steps:")
    print("1. Restart the task-api service")
    print("2. Restart all agent containers")
    print("3. Test with a WarmBoot run")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
