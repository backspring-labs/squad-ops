#!/usr/bin/env python3
"""
Apply memory_count migration to agent_status table
Ensures the column exists for tracking agent memory counts
"""

import asyncio
import asyncpg
import os
import sys

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://squadops:squadops123@localhost:5432/squadops")

async def check_column_exists(pool):
    """Check if memory_count column already exists"""
    async with pool.acquire() as conn:
        try:
            # Check if column exists
            result = await conn.fetchval("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'agent_status' 
                AND column_name = 'memory_count'
            """)
            return result is not None
        except Exception as e:
            print(f"Error checking column: {e}")
            return False

async def apply_migration(pool):
    """Apply the memory_count migration"""
    async with pool.acquire() as conn:
        try:
            # Apply migration
            await conn.execute("""
                ALTER TABLE agent_status 
                ADD COLUMN IF NOT EXISTS memory_count INTEGER DEFAULT 0
            """)
            
            # Add comment
            await conn.execute("""
                COMMENT ON COLUMN agent_status.memory_count IS 'Number of memories stored in LanceDB for this agent'
            """)
            
            print("✅ Migration applied successfully")
            return True
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            return False

async def verify_migration(pool):
    """Verify the migration was applied correctly"""
    async with pool.acquire() as conn:
        try:
            # Check column exists and get sample data
            result = await conn.fetchrow("""
                SELECT 
                    column_name,
                    data_type,
                    column_default
                FROM information_schema.columns 
                WHERE table_name = 'agent_status' 
                AND column_name = 'memory_count'
            """)
            
            if result:
                print(f"✅ Column verified: {result['column_name']} ({result['data_type']}, default: {result['column_default']})")
                
                # Check current agent statuses
                agents = await conn.fetch("""
                    SELECT agent_name, memory_count 
                    FROM agent_status 
                    ORDER BY agent_name
                """)
                
                if agents:
                    print(f"\n📊 Current agent memory counts:")
                    for agent in agents:
                        print(f"   {agent['agent_name']}: {agent['memory_count']} memories")
                else:
                    print("\n📊 No agents registered yet (will appear after agents send heartbeats)")
                
                return True
            else:
                print("❌ Column not found after migration")
                return False
        except Exception as e:
            print(f"❌ Verification failed: {e}")
            return False

async def main():
    """Main migration function"""
    print("=== SquadOps Memory Count Migration ===")
    print(f"Database: {POSTGRES_URL}")
    print()
    
    # Create a single connection pool for all operations
    pool = None
    try:
        pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=2)
        
        # Check if column already exists
        print("🔍 Checking if memory_count column exists...")
        exists = await check_column_exists(pool)
        
        if exists:
            print("✅ Column already exists, verifying...")
            await verify_migration(pool)
        else:
            print("📝 Column not found, applying migration...")
            success = await apply_migration(pool)
            
            if success:
                print("\n🔍 Verifying migration...")
                await verify_migration(pool)
            else:
                print("\n❌ Migration failed")
                return False
        
        print("\n✅ Migration complete!")
        print("\n💡 Next steps:")
        print("   1. Restart agents to ensure they're using LanceDBAdapter")
        print("   2. Run a WarmBoot to generate memories")
        print("   3. Check health dashboard at http://localhost:8000/health")
        print("   4. Memory counts will update every 30 seconds via agent heartbeats")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        if pool:
            await pool.close()

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)


