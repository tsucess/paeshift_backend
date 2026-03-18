#!/usr/bin/env python
import sqlite3
import sys

# Connect to the database
conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Get table info for jobs_job
print("=== Current jobs_job table schema ===")
cursor.execute("PRAGMA table_info(jobs_job)")
columns = cursor.fetchall()
for col in columns:
    print(f"Column {col[1]}: {col[2]}")

# Check if start_date exists
has_start_date = any(col[1] == 'start_date' for col in columns)
has_date = any(col[1] == 'date' for col in columns)

print(f"\nhas_start_date: {has_start_date}")
print(f"has_date: {has_date}")

if not has_start_date and has_date:
    print("\n=== Fixing: Renaming 'date' to 'start_date' ===")
    try:
        cursor.execute("ALTER TABLE jobs_job RENAME COLUMN date TO start_date")
        conn.commit()
        print("✓ Successfully renamed 'date' to 'start_date'")
    except Exception as e:
        print(f"✗ Error: {e}")
        conn.close()
        sys.exit(1)
elif not has_start_date and not has_date:
    print("\n=== ERROR: Neither 'date' nor 'start_date' column exists ===")
    print("Need to add start_date column manually")
    try:
        cursor.execute("ALTER TABLE jobs_job ADD COLUMN start_date DATE")
        conn.commit()
        print("✓ Successfully added 'start_date' column")
    except Exception as e:
        print(f"✗ Error: {e}")
        conn.close()
        sys.exit(1)
else:
    print("\n✓ Schema is correct - start_date column exists")

conn.close()
print("\n=== Done ===")

