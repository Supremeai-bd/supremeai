import asyncio
import os

import asyncpg


async def run_migration():
    # Setup database url
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    # Read sql file from centralized database migrations home
    target_sql = os.path.join(
        os.path.dirname(__file__),
        '../../backend/database/migrations/legacy/phase3_multi_tenant_schema.sql',
    )
    with open(target_sql, 'r') as f:
        sql = f.read()
        
    print('Connecting to database...')
    conn = await asyncpg.connect(db_url)
    try:
        print('Executing migration...')
        await conn.execute(sql)
        print('Migration applied successfully!')
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run_migration())
