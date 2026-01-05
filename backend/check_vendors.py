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

# Find all vendors with names containing "meat" (case insensitive)
cursor.execute("""
    SELECT id, name, company, address
    FROM icap_vendor
    WHERE LOWER(name) LIKE '%meat%'
    ORDER BY name;
""")

print("📋 Vendors with 'meat' in name:")
print("="*80)
results = cursor.fetchall()
if results:
    for row in results:
        print(f"ID: {row[0]}")
        print(f"Name: '{row[1]}'")
        print(f"Company: '{row[2]}'")
        print(f"Address: {row[3]}")
        print("-"*80)
else:
    print("No vendors found with 'meat' in name")

# Also check for exact "Meat Hub"
cursor.execute("""
    SELECT id, name, company
    FROM icap_vendor
    WHERE name = 'Meat Hub'
    LIMIT 5;
""")

print("\n📋 Exact match for 'Meat Hub':")
print("="*80)
results = cursor.fetchall()
if results:
    for row in results:
        print(f"ID: {row[0]}, Name: '{row[1]}', Company: '{row[2]}'")
else:
    print("No exact match found")

# Check all vendors (first 20)
cursor.execute("""
    SELECT id, name
    FROM icap_vendor
    ORDER BY name
    LIMIT 20;
""")

print("\n📋 First 20 vendors in database:")
print("="*80)
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Name: '{row[1]}'")

cursor.close()
conn.close()
