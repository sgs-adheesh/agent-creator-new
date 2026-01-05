import psycopg2
from config import settings

conn = psycopg2.connect(
    host=settings.postgres_host,
    port=settings.postgres_port,
    database=settings.postgres_database,
    user=settings.postgres_user,
    password=settings.postgres_password
)

cursor = conn.cursor()

# Check enum values for payment_status_enum
cursor.execute("""
    SELECT enumlabel 
    FROM pg_enum 
    WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'payment_status_enum')
    ORDER BY enumsortorder;
""")

print("Valid status ENUM values:")
for row in cursor.fetchall():
    print(f"  - '{row[0]}'")

# Check icap_invoice table structure
cursor.execute("""
    SELECT column_name, data_type, udt_name
    FROM information_schema.columns
    WHERE table_name = 'icap_invoice' AND column_name = 'status';
""")

print("\nColumn info:")
for row in cursor.fetchall():
    print(f"  Column: {row[0]}, Type: {row[1]}, UDT: {row[2]}")

cursor.close()
conn.close()
