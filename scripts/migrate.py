import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_migrations():
    # Fetch database connection string
    conn_string = os.getenv("SUPABASE_DATABASE_URL")
    pooler_string = os.getenv("SUPABASE_DATABASE_URL_POOLER")
    
    if not conn_string and not pooler_string:
        print("[Error] No database URL found in environment variables.")
        return

    print("[Info] Connecting to Supabase PostgreSQL database...")
    conn = None
    
    # Try direct connection URL first
    if conn_string:
        try:
            print("[Info] Trying direct connection...")
            conn = psycopg2.connect(conn_string)
        except Exception as e:
            print(f"[Warning] Direct connection failed: {e}")

    # Fallback to Pooler connection URL
    if not conn and pooler_string:
        try:
            print("[Info] Trying pooler connection...")
            conn = psycopg2.connect(pooler_string)
        except Exception as e:
            print(f"[Error] Pooler connection failed: {e}")

    if not conn:
        print("[Error] Could not connect to any database connection string. Please check internet connection or database credentials.")
        return
        
    conn.autocommit = True

    migrations_dir = os.path.join("backend", "database", "migrations")
    if not os.path.exists(migrations_dir):
        print(f"[Error] Migrations directory '{migrations_dir}' not found.")
        conn.close()
        return

    # List and sort migrations
    migration_files = sorted(
        [f for f in os.listdir(migrations_dir) if f.endswith(".sql")]
    )

    import sys
    start_from = sys.argv[1] if len(sys.argv) > 1 else ""
    if start_from:
        if start_from in migration_files:
            migration_files = migration_files[migration_files.index(start_from):]
            print(f"[Info] Resuming migrations from: {start_from}")
        else:
            print(f"[Error] Start migration file '{start_from}' not found in migrations folder.")
            conn.close()
            return

    print(f"[Info] Found {len(migration_files)} migration files to run.")

    for file_name in migration_files:
        file_path = os.path.join(migrations_dir, file_name)
        print(f"[Run] Running migration: {file_name}...")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                sql_script = f.read()

            with conn.cursor() as cursor:
                cursor.execute(sql_script)
            print(f"[Success] Migration successful: {file_name}")
        except Exception as e:
            print(f"[Error] Error running migration {file_name}: {e}")
            print("[Warning] Stopping migration process.")
            break

    conn.close()
    print("[Info] Database connection closed.")

if __name__ == "__main__":
    run_migrations()
