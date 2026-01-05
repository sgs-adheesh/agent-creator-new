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

# Check what status values actually exist in data
cursor.execute("""
    SELECT 
        status,
        COUNT(*) as count,
        STRING_AGG(DISTINCT (invoice_number->>'value')::text, ', ') as sample_invoices
    FROM icap_invoice
    WHERE status IS NOT NULL
    GROUP BY status
    ORDER BY status;
""")

print("📊 Actual status values in icap_invoice:")
print("="*60)
for row in cursor.fetchall():
    status, count, samples = row
    sample_list = (samples or '')[:100] + '...' if samples and len(samples) > 100 else (samples or 'N/A')
    print(f"Status: '{status}' → {count} invoices")
    print(f"  Sample invoices: {sample_list}\n")

# Check if there are any other status-like columns
cursor.execute("""
    SELECT column_name, data_type, udt_name
    FROM information_schema.columns
    WHERE table_name = 'icap_invoice' 
    AND (column_name LIKE '%status%' OR column_name LIKE '%approval%' OR column_name LIKE '%quality%')
    ORDER BY column_name;
""")

print("\n📋 Status-related columns in icap_invoice:")
print("="*60)
for row in cursor.fetchall():
    print(f"  {row[0]} ({row[1]}, {row[2]})")

cursor.close()
conn.close()
