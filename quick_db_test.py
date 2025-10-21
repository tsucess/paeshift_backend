import psycopg2

# Test with current config first
try:
    conn = psycopg2.connect(
        host='paeshift-postgres-db.cmd66sgm8qyp.us-east-1.rds.amazonaws.com',
        database='payshift_production',
        user='payshift_admin',
        password='8137249989JoE',
        port=5432,
        connect_timeout=10
    )
    print("✅ SUCCESS: payshift_production/payshift_admin works!")
    conn.close()
except Exception as e:
    print(f"❌ FAILED: payshift_production/payshift_admin - {e}")
    
    # Try default postgres config
    try:
        conn = psycopg2.connect(
            host='paeshift-postgres-db.cmd66sgm8qyp.us-east-1.rds.amazonaws.com',
            database='postgres',
            user='postgres',
            password='8137249989JoE',
            port=5432,
            connect_timeout=10
        )
        print("✅ SUCCESS: postgres/postgres works!")
        conn.close()
    except Exception as e2:
        print(f"❌ FAILED: postgres/postgres - {e2}")
        print("🔧 Need to check RDS settings manually")
