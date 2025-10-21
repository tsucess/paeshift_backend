#!/usr/bin/env python3
"""
Smart Database Configuration for Payshift
Handles PostgreSQL primary with SQLite fallback
"""

import os
from pathlib import Path

try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("⚠️  psycopg2 not available, will use SQLite fallback")

def test_postgres_connection():
    """Test PostgreSQL connection with your AWS RDS credentials"""
    if not PSYCOPG2_AVAILABLE:
        print("❌ psycopg2 not available, cannot test PostgreSQL connection")
        print("🔄 Will fallback to SQLite...")
        return False
        
    try:
        # AWS RDS PostgreSQL Configuration
        # DB Instance ID: paeshift-postgres-db
        # Engine: PostgreSQL
        # Region & AZ: us-east-1f
        host = 'paeshift-postgres-db.cmd66sgm8qyp.us-east-1.rds.amazonaws.com'  # Endpoint
        database = 'postgres'  # Default database
        user = 'postgres'      # Master username
        password = os.getenv('RDS_PASSWORD', os.getenv('DB_PASSWORD', '8137249989JoE'))
        port = '5432'          # Default PostgreSQL port
        
        print(f"Testing PostgreSQL connection to {host}:{port}/{database}")
        
        # Test connection with a shorter timeout for faster fallback
        conn = psycopg2.connect(
            host=host,
            database=database,
            user=user,
            password=password,
            port=port,
            connect_timeout=5,  # Reduced timeout for faster fallback
            sslmode='require'
        )
        
        # Test basic query
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.fetchone()
        cur.close()
        conn.close()
        
        print("✅ PostgreSQL connection successful!")
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        print("🔄 Will fallback to SQLite...")
        return False

def get_database_settings():
    """
    Get database settings with PostgreSQL primary and SQLite fallback
    """
    
    # Force SQLite if environment variable is set
    if os.getenv('FORCE_SQLITE', 'False').lower() == 'true':
        print("🔧 FORCE_SQLITE enabled, using SQLite database")
        return get_sqlite_config()
    
    # Try PostgreSQL first
    if test_postgres_connection():
        print("🐘 Using PostgreSQL database (primary)")
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'postgres',
            'USER': 'postgres',
            'PASSWORD': os.getenv('RDS_PASSWORD', os.getenv('DB_PASSWORD', '8137249989JoE')),
            'HOST': 'paeshift-postgres-db.cmd66sgm8qyp.us-east-1.rds.amazonaws.com',
            'PORT': '5432',
            'OPTIONS': {
                'sslmode': 'require',
            },
            'CONN_MAX_AGE': 60,
        }
    else:
        print("🗃️  Falling back to SQLite database (local)")
        return get_sqlite_config()

def get_sqlite_config():
    """Get SQLite configuration with proper permissions"""
    BASE_DIR = Path(__file__).resolve().parent
    db_path = BASE_DIR / 'db.sqlite3'
    
    # Ensure the database file has proper permissions
    if db_path.exists():
        try:
            # Make sure the file is writable
            os.chmod(db_path, 0o666)
        except Exception as e:
            print(f"⚠️  Warning: Could not set database permissions: {e}")
    
    # Ensure the directory is writable
    try:
        os.chmod(BASE_DIR, 0o755)
    except Exception as e:
        print(f"⚠️  Warning: Could not set directory permissions: {e}")
    
    return {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(db_path),
        'OPTIONS': {
            'timeout': 20,
        },
    }

def main():
    """Test the database configuration"""
    print("🔧 Testing Database Configuration...")
    print("=" * 50)
    
    config = get_database_settings()
    
    print("\n📊 Current Database Configuration:")
    print(f"Engine: {config['ENGINE']}")
    if 'HOST' in config:
        print(f"Host: {config['HOST']}")
        print(f"Database: {config['NAME']}")
        print(f"User: {config['USER']}")
        print(f"Port: {config['PORT']}")
    else:
        print(f"SQLite file: {config['NAME']}")
    
    print("\n✅ Database configuration ready!")
    return config

if __name__ == "__main__":
    main()
