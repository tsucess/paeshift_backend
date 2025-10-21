#!/usr/bin/env python3
"""
Fix database permissions for SQLite fallback
"""

import os
import stat
from pathlib import Path

def fix_database_permissions():
    """Fix SQLite database permissions to prevent readonly errors"""
    
    BASE_DIR = Path(__file__).resolve().parent
    db_path = BASE_DIR / 'db.sqlite3'
    
    print("🔧 Fixing database permissions...")
    
    # Ensure the directory is writable
    try:
        current_dir_perms = os.stat(BASE_DIR).st_mode
        if not (current_dir_perms & stat.S_IWUSR):
            os.chmod(BASE_DIR, current_dir_perms | stat.S_IWUSR | stat.S_IWGRP)
            print(f"✅ Fixed directory permissions: {BASE_DIR}")
        else:
            print(f"✅ Directory permissions OK: {BASE_DIR}")
    except Exception as e:
        print(f"⚠️  Warning: Could not fix directory permissions: {e}")
    
    # Fix database file permissions if it exists
    if db_path.exists():
        try:
            current_file_perms = os.stat(db_path).st_mode
            if not (current_file_perms & stat.S_IWUSR):
                os.chmod(db_path, current_file_perms | stat.S_IWUSR | stat.S_IWGRP)
                print(f"✅ Fixed database file permissions: {db_path}")
            else:
                print(f"✅ Database file permissions OK: {db_path}")
        except Exception as e:
            print(f"⚠️  Warning: Could not fix database file permissions: {e}")
    else:
        print(f"📝 Database file will be created: {db_path}")
    
    # Remove any readonly flags
    try:
        if db_path.exists():
            # Remove readonly attribute on Windows
            if os.name == 'nt':
                import subprocess
                subprocess.run(['attrib', '-R', str(db_path)], check=False)
                print("✅ Removed readonly attribute (Windows)")
    except Exception as e:
        print(f"⚠️  Warning: Could not remove readonly attribute: {e}")
    
    print("🎉 Database permissions fixed!")
    return True

if __name__ == "__main__":
    fix_database_permissions()
