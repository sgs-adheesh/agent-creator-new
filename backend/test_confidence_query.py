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

# Test the exact CTE query from template (threshold=90 for testing)
query = """
WITH invoice_detail_confidence AS (
    SELECT 
        ivd.document_id,
        MIN((ivd.description->>'confidence')::numeric) AS min_desc_conf,
        MIN((ivd.quantity->>'confidence')::numeric) AS min_qty_conf,
        MIN((ivd.unit_price->>'confidence')::numeric) AS min_price_conf,
        COUNT(*) AS line_count
    FROM icap_invoice_detail ivd
    GROUP BY ivd.document_id
    HAVING MIN((ivd.description->>'confidence')::numeric) >= 90.0
        AND MIN((ivd.quantity->>'confidence')::numeric) >= 90.0
        AND MIN((ivd.unit_price->>'confidence')::numeric) >= 90.0
)
SELECT
    i.id,
    (i.invoice_number->>'value')::text AS invoice_number,
    (i.invoice_number->>'confidence')::numeric AS inv_num_conf,
    (i.invoice_date->>'value')::text AS invoice_date,
    (i.invoice_date->>'confidence')::numeric AS inv_date_conf,
    (i.due_date->>'value')::text AS due_date,
    (i.due_date->>'confidence')::numeric AS due_date_conf,
    v.name AS vendor_name,
    idc.line_count,
    idc.min_desc_conf,
    idc.min_qty_conf,
    idc.min_price_conf,
    LEAST(
        (i.invoice_number->>'confidence')::numeric,
        (i.invoice_date->>'confidence')::numeric,
        (i.due_date->>'confidence')::numeric,
        idc.min_desc_conf,
        idc.min_qty_conf,
        idc.min_price_conf
    ) AS overall_min_confidence,
    i.status
FROM icap_invoice i
LEFT JOIN icap_vendor v ON i.vendor_id = v.id
INNER JOIN invoice_detail_confidence idc ON i.document_id = idc.document_id
WHERE i.status = '0'
  AND (i.invoice_number->>'confidence')::numeric >= 90.0
  AND (i.invoice_date->>'confidence')::numeric >= 90.0
  AND (i.due_date->>'confidence')::numeric >= 90.0
ORDER BY overall_min_confidence DESC
LIMIT 5;
"""

print("🔍 Testing Confidence-Based Query (threshold=90):")
print("="*100)

cursor.execute(query)
results = cursor.fetchall()

if results:
    print(f"\n✅ Found {len(results)} qualifying invoices:\n")
    for row in results:
        print(f"Invoice: {row[1]}")
        print(f"  Vendor: {row[7]}")
        print(f"  Status: {row[13]}")
        print(f"  Line Items: {row[8]}")
        print(f"  Confidence Scores:")
        print(f"    - Invoice Number: {row[2]}")
        print(f"    - Invoice Date: {row[4]}")
        print(f"    - Due Date: {row[6]}")
        print(f"    - Description (min): {row[9]}")
        print(f"    - Quantity (min): {row[10]}")
        print(f"    - Unit Price (min): {row[11]}")
        print(f"    - Overall Min: {row[12]}")
        print("-"*100)
else:
    print("\n❌ No invoices found meeting criteria")

cursor.close()
conn.close()
