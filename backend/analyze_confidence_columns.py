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

print("="*100)
print("ICAP_INVOICE TABLE - Column Types")
print("="*100)

cursor.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'icap_invoice' 
    AND column_name IN ('vendor_id', 'invoice_number', 'invoice_date', 'due_date')
    ORDER BY ordinal_position;
""")

for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]}")

print("\n" + "="*100)
print("ICAP_INVOICE_DETAIL TABLE - Column Types")
print("="*100)

cursor.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'icap_invoice_detail' 
    AND column_name IN ('description', 'quantity', 'unit_price')
    ORDER BY ordinal_position;
""")

for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]}")

print("\n" + "="*100)
print("SAMPLE DATA - icap_invoice")
print("="*100)

cursor.execute("""
    SELECT 
        vendor_id,
        invoice_number,
        invoice_date,
        due_date
    FROM icap_invoice
    LIMIT 2;
""")

for row in cursor.fetchall():
    print(f"\nvendor_id: {row[0]} (type: UUID - NO CONFIDENCE)")
    print(f"invoice_number: {row[1]}")
    print(f"invoice_date: {row[2]}")
    print(f"due_date: {row[3]}")

print("\n" + "="*100)
print("SAMPLE DATA - icap_invoice_detail")
print("="*100)

cursor.execute("""
    SELECT 
        description,
        quantity,
        unit_price
    FROM icap_invoice_detail
    LIMIT 2;
""")

for row in cursor.fetchall():
    print(f"\ndescription: {row[0]}")
    print(f"quantity: {row[1]}")
    print(f"unit_price: {row[2]}")

cursor.close()
conn.close()
