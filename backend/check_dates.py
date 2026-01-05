import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    dbname=os.getenv('POSTGRES_DB_NAME'),
    user=os.getenv('POSTGRES_USER'),
    password=os.getenv('POSTGRES_PASSWORD'),
    host=os.getenv('POSTGRES_HOST'),
    port=os.getenv('POSTGRES_PORT')
)

cursor = conn.cursor()

# Check sample dates in database
cursor.execute("SELECT DISTINCT i.invoice_date->>'value' as invoice_date FROM icap_invoice i WHERE i.invoice_date->>'value' IS NOT NULL ORDER BY invoice_date LIMIT 20")
rows = cursor.fetchall()

print('\n📅 Sample dates in database:')
for row in rows:
    print(f"  - {row[0]}")

# Check if any February 2025 dates exist
cursor.execute("SELECT COUNT(*) as count FROM icap_invoice i WHERE i.invoice_date->>'value' LIKE '02/%/2025'")
count1 = cursor.fetchone()[0]
print(f"\n🔍 February 2025 invoices (LIKE pattern): {count1}")

# Check using TO_DATE for Feb 2025
cursor.execute("SELECT COUNT(*) as count FROM icap_invoice i WHERE TO_DATE(i.invoice_date->>'value', 'MM/DD/YYYY') BETWEEN TO_DATE('02/01/2025', 'MM/DD/YYYY') AND TO_DATE('02/28/2025', 'MM/DD/YYYY')")
count2 = cursor.fetchone()[0]
print(f"🔍 February 2025 invoices (TO_DATE): {count2}")

cursor.close()
conn.close()
