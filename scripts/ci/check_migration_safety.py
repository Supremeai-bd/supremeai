import os
import glob
import re
import sys

def check_migration_safety():
    """
    Scans Alembic migration files for destructive operations.
    If 'drop_column', 'alter_column', or 'drop_table' are found without 
    a 'IGNORE_SAFETY_WARNING' comment, it fails the CI step.
    This ensures zero-downtime deployments.
    """
    alembic_dir = os.path.join("backend", "alembic", "versions")
    
    if not os.path.exists(alembic_dir):
        print(f"Warning: Alembic directory not found at {alembic_dir}")
        return 0

    migration_files = glob.glob(os.path.join(alembic_dir, "*.py"))
    
    destructive_patterns = [
        re.compile(r"op\.drop_column"),
        re.compile(r"op\.drop_table"),
        re.compile(r"op\.alter_column\(.*type_=.*\)"), # Changing column type
    ]

    unsafe_files = []

    for file_path in migration_files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

            # If developer explicitly bypasses this safety check
            if "IGNORE_SAFETY_WARNING" in content:
                continue

            for pattern in destructive_patterns:
                if pattern.search(content):
                    unsafe_files.append((file_path, pattern.pattern))

    if unsafe_files:
        print("\n❌ DANGER: Destructive database migrations detected!\n")
        print("To achieve zero-downtime deployments, avoid dropping or altering columns.")
        print("Instead, use the Expand & Contract pattern:\n")
        print("1. Add the new column/table.")
        print("2. Deploy and dual-write to both.")
        print("3. Backfill old data.")
        print("4. Drop the old column in a future release.\n")
        
        for file_path, pattern in unsafe_files:
            print(f"- {file_path} contains unsafe operation matching: {pattern}")
            
        print("\nIf you are absolutely sure this is safe, add '# IGNORE_SAFETY_WARNING' to the migration file.\n")
        return 1
        
    print("✅ All migrations pass the zero-downtime safety check.")
    return 0

if __name__ == "__main__":
    sys.exit(check_migration_safety())
