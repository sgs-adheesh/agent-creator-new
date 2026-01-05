import psycopg2
from config import settings
import json

conn = psycopg2.connect(
    host=settings.postgres_host,
    port=settings.postgres_port,
    database=settings.postgres_database,
    user=settings.postgres_user,
    password=settings.postgres_password
)

cursor = conn.cursor()

# Get sample invoice with JSONB structure
cursor.execute("""
    SELECT 
        (invoice_number->>'value')::text AS inv_num,
        (invoice_number->>'confidence')::numeric AS inv_num_conf,
        (invoice_date->>'confidence')::numeric AS inv_date_conf,
        (total->>'confidence')::numeric AS total_conf,
        invoice_number,
        invoice_date,
        total,
        status
    FROM icap_invoice
    WHERE (invoice_number->>'value') IS NOT NULL
    AND (invoice_number->>'value') != ''
    LIMIT 5;
""")

print("📊 Sample Invoice Confidence Scores:")
print("="*100)
for row in cursor.fetchall():
    print(f"Invoice: {row[0]}")
    print(f"  - Invoice Number Confidence: {row[1]}")
    print(f"  - Invoice Date Confidence: {row[2]}")
    print(f"  - Total Confidence: {row[3]}")
    print(f"  - Status: {row[7]}")
    print(f"\nFull JSONB structure:")
    print(f"  invoice_number: {json.dumps(row[4], indent=2)}")
    print(f"  invoice_date: {json.dumps(row[5], indent=2)}")
    print(f"  total: {json.dumps(row[6], indent=2)}")
    print("-"*100)

cursor.close()
conn.close()
